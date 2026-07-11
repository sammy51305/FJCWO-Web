import re
from itertools import groupby

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.deletion import Collector, ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import BootstrapAuthenticationForm, ProfileForm
from .models import InstrumentFamily, InstrumentType, Registration, SectionType, User
from .utils import send_temp_password_email


def _unique_username(base):
    base = re.sub(r'[^\w.@+-]', '', base) or 'member'
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f'{base}{suffix}'
    return username


def _user_has_related_records(user):
    """
    用 Django 的 Collector 模擬一次刪除，檢查這個帳號是否已被任何其他資料表參照
    （出席、請假、借用、財務、公告…）。只要有牽連（含 CASCADE 會被連帶刪除、
    SET_NULL 會被清空、或 PROTECT 直接擋下），就代表這個帳號已經「被使用過」，
    不該真的刪除，只能用「退團」（is_active=False）處理。
    用 Collector 而非手動列出每張表，是因為未來新增別的 app 參照 User 時不用回來改這裡。
    """
    collector = Collector(using='default')
    try:
        collector.collect([user])
    except ProtectedError:
        return True
    for model, instances in collector.data.items():
        if model is not User and len(instances) > 0:
            return True
    # 有些 CASCADE 反向關聯 Django 會走「快速刪除路徑」，直接發 SQL DELETE，
    # 不會經過 collector.data，而是放在 collector.fast_deletes（一批 QuerySet）。
    for qs in collector.fast_deletes:
        if qs.model is not User and qs.exists():
            return True
    # collector.field_updates 的 key 是 (field, value)，不是 model；
    # value 是尚未評估的 QuerySet 列表，要看 QuerySet 內容是否真的有資料，
    # 不能只看 list 長度（SET_NULL 欄位一定會出現在這裡，即使對應資料是空的）。
    for (field, value), querysets in collector.field_updates.items():
        for qs in querysets:
            if qs.exists():
                return True
    return False


def _create_member_with_temp_password(*, name, email, instrument=None, section=None, grad_year=None, phone=''):
    """
    建立團員帳號（校友報到核准 / 幹部手動新增團員共用）：
    帳號用 email 前綴自動產生，密碼是隨機臨時密碼，並標記 must_change_password，
    強制對方第一次登入後就設定自己的新密碼（見 ForcePasswordChangeMiddleware）。
    回傳 (user, username, password, email_sent)。
    """
    username = _unique_username(email.split('@')[0])
    password = get_random_string(10)
    user = User.objects.create_user(
        username=username,
        password=password,
        name=name,
        email=email,
        role=User.Role.MEMBER,
        instrument=instrument,
        section=section,
        grad_year=grad_year,
        phone=phone,
        must_change_password=True,
    )
    email_sent = send_temp_password_email(user, username, password)
    return user, username, password, email_sent


def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    form = BootstrapAuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        next_url = request.GET.get('next', '/')
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = '/'
        return redirect(next_url)

    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('/')


@login_required
def change_password_view(request):
    """
    強制設定新密碼頁面。幹部建立團員帳號或核准校友報到後，
    User.must_change_password 會是 True，ForcePasswordChangeMiddleware
    會把使用者導來這裡，直到成功設定新密碼為止。
    """
    if request.method == 'POST':
        password1 = request.POST.get('new_password1', '')
        password2 = request.POST.get('new_password2', '')

        errors = []
        if not password1 or not password2:
            errors.append('請輸入兩次新密碼。')
        elif password1 != password2:
            errors.append('兩次輸入的密碼不一致。')
        else:
            try:
                validate_password(password1, user=request.user)
            except ValidationError as e:
                errors.extend(e.messages)

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            request.user.set_password(password1)
            request.user.must_change_password = False
            request.user.save()
            update_session_auth_hash(request, request.user)  # 避免改密碼後被登出
            messages.success(request, '密碼設定成功。')
            return redirect('/')

    return render(request, 'accounts/change_password.html')


