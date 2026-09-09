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
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import BootstrapAuthenticationForm, ProfileForm
from .imports import ImportError_, normalize_instrument, parse_csv, parse_date
from .models import (
    InstrumentFamily, InstrumentType, Registration, SectionType, User,
    validate_national_id,
)
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


# 2026-08-29（#13-1）必填改為：姓名／Email／出生年月日／住址／手機／LINE ID／身分證字號；
# 樂器、聲部、畢業年份改為選填。
#
# 這組規則有四個入口會用到（校友自行申請、幹部補登申請、幹部編輯申請、幹部建團員帳號），
# 各寫一份必然會隨時間走鐘，故集中在這裡。**必填只在表單層把關，model 一律可空**——
# 既有團員這些欄位是空的，model 設 null=False 會讓 migrate 直接卡在既有資料上（#13-1 決定三）。
_REQUIRED_PROFILE_FIELDS = (
    ('name', '姓名'),
    ('email', 'Email'),
    ('address', '住址'),
    ('phone', '手機'),
    ('line_id', 'LINE ID'),
    ('national_id', '身分證字號／居留證號'),
)


def _parse_profile_fields(post, *, require_national_id=True):
    """解析並驗證個人資料欄位，回傳 (data, errors)。

    data 只含純量欄位；樂器／聲部的 FK 查詢由各 view 自己做——申請單指向具體樂器
    (InstrumentType)、團員帳號指向樂器族群 (InstrumentFamily)，兩者不同層級。
    """
    data = {
        'name': post.get('name', '').strip(),
        'email': post.get('email', '').strip(),
        'address': post.get('address', '').strip(),
        'phone': post.get('phone', '').strip(),
        'line_id': post.get('line_id', '').strip(),
        # 身分證字號一律轉大寫再存，避免同一個號碼因大小寫不同被當成兩筆
        'national_id': post.get('national_id', '').strip().upper(),
        # 入學年／科系原文照存，不自動拆成 grad_year（見 models.Registration.alumni_info）
        'alumni_info': post.get('alumni_info', '').strip(),
        'birth_date': None,
        'grad_year': None,
    }
    # 幹部端把證號排除在必填之外：團裡有既無身分證、也無居留證的境外團員，
    # 公開申請頁擋的是隨手亂填、幹部端擋的是本來就不存在的東西，兩者需求不同。
    required = _REQUIRED_PROFILE_FIELDS
    if not require_national_id:
        required = tuple(f for f in required if f[0] != 'national_id')
    errors = [f'請填寫{label}。' for field, label in required if not data[field]]

    if data['national_id']:
        try:
            validate_national_id(data['national_id'])
        except ValidationError as exc:
            errors.append(exc.messages[0])

    birth_date = post.get('birth_date', '').strip()
    if not birth_date:
        errors.append('請填寫出生年月日。')
    else:
        data['birth_date'] = parse_date(birth_date)
        if data['birth_date'] is None:
            errors.append('出生年月日格式錯誤（請用 YYYY-MM-DD）。')

    grad_year = post.get('grad_year', '').strip()
    if grad_year:
        if grad_year.isdigit():
            data['grad_year'] = int(grad_year)
        else:
            errors.append('畢業年份格式錯誤。')

    return data, errors


