from itertools import groupby

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import BootstrapAuthenticationForm, ProfileForm
from .models import InstrumentType, User


def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    form = BootstrapAuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get('next', '/'))

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