@login_required
def profile_view(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def member_directory(request):
    # 退團／全部篩選只給幹部用，一般團員永遠只看得到在團名單
    status_filter = request.GET.get('status', '') if request.user.is_officer else ''
    query = request.GET.get('q', '').strip()

    members = User.objects.exclude(role=User.Role.ADMIN).select_related('instrument', 'section')

    if status_filter == 'inactive':
        members = members.filter(is_active=False)
    elif status_filter == 'all':
        pass
    else:
        status_filter = ''
        members = members.filter(is_active=True)

    if query:
        members = members.filter(Q(name__icontains=query) | Q(instrument__name__icontains=query))

    members = members.order_by('instrument__category', 'instrument__name', 'name')

    # 按樂器族群分類分組
    grouped = {}
    for member in members:
        category = member.instrument.get_category_display() if member.instrument else '未分類'
        grouped.setdefault(category, []).append(member)

    # 排序：木管 → 銅管 → 打擊 → 其他 → 未分類
    order = ['木管', '銅管', '打擊', '其他', '未分類']
    sorted_groups = sorted(grouped.items(), key=lambda x: order.index(x[0]) if x[0] in order else 99)

    return render(request, 'accounts/member_directory.html', {
        'grouped_members': sorted_groups,
        'query': query,
        'status_filter': status_filter,
    })


@login_required
def member_edit(request, pk):
    """幹部編輯任一團員的資料（含角色；admin 角色僅限管理員本身才能授予，避免權限升級）"""
    member = get_object_or_404(User, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    can_grant_admin = request.user.is_superuser or request.user.is_admin_role

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', member.role)
        instrument_id = request.POST.get('instrument', '')
        section_id = request.POST.get('section', '')
        grad_year = request.POST.get('grad_year', '').strip()
        phone = request.POST.get('phone', '').strip()

        errors = []
        if not name:
            errors.append('請填寫姓名。')
        if not email:
            errors.append('請填寫 Email。')
        elif User.objects.exclude(pk=member.pk).filter(email=email).exists():
            errors.append('此 Email 已被使用。')
        if role not in User.Role.values:
            errors.append('請選擇角色。')
        elif role == User.Role.ADMIN and not can_grant_admin:
            errors.append('只有管理員可以將角色設為管理員。')

        grad_year_value = None
        if grad_year:
            try:
                grad_year_value = int(grad_year)
            except ValueError:
                errors.append('畢業年份格式錯誤。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            member.name = name
            member.email = email
            member.role = role
            member.instrument = InstrumentFamily.objects.filter(pk=instrument_id).first() if instrument_id else None
            member.section = SectionType.objects.filter(pk=section_id).first() if section_id else None
            member.grad_year = grad_year_value
            member.phone = phone
            member.save()
            messages.success(request, f'已更新 {member.name} 的資料。')
            return redirect('accounts:member_directory')

    role_choices = User.Role.choices
    if not can_grant_admin:
        role_choices = [c for c in role_choices if c[0] != User.Role.ADMIN]

    form_data = request.POST if request.method == 'POST' else {
        'name': member.name,
        'email': member.email,
        'role': member.role,
        'instrument': str(member.instrument_id or ''),
        'section': str(member.section_id or ''),
        'grad_year': member.grad_year,
        'phone': member.phone,
    }

    return render(request, 'accounts/member_form.html', {
        'action': 'edit',
        'member': member,
        'form_data': form_data,
        'instruments': InstrumentFamily.objects.order_by('category', 'name'),
        'sections': SectionType.objects.all(),
        'role_choices': role_choices,
    })


@login_required
def member_deactivate(request, pk):
    """團員退團：標記 is_active=False（軟刪除），保留所有歷史紀錄"""
    member = get_object_or_404(User, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    if request.method == 'POST':
        if member.pk == request.user.pk:
            messages.error(request, '不能將自己標記為退團。')
        else:
            member.is_active = False
            member.save()
            messages.success(request, f'已將 {member.name} 標記為退團。')
    return redirect('accounts:member_directory')


@login_required
def member_reactivate(request, pk):
    """恢復退團團員的在團狀態"""
    member = get_object_or_404(User, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    if request.method == 'POST':
        member.is_active = True
        member.save()
        messages.success(request, f'已恢復 {member.name} 的在團狀態。')
    return redirect('accounts:member_directory')


@login_required
def member_delete(request, pk):
    """
    刪除團員帳號。只有完全沒有任何關聯紀錄（出席/請假/借用/財務…）的帳號才允許真的刪除，
    通常對應「剛新增就發現打錯」的情境；已經有歷史紀錄的帳號一律擋下，改請使用「退團」。
    """
    member = get_object_or_404(User, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    if request.method == 'POST':
        if member.pk == request.user.pk:
            messages.error(request, '不能刪除自己的帳號。')
        elif _user_has_related_records(member):
            messages.error(
                request,
                f'{member.name} 已有相關紀錄（出席／請假／借用／財務等），無法直接刪除，請改用「退團」。'
            )
        else:
            name = member.name
            member.delete()
            messages.success(request, f'已刪除 {name} 的帳號。')
    return redirect('accounts:member_directory')


@login_required
def member_create(request):
    """幹部手動新增團員帳號（不透過校友報到申請，例如指導老師或口頭建檔的人）"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        instrument_id = request.POST.get('instrument', '')
        section_id = request.POST.get('section', '')
        grad_year = request.POST.get('grad_year', '').strip()
        phone = request.POST.get('phone', '').strip()

        errors = []
        if not name:
            errors.append('請填寫姓名。')
        if not email:
            errors.append('請填寫 Email。')
        elif User.objects.filter(email=email).exists():
            errors.append('此 Email 已被使用。')

        grad_year_value = None
        if grad_year:
            try:
                grad_year_value = int(grad_year)
            except ValueError:
                errors.append('畢業年份格式錯誤。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            instrument = InstrumentFamily.objects.filter(pk=instrument_id).first() if instrument_id else None
            section = SectionType.objects.filter(pk=section_id).first() if section_id else None
            user, username, password, email_sent = _create_member_with_temp_password(
                name=name, email=email, instrument=instrument,
                section=section, grad_year=grad_year_value, phone=phone,
            )
            if email_sent:
                messages.success(request, f'已新增團員 {name}，帳號密碼已寄送至 {email}。')
            else:
                messages.warning(
                    request,
                    f'已新增團員 {name}，但寄信失敗，請自行告知本人：'
                    f'帳號：{username}，臨時密碼：{password}。'
                )
            return redirect('accounts:member_directory')

    return render(request, 'accounts/member_form.html', {
        'action': 'create',
        'form_data': request.POST if request.method == 'POST' else {},
        'instruments': InstrumentFamily.objects.order_by('category', 'name'),
        'sections': SectionType.objects.all(),
    })


def registration_apply(request):
    """校友報到申請（公開，不需登入）"""
    instruments = InstrumentType.objects.select_related('family').all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        instrument_id = request.POST.get('instrument', '')
        grad_year = request.POST.get('grad_year', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()

        errors = []
        if not name:
            errors.append('請填寫姓名。')
        if not instrument_id:
            errors.append('請選擇樂器。')
        if not grad_year or not grad_year.isdigit():
            errors.append('請填寫有效的畢業年份。')
        if not email:
            errors.append('請填寫 Email。')
        elif Registration.objects.filter(email=email, status=Registration.Status.PENDING).exists():
            errors.append('此 Email 已有待審核的申請，請耐心等候。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            Registration.objects.create(
                name=name,
                instrument_id=instrument_id,
                grad_year=int(grad_year),
                phone=phone,
                email=email,
            )
            messages.success(request, '申請已送出，幹部審核後會與您聯絡。')
            return redirect('accounts:registration_status')

    return render(request, 'accounts/registration_apply.html', {'instruments': instruments})


def registration_status(request):
    """申請狀態查詢（公開，用 email 查）"""
    registrations = None
    queried_email = ''

    if request.method == 'POST':
        queried_email = request.POST.get('email', '').strip()
        if queried_email:
            registrations = Registration.objects.filter(email=queried_email).order_by('-created_at')
            if not registrations.exists():
                messages.info(request, '查無此 Email 的申請紀錄。')

    return render(request, 'accounts/registration_status.html', {
        'registrations': registrations,
        'queried_email': queried_email,
    })


@login_required
def registration_review(request):
    """幹部審核／管理校友報到申請：核准、拒絕、重新開放審核"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    if request.method == 'POST':
        reg_id = request.POST.get('reg_id')
        action = request.POST.get('action')
        reg = Registration.objects.filter(pk=reg_id).first()

        if reg and action == 'approve' and reg.status == Registration.Status.PENDING:
            if User.objects.filter(email=reg.email).exists():
                messages.error(request, f'Email {reg.email} 已有帳號使用，請確認是否重複申請。')
            else:
                user, username, password, email_sent = _create_member_with_temp_password(
                    name=reg.name, email=reg.email, instrument=reg.instrument.family,
                    grad_year=reg.grad_year, phone=reg.phone,
                )
                reg.status = Registration.Status.APPROVED
                reg.reviewed_by = request.user
                reg.reviewed_at = timezone.now()
                reg.save()
                if email_sent:
                    messages.success(request, f'已核准 {reg.name} 的申請，帳號密碼已寄送至 {reg.email}。')
                else:
                    messages.warning(
                        request,
                        f'已核准 {reg.name} 的申請，但寄信失敗，請自行告知本人：'
                        f'帳號：{username}，臨時密碼：{password}。'
                    )
        elif reg and action == 'reject' and reg.status == Registration.Status.PENDING:
            reg.status = Registration.Status.REJECTED
            reg.reviewed_by = request.user
            reg.reviewed_at = timezone.now()
            reg.save()
            messages.success(request, f'已拒絕 {reg.name} 的申請。')
        elif reg and action == 'reopen' and reg.status == Registration.Status.REJECTED:
            reg.status = Registration.Status.PENDING
            reg.reviewed_by = None
            reg.reviewed_at = None
            reg.save()
            messages.success(request, f'{reg.name} 的申請已重新開放審核。')

        return redirect('accounts:registration_review')

    registrations = Registration.objects.select_related('instrument', 'reviewed_by').order_by('-created_at')

    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    if query:
        registrations = registrations.filter(Q(name__icontains=query) | Q(email__icontains=query))
    if status_filter in Registration.Status.values:
        registrations = registrations.filter(status=status_filter)

    paginator = Paginator(registrations, 30)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'accounts/registration_review.html', {
        'page_obj': page,
        'registrations': page.object_list,
        'query': query,
        'status_filter': status_filter,
        'status_choices': Registration.Status.choices,
        'pending_count': Registration.objects.filter(status=Registration.Status.PENDING).count(),
    })


@login_required
def registration_create(request):
    """幹部手動新增一筆校友報到申請紀錄（例如電話/現場口頭申請，補登進系統）"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:registration_review')

    instruments = InstrumentType.objects.select_related('family').all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        instrument_id = request.POST.get('instrument', '')
        grad_year = request.POST.get('grad_year', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()

        errors = []
        if not name:
            errors.append('請填寫姓名。')
        if not instrument_id:
            errors.append('請選擇樂器。')
        if not grad_year or not grad_year.isdigit():
            errors.append('請填寫有效的畢業年份。')
        if not email:
            errors.append('請填寫 Email。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            Registration.objects.create(
                name=name, instrument_id=instrument_id,
                grad_year=int(grad_year), phone=phone, email=email,
            )
            messages.success(request, f'已新增申請紀錄 {name}，狀態為待審核。')
            return redirect('accounts:registration_review')

    return render(request, 'accounts/registration_form.html', {
        'action': 'create',
        'instruments': instruments,
    })


@login_required
def registration_edit(request, pk):
    """幹部編輯校友報到申請的基本資料（不含審核狀態，狀態變更走核准/拒絕按鈕）"""
    reg = get_object_or_404(Registration, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:registration_review')

    instruments = InstrumentType.objects.select_related('family').all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        instrument_id = request.POST.get('instrument', '')
        grad_year = request.POST.get('grad_year', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()

        errors = []
        if not name:
            errors.append('請填寫姓名。')
        if not instrument_id:
            errors.append('請選擇樂器。')
        if not grad_year or not grad_year.isdigit():
            errors.append('請填寫有效的畢業年份。')
        if not email:
            errors.append('請填寫 Email。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            reg.name = name
            reg.instrument_id = instrument_id
            reg.grad_year = int(grad_year)
            reg.phone = phone
            reg.email = email
            reg.save()
            messages.success(request, f'已更新 {reg.name} 的申請資料。')
            return redirect('accounts:registration_review')

    return render(request, 'accounts/registration_form.html', {
        'action': 'edit',
        'registration': reg,
        'instruments': instruments,
    })


@login_required
def registration_delete(request, pk):
    """幹部刪除校友報到申請紀錄（僅限待審核／已拒絕，已核准的保留稽核軌跡）"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:registration_review')

    reg = get_object_or_404(Registration, pk=pk)
    if request.method == 'POST':
        if reg.status == Registration.Status.APPROVED:
            messages.error(request, '已核准的申請紀錄不可刪除，需保留稽核軌跡。')
        else:
            name = reg.name
            reg.delete()
            messages.success(request, f'已刪除 {name} 的申請紀錄。')
    return redirect('accounts:registration_review')
