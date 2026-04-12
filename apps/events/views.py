from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import LeaveRequest, PerformanceEvent, Rehearsal


@login_required
def event_list(request):
    upcoming = PerformanceEvent.objects.exclude(
        status=PerformanceEvent.Status.FINISHED
    ).select_related('performance_venue').order_by('performance_date')

    past = PerformanceEvent.objects.filter(
        status=PerformanceEvent.Status.FINISHED
    ).select_related('performance_venue').order_by('-performance_date')

    return render(request, 'events/event_list.html', {
        'upcoming': upcoming,
        'past': past,
    })


@login_required
def event_detail(request, pk):
    event = get_object_or_404(
        PerformanceEvent.objects.select_related('performance_venue'),
        pk=pk
    )
    rehearsals = event.rehearsals.select_related('venue').order_by('sequence')
    setlists = event.setlists.select_related('score').order_by('order')

    return render(request, 'events/event_detail.html', {
        'event': event,
        'rehearsals': rehearsals,
        'setlists': setlists,
    })


@login_required
def rehearsal_detail(request, pk):
    rehearsal = get_object_or_404(
        Rehearsal.objects.select_related('event', 'venue', 'summary_by'),
        pk=pk
    )
    return render(request, 'events/rehearsal_detail.html', {
        'rehearsal': rehearsal,
    })


@login_required
def leave_request_create(request, rehearsal_pk):
    rehearsal = get_object_or_404(Rehearsal.objects.select_related('event'), pk=rehearsal_pk)
    existing = LeaveRequest.objects.filter(member=request.user, rehearsal=rehearsal).first()

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, '請填寫請假原因。')
        elif existing:
            messages.error(request, '您已提交過此次排練的請假申請。')
        else:
            LeaveRequest.objects.create(
                member=request.user,
                rehearsal=rehearsal,
                reason=reason,
            )
            messages.success(request, '請假申請已送出。')
            return redirect('events:my_leave_requests')

    return render(request, 'events/leave_request_form.html', {
        'rehearsal': rehearsal,
        'existing': existing,
    })


@login_required
def my_leave_requests(request):
    leaves = (
        LeaveRequest.objects
        .filter(member=request.user)
        .select_related('rehearsal__event', 'reviewed_by')
        .order_by('-rehearsal__date')
    )
    return render(request, 'events/my_leave_requests.html', {'leaves': leaves})


@login_required
def leave_review_list(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('events:event_list')

    if request.method == 'POST':
        leave_id = request.POST.get('leave_id')
        action = request.POST.get('action')
        leave = get_object_or_404(LeaveRequest, pk=leave_id)
        if action == 'approve':
            leave.status = LeaveRequest.Status.APPROVED
            leave.reviewed_by = request.user
            leave.reviewed_at = timezone.now()
            leave.save()
            messages.success(request, f'已核准 {leave.member.name} 的請假申請。')
        elif action == 'reject':
            leave.status = LeaveRequest.Status.REJECTED
            leave.reviewed_by = request.user
            leave.reviewed_at = timezone.now()
            leave.save()
            messages.success(request, f'已拒絕 {leave.member.name} 的請假申請。')
        return redirect('events:leave_review_list')

    pending = (
        LeaveRequest.objects
        .filter(status=LeaveRequest.Status.PENDING)
        .select_related('member', 'rehearsal__event')
        .order_by('rehearsal__date')
    )
    reviewed = (
        LeaveRequest.objects
        .exclude(status=LeaveRequest.Status.PENDING)
        .select_related('member', 'rehearsal__event', 'reviewed_by')
        .order_by('-reviewed_at')[:50]
    )
    return render(request, 'events/leave_review_list.html', {
        'pending': pending,
        'reviewed': reviewed,
    })