def _create_member_with_temp_password(
    *, name, email, instrument=None, section=None, grad_year=None, phone='',
    birth_date=None, address='', national_id='', line_id='', alumni_info='',
):
    """
    建立團員帳號（入團申請核准 / 幹部手動新增團員共用）：
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
        birth_date=birth_date,
        address=address,
        national_id=national_id,
        line_id=line_id,
        alumni_info=alumni_info,
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
    強制設定新密碼頁面。幹部建立團員帳號或核准入團申請後，
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

    members = User.objects.exclude(role__in=[User.Role.ADMIN, User.Role.GUEST]).select_related('instrument', 'section')

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
def member_directory_report(request):
    """
    團員通訊錄列印報表（幹部限定）。

    比照排練出席、財產借用、會費繳納、請假統計都已有的列印報表：套用 @media print 樣式、
    附報表日期與列印按鈕。含電話／Email，故限幹部；分組邏輯與通訊錄頁一致（依樂器族群分類）。
    沿用通訊錄的 status 參數（在團／已退團／全部），預設只印在團名單。
    """
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    status_filter = request.GET.get('status', '')
    members = User.objects.exclude(role__in=[User.Role.ADMIN, User.Role.GUEST]).select_related('instrument', 'section')

    if status_filter == 'inactive':
        members = members.filter(is_active=False)
    elif status_filter == 'all':
        pass
    else:
        status_filter = ''
        members = members.filter(is_active=True)

    members = members.order_by('instrument__category', 'instrument__name', 'name')

    # 依樂器族群分類分組（與 member_directory 相同：木管 → 銅管 → 打擊 → 其他 → 未分類）
    grouped = {}
    for member in members:
        category = member.instrument.get_category_display() if member.instrument else '未分類'
        grouped.setdefault(category, []).append(member)
    order = ['木管', '銅管', '打擊', '其他', '未分類']
    grouped_members = sorted(grouped.items(), key=lambda x: order.index(x[0]) if x[0] in order else 99)
    total = sum(len(m) for _, m in grouped_members)

    return render(request, 'accounts/member_directory_report.html', {
        'grouped_members': grouped_members,
        'status_filter': status_filter,
        'total': total,
        'today': timezone.localdate(),
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
        data, errors = _parse_profile_fields(request.POST, require_national_id=False)
        role = request.POST.get('role', member.role)

        if data['email'] and User.objects.exclude(pk=member.pk).filter(email=data['email']).exists():
            errors.append('此 Email 已被使用。')
        if role not in User.Role.values:
            errors.append('請選擇角色。')
        elif role == User.Role.ADMIN and not can_grant_admin:
            errors.append('只有管理員可以將角色設為管理員。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            instrument_id = request.POST.get('instrument', '')
            section_id = request.POST.get('section', '')
            for field, value in data.items():
                setattr(member, field, value)
            member.role = role
            member.instrument = InstrumentFamily.objects.filter(pk=instrument_id).first() if instrument_id else None
            member.section = SectionType.objects.filter(pk=section_id).first() if section_id else None
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
        'grad_year': member.grad_year or '',
        'phone': member.phone,
        'address': member.address,
        'line_id': member.line_id,
        'national_id': member.national_id,
        'alumni_info': member.alumni_info,
        'birth_date': member.birth_date.isoformat() if member.birth_date else '',
    }

    return render(request, 'accounts/member_form.html', {
        'action': 'edit',
        'member': member,
        'form_data': form_data,
        'national_id_optional': True,   # 幹部端：既無身分證也無居留證的境外團員可留空
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
    刪除團員帳號。一般幹部只有完全沒有任何關聯紀錄（出席/請假/借用/財務…）的帳號才允許真的刪除，
    通常對應「剛新增就發現打錯」的情境；已經有歷史紀錄的帳號一律擋下，改請使用「退團」。
    管理員（admin 角色或 superuser）可以強制刪除，跳過關聯紀錄檢查，方便清除測試/除錯帳號；
    但 PROTECT 關聯（如發過公告）仍是資料庫層級的硬限制，管理員也無法繞過，只能先處理該筆關聯資料。
    """
    member = get_object_or_404(User, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    can_force_delete = request.user.is_superuser or request.user.is_admin_role

    if request.method == 'POST':
        if member.pk == request.user.pk:
            messages.error(request, '不能刪除自己的帳號。')
        elif not can_force_delete and _user_has_related_records(member):
            messages.error(
                request,
                f'{member.name} 已有相關紀錄（出席／請假／借用／財務等），無法直接刪除，請改用「退團」。'
            )
        else:
            name = member.name
            try:
                member.delete()
                messages.success(request, f'已刪除 {name} 的帳號。')
            except ProtectedError:
                messages.error(
                    request,
                    f'{name} 有無法自動處理的關聯資料（如發布過的公告），請先於 Django Admin 處理該筆資料後再刪除。'
                )
    return redirect('accounts:member_directory')


@login_required
def member_create(request):
    """幹部手動新增團員帳號（不透過入團申請，例如指導老師或口頭建檔的人）"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    if request.method == 'POST':
        data, errors = _parse_profile_fields(request.POST, require_national_id=False)
        if data['email'] and User.objects.filter(email=data['email']).exists():
            errors.append('此 Email 已被使用。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            instrument_id = request.POST.get('instrument', '')
            section_id = request.POST.get('section', '')
            user, username, password, email_sent = _create_member_with_temp_password(
                instrument=InstrumentFamily.objects.filter(pk=instrument_id).first() if instrument_id else None,
                section=SectionType.objects.filter(pk=section_id).first() if section_id else None,
                **data,
            )
            if email_sent:
                messages.success(request, f'已新增團員 {data["name"]}，帳號密碼已寄送至 {data["email"]}。')
            else:
                messages.warning(
                    request,
                    f'已新增團員 {data["name"]}，但寄信失敗，請自行告知本人：'
                    f'帳號：{username}，臨時密碼：{password}。'
                )
            return redirect('accounts:member_directory')

    return render(request, 'accounts/member_form.html', {
        'action': 'create',
        'form_data': request.POST if request.method == 'POST' else {},
        'national_id_optional': True,   # 幹部端：既無身分證也無居留證的境外團員可留空
        'instruments': InstrumentFamily.objects.order_by('category', 'name'),
        'sections': SectionType.objects.all(),
    })


# ── 客座團員（槍手）管理 ──────────────────────────────────────────
# 槍手是 role=GUEST 的 User（純名冊人物、set_unusable_password 不可登入），與正式團員同一張人員表，
# 但另用獨立頁管理，讓通訊錄維持只含正式團員（見 DESIGN 附錄五 §5）。


@login_required
def guest_list(request):
    """客座團員（槍手）管理列表，幹部限定。"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('/')

    query = request.GET.get('q', '').strip()
    guests = User.objects.filter(role=User.Role.GUEST).select_related('instrument', 'section')
    if query:
        guests = guests.filter(Q(name__icontains=query) | Q(from_band__icontains=query))
    guests = guests.order_by('instrument__category', 'instrument__name', 'name')

    return render(request, 'accounts/guest_list.html', {
        'guests': guests,
        'query': query,
    })


def _apply_guest_form(request, guest):
    """把 POST 資料寫進槍手 User 實例（新建或既有皆可），回傳 errors 清單。email 空白存 NULL。"""
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    instrument_id = request.POST.get('instrument', '')
    section_id = request.POST.get('section', '')
    from_band = request.POST.get('from_band', '').strip()
    phone = request.POST.get('phone', '').strip()

    errors = []
    if not name:
        errors.append('請填寫姓名。')
    if email and User.objects.exclude(pk=guest.pk).filter(email=email).exists():
        errors.append('此 Email 已被使用。')

    if not errors:
        guest.name = name
        guest.email = email or None  # 空字串要存 NULL，否則多個槍手的 '' 會違反 unique
        guest.instrument = InstrumentFamily.objects.filter(pk=instrument_id).first() if instrument_id else None
        guest.section = SectionType.objects.filter(pk=section_id).first() if section_id else None
        guest.from_band = from_band
        guest.phone = phone
    return errors


def _guest_form_context(action, guest=None, form_data=None):
    return {
        'action': action,
        'guest': guest,
        'form_data': form_data if form_data is not None else {},
        'instruments': InstrumentFamily.objects.order_by('category', 'name'),
        'sections': SectionType.objects.all(),
    }


@login_required
def guest_create(request):
    """新增槍手：set_unusable_password 不可登入、不寄帳密信、role=GUEST、is_active=True。"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:guest_list')

    if request.method == 'POST':
        guest = User(
            role=User.Role.GUEST,
            is_active=True,
            must_change_password=False,
        )
        errors = _apply_guest_form(request, guest)
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'accounts/guest_form.html',
                          _guest_form_context('create', form_data=request.POST))
        guest.username = _unique_username(guest.name or 'guest')
        guest.set_unusable_password()  # 關鍵：槍手不可登入系統
        guest.save()
        messages.success(request, f'已新增槍手 {guest.name}。')
        return redirect('accounts:guest_list')

    return render(request, 'accounts/guest_form.html', _guest_form_context('create'))


@login_required
def guest_edit(request, pk):
    """編輯槍手基本資料（幹部限定）。"""
    guest = get_object_or_404(User, pk=pk, role=User.Role.GUEST)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:guest_list')

    if request.method == 'POST':
        errors = _apply_guest_form(request, guest)
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'accounts/guest_form.html',
                          _guest_form_context('edit', guest=guest, form_data=request.POST))
        guest.save()
        messages.success(request, f'已更新槍手 {guest.name} 的資料。')
        return redirect('accounts:guest_list')

    form_data = {
        'name': guest.name,
        'email': guest.email or '',
        'instrument': str(guest.instrument_id or ''),
        'section': str(guest.section_id or ''),
        'from_band': guest.from_band,
        'phone': guest.phone,
    }
    return render(request, 'accounts/guest_form.html',
                  _guest_form_context('edit', guest=guest, form_data=form_data))


@login_required
def guest_promote(request, pk):
    """
    槍手轉正為正式團員：role guest→member、補 email、發臨時密碼並開通登入
    （複用「臨時密碼 + 強制改密碼」機制）。過去的分譜分配/出席都指向同一 User pk，履歷天然接上。
    """
    guest = get_object_or_404(User, pk=pk, role=User.Role.GUEST)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:guest_list')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        errors = []
        if not email:
            errors.append('轉正需要 Email（用於寄送登入帳密）。')
        elif User.objects.exclude(pk=guest.pk).filter(email=email).exists():
            errors.append('此 Email 已被使用。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            password = get_random_string(10)
            guest.role = User.Role.MEMBER
            guest.email = email
            guest.set_password(password)
            guest.must_change_password = True
            guest.save()
            email_sent = send_temp_password_email(guest, guest.username, password)
            if email_sent:
                messages.success(request, f'已將 {guest.name} 轉為正式團員，帳密已寄送至 {email}。')
            else:
                messages.warning(
                    request,
                    f'已將 {guest.name} 轉為正式團員，但寄信失敗，請自行告知本人：'
                    f'帳號：{guest.username}，臨時密碼：{password}。'
                )
            return redirect('accounts:member_directory')

    return render(request, 'accounts/guest_promote.html', {'guest': guest})


@login_required
def guest_delete(request, pk):
    """刪除槍手：比照 member_delete——無關聯可刪、有關聯擋下（管理員可強制）。"""
    guest = get_object_or_404(User, pk=pk, role=User.Role.GUEST)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:guest_list')

    can_force_delete = request.user.is_superuser or request.user.is_admin_role

    if request.method == 'POST':
        if not can_force_delete and _user_has_related_records(guest):
            messages.error(
                request,
                f'{guest.name} 已有相關紀錄（分譜分配／出席等），無法直接刪除。'
            )
        else:
            name = guest.name
            try:
                guest.delete()
                messages.success(request, f'已刪除槍手 {name}。')
            except ProtectedError:
                messages.error(
                    request,
                    f'{name} 有無法自動處理的關聯資料，請先於 Django Admin 處理後再刪除。'
                )
    return redirect('accounts:guest_list')


def _registration_form_context(request, *, action=None, registration=None):
    """報到申請三個入口（公開申請／幹部補登／幹部編輯）共用的 template context。

    表單重繪時以 POST 內容回填，避免使用者填了七個欄位卻因一個錯誤全部清空。
    """
    if request.method == 'POST':
        form_data = request.POST
    elif registration is not None:
        form_data = {
            'name': registration.name,
            'email': registration.email,
            'phone': registration.phone,
            'address': registration.address,
            'line_id': registration.line_id,
            'national_id': registration.national_id,
            'alumni_info': registration.alumni_info,
            'birth_date': registration.birth_date.isoformat() if registration.birth_date else '',
            'grad_year': registration.grad_year or '',
            'instrument': str(registration.instrument_id or ''),
            'section': str(registration.section_id or ''),
        }
    else:
        form_data = {}

    return {
        'action': action,
        'registration': registration,
        'form_data': form_data,
        # 公開申請頁維持必填，幹部端（補登／編輯）允許留空
        'national_id_optional': action is not None,
        # 樂器下拉列「族群」而非細項——表單填的是粗分類（見 models.Registration.instrument）
        'instruments': InstrumentFamily.objects.order_by('category', 'name'),
        'sections': SectionType.objects.all(),
    }


def registration_apply(request):
    """入團申請（公開，不需登入）"""
    if request.method == 'POST':
        data, errors = _parse_profile_fields(request.POST)
        if data['email'] and Registration.objects.filter(
            email=data['email'], status=Registration.Status.PENDING
        ).exists():
            errors.append('此 Email 已有待審核的申請，請耐心等候。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            Registration.objects.create(
                instrument_id=request.POST.get('instrument') or None,
                section_id=request.POST.get('section') or None,
                **data,
            )
            messages.success(request, '申請已送出，幹部審核後會與您聯絡。')
            return redirect('accounts:registration_status')

    return render(request, 'accounts/registration_apply.html', _registration_form_context(request))


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


def _approve_registration(reg, reviewer):
    """核准一筆申請並建立帳號，回傳 (成功?, 說明)。單筆與批次共用同一套規則。"""
    if reg.status != Registration.Status.PENDING:
        return False, '狀態不是待審核'
    if not reg.email:
        return False, '沒有 Email，無法建立帳號'
    if User.objects.filter(email=reg.email).exists():
        return False, f'{reg.email} 已有帳號'

    _, username, password, email_sent = _create_member_with_temp_password(
        name=reg.name, email=reg.email,
        instrument=reg.instrument, section=reg.section,
        grad_year=reg.grad_year, phone=reg.phone,
        birth_date=reg.birth_date, address=reg.address,
        national_id=reg.national_id, line_id=reg.line_id,
        alumni_info=reg.alumni_info,
    )
    reg.status = Registration.Status.APPROVED
    reg.reviewed_by = reviewer
    reg.reviewed_at = timezone.now()
    reg.save()
    if email_sent:
        return True, ''
    # 寄信失敗不讓核准失敗——帳號已經建好了，退回顯示帳密讓幹部自行轉達
    return True, f'寄信失敗，帳號：{username}，臨時密碼：{password}'


def _bulk_approve_registrations(request):
    """批次核准勾選的申請（#11）。

    **一筆失敗不影響其他筆**：300 筆裡有幾筆 Email 撞號是常態，
    整批 rollback 只會讓幹部無從下手。失敗的逐筆列出原因，成功的照常建帳號。
    """
    ids = request.POST.getlist('reg_ids')
    if not ids:
        messages.error(request, '請先勾選要核准的申請。')
        return redirect('accounts:registration_review')

    approved, failed, mail_failures = 0, [], []
    for reg in Registration.objects.filter(pk__in=ids, status=Registration.Status.PENDING):
        ok, note = _approve_registration(reg, request.user)
        if not ok:
            failed.append(f'{reg.name}（{note}）')
        else:
            approved += 1
            if note:
                mail_failures.append(f'{reg.name} — {note}')

    if approved:
        messages.success(request, f'已核准 {approved} 筆，帳號密碼已寄出。')
    if mail_failures:
        messages.warning(
            request,
            '以下帳號建立成功但寄信失敗，請自行告知本人：' + '；'.join(mail_failures)
        )
    if failed:
        messages.error(request, '以下未能核准：' + '；'.join(failed))
    return redirect('accounts:registration_review')


@login_required
def registration_review(request):
    """幹部審核／管理入團申請：核准、拒絕、重新開放審核"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    if request.method == 'POST':
        reg_id = request.POST.get('reg_id')
        action = request.POST.get('action')

        # 批次核准（#11）：勾選多筆一次處理。逐筆結果彙整成一則訊息，
        # 不是每筆各噴一條——300 筆會把畫面洗掉。
        if action == 'bulk_approve':
            return _bulk_approve_registrations(request)

        reg = Registration.objects.filter(pk=reg_id).first()

        if reg and action == 'approve' and reg.status == Registration.Status.PENDING:
            if User.objects.filter(email=reg.email).exists():
                messages.error(request, f'Email {reg.email} 已有帳號使用，請確認是否重複申請。')
            else:
                user, username, password, email_sent = _create_member_with_temp_password(
                    name=reg.name, email=reg.email,
                    # 申請單與帳號都存樂器族群 (InstrumentFamily)，同一層直接帶過去
                    instrument=reg.instrument,
                    section=reg.section,
                    grad_year=reg.grad_year, phone=reg.phone,
                    birth_date=reg.birth_date, address=reg.address,
                    national_id=reg.national_id, line_id=reg.line_id,
                    alumni_info=reg.alumni_info,
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
def registration_import(request):
    """CSV 批次匯入報到申請（#11）。

    **匯入目標是 Registration 而非直接建 User**：DESIGN §4.2 訂了「Registration 是這個帳號
    怎麼來的唯一紀錄」，直接建 User 會讓這批帳號沒有來源、破壞稽核原則。代價是多一道核准，
    用批次核准解決。

    **一步匯入 ＋ 詳細報告，不做預覽確認制**：預覽要在兩個 request 之間保存解析結果，
    而那裡面有身分證字號——存進 session 就是明文落在 django_session 表，
    直接抵銷掉欄位加密（#13-1 決定二）。改用「錯誤列不寫入 ＋ 以 Email 冪等」達到同樣效果：
    幹部照報告修好 CSV 重傳，不會產生重複。

    **有問題的列一律列出來、不靜默略過**（DESIGN #11 風險表要求）。
    """
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:registration_review')

    result = None
    if request.method == 'POST' and request.FILES.get('csv_file'):
        upload = request.FILES['csv_file']
        if upload.size > 5 * 1024 * 1024:
            messages.error(request, '檔案過大（上限 5 MB）。')
        else:
            try:
                rows, _ = parse_csv(upload.read())
            except ImportError_ as exc:
                messages.error(request, str(exc))
            else:
                result = _import_registration_rows(rows)
                messages.success(
                    request,
                    f'匯入完成：新增 {len(result["created"])} 筆、'
                    f'略過 {len(result["skipped"])} 筆。'
                )

    return render(request, 'accounts/registration_import.html', {'result': result})


def _import_registration_rows(rows):
    """把解析後的列寫進 Registration，回傳 {'created': [...], 'skipped': [...]}。

    略過的原因逐列記下來給幹部處理——「哪幾筆沒進去、為什麼」是這個功能最重要的輸出，
    比「成功幾筆」更需要看得清楚。
    """
    families = {f.name: f for f in InstrumentFamily.objects.all()}
    existing_user_emails = set(
        User.objects.exclude(email=None).values_list('email', flat=True)
    )

    created, skipped = [], []
    seen_emails = set()

    for line_no, row in enumerate(rows, start=2):     # 第 1 列是標題
        name = row.get('name', '')
        email = row.get('email', '')
        label = name or f'第 {line_no} 列'

        # 沒有 Email 就產不出 username、也寄不出臨時密碼，整條鏈路斷在這裡。
        # 這是實際回覆裡最常見的缺漏（Email 那題是後來才加的），所以訊息要講清楚怎麼補。
        if not email:
            skipped.append((label, '缺 Email——無法建立帳號，請向本人補齊後重新匯入'))
            continue
        if not name:
            skipped.append((f'第 {line_no} 列', '缺姓名'))
            continue
        if email in seen_emails:
            skipped.append((label, f'同一份檔案裡 Email 重複（{email}）'))
            continue
        seen_emails.add(email)
        if email in existing_user_emails:
            skipped.append((label, f'{email} 已有系統帳號'))
            continue
        if Registration.objects.filter(email=email).exists():
            skipped.append((label, f'{email} 已有申請紀錄（重複匯入會跳過）'))
            continue

        # 樂器對不上就留空給幹部指定，不猜——但要讓幹部知道有這件事
        instrument_name = normalize_instrument(row.get('instrument', ''))
        instrument = families.get(instrument_name)
        notes = []
        if instrument_name and instrument is None:
            notes.append(f'樂器「{row.get("instrument")}」對不上系統樂器族群，已留空')

        birth_date = parse_date(row.get('birth_date', ''))
        if row.get('birth_date') and birth_date is None:
            notes.append(f'出生年月日「{row.get("birth_date")}」格式無法辨識，已留空')

        Registration.objects.create(
            name=name,
            email=email,
            phone=row.get('phone', ''),
            address=row.get('address', ''),
            line_id=row.get('line_id', ''),
            national_id=row.get('national_id', '').strip().upper(),
            alumni_info=row.get('alumni_info', ''),
            birth_date=birth_date,
            instrument=instrument,
        )
        created.append((label, '；'.join(notes)))

    return {'created': created, 'skipped': skipped}


@login_required
def registration_create(request):
    """幹部手動新增一筆入團申請紀錄（例如電話/現場口頭申請，補登進系統）"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:registration_review')

    if request.method == 'POST':
        data, errors = _parse_profile_fields(request.POST, require_national_id=False)
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            Registration.objects.create(
                instrument_id=request.POST.get('instrument') or None,
                section_id=request.POST.get('section') or None,
                **data,
            )
            messages.success(request, f'已新增申請紀錄 {data["name"]}，狀態為待審核。')
            return redirect('accounts:registration_review')

    return render(request, 'accounts/registration_form.html',
                  _registration_form_context(request, action='create'))


@login_required
def registration_edit(request, pk):
    """幹部編輯入團申請的基本資料（不含審核狀態，狀態變更走核准/拒絕按鈕）"""
    reg = get_object_or_404(Registration, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:registration_review')

    if request.method == 'POST':
        data, errors = _parse_profile_fields(request.POST, require_national_id=False)
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            for field, value in data.items():
                setattr(reg, field, value)
            reg.instrument_id = request.POST.get('instrument') or None
            reg.section_id = request.POST.get('section') or None
            reg.save()
            messages.success(request, f'已更新 {reg.name} 的申請資料。')
            return redirect('accounts:registration_review')

    return render(request, 'accounts/registration_form.html',
                  _registration_form_context(request, action='edit', registration=reg))


@login_required
def registration_delete(request, pk):
    """幹部刪除入團申請紀錄（僅限待審核／已拒絕，已核准的保留稽核軌跡）"""
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
