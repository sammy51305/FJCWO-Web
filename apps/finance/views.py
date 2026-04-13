from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.accounts.models import User

from .models import MembershipFee


@login_required
def membership_fee_report(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('/')

    # 取得所有已建立的期別，從新到舊排序
    periods = (
        MembershipFee.objects
        .values_list('period', flat=True)
        .distinct()
        .order_by('-period')
    )

    selected_period = request.GET.get('period', '')
    if not selected_period and periods:
        selected_period = periods[0]

    rows = []
    paid_count = unpaid_count = no_record_count = 0

    if selected_period:
        members = (
            User.objects.filter(is_active=True)
            .exclude(role=User.Role.ADMIN)
            .select_related('instrument')
            .order_by('instrument__category', 'instrument__name', 'name')
        )
        fee_map = {
            f.member_id: f
            for f in MembershipFee.objects.filter(period=selected_period).select_related('collected_by')
        }
        for member in members:
            fee = fee_map.get(member.pk)
            if fee is None:
                status = 'no_record'
                no_record_count += 1
            elif fee.is_paid:
                status = 'paid'
                paid_count += 1
            else:
                status = 'unpaid'
                unpaid_count += 1
            rows.append({'member': member, 'fee': fee, 'status': status})

    return render(request, 'finance/membership_fee_report.html', {
        'periods': periods,
        'selected_period': selected_period,
        'rows': rows,
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
        'no_record_count': no_record_count,
    })
