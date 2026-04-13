from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import AssetBorrow


@login_required
def borrow_status_report(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('/')

    today = timezone.localdate()

    active_borrows = (
        AssetBorrow.objects
        .filter(returned_at__isnull=True)
        .select_related('asset', 'borrower')
        .order_by('due_date', 'asset__category', 'asset__name')
    )

    # 標記逾期
    rows = []
    for borrow in active_borrows:
        overdue = borrow.due_date is not None and borrow.due_date < today
        rows.append({'borrow': borrow, 'overdue': overdue})

    overdue_count = sum(1 for r in rows if r['overdue'])

    return render(request, 'assets/borrow_status_report.html', {
        'rows': rows,
        'overdue_count': overdue_count,
        'today': today,
    })
