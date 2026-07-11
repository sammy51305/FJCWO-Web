import re
from itertools import groupby

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
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
    members = (
        User.objects
        .filter(is_active=True)
        .exclude(role=User.Role.ADMIN)
        .select_related('instrument', 'section')
        .order_by('instrument__category', 'instrument__name', 'name')
    )

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
    })


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
    """幹部審核校友報到申請"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('accounts:member_directory')

    if request.method == 'POST':
        reg_id = request.POST.get('reg_id')
        action = request.POST.get('action')
        reg = Registration.objects.filter(pk=reg_id).first()
        if reg and reg.status == Registration.Status.PENDING:
            if action == 'approve':
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
            elif action == 'reject':
                reg.status = Registration.Status.REJECTED
                reg.reviewed_by = request.user
                reg.reviewed_at = timezone.now()
                reg.save()
                messages.success(request, f'已拒絕 {reg.name} 的申請。')
        return redirect('accounts:registration_review')

    pending = Registration.objects.filter(status=Registration.Status.PENDING).select_related('instrument')
    reviewed = Registration.objects.exclude(status=Registration.Status.PENDING).select_related('instrument', 'reviewed_by').order_by('-reviewed_at')[:50]

    return render(request, 'accounts/registration_review.html', {
        'pending': pending,
        'reviewed': reviewed,
    })
