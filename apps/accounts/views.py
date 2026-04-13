from itertools import groupby

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import BootstrapAuthenticationForm, ProfileForm
from .models import InstrumentType, Registration, User


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

    # 按樂器分類分組
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


def registration_apply(request):
    """校友報到申請（公開，不需登入）"""
    instruments = InstrumentType.objects.all()

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
            if action in ('approve', 'reject'):
                reg.status = Registration.Status.APPROVED if action == 'approve' else Registration.Status.REJECTED
                reg.reviewed_by = request.user
                reg.reviewed_at = timezone.now()
                reg.save()
                label = '核准' if action == 'approve' else '拒絕'
                messages.success(request, f'已{label} {reg.name} 的申請。')
        return redirect('accounts:registration_review')

    pending = Registration.objects.filter(status=Registration.Status.PENDING).select_related('instrument')
    reviewed = Registration.objects.exclude(status=Registration.Status.PENDING).select_related('instrument', 'reviewed_by').order_by('-reviewed_at')[:50]

    return render(request, 'accounts/registration_review.html', {
        'pending': pending,
        'reviewed': reviewed,
    })
