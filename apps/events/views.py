import base64
import io

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (
    LeaveRequest, PerformanceEvent, Rehearsal,
    RehearsalAttendance, RehearsalQRToken,
)


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


def _make_qr_data_url(url):
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    data = base64.b64encode(buf.getvalue()).decode()
    return f'data:image/png;base64,{data}'


@login_required
def qr_manage(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('events:event_list')

    rehearsal = get_object_or_404(Rehearsal.objects.select_related('event', 'venue'), pk=pk)
    qr_token = getattr(rehearsal, 'qr_token', None)

    qr_image = None
    if qr_token:
        checkin_url = request.build_absolute_uri(f'/events/checkin/{qr_token.token}/')
        qr_image = _make_qr_data_url(checkin_url)

    attendances = (
        RehearsalAttendance.objects
        .filter(rehearsal=rehearsal)
        .select_related('member')
        .order_by('member__name')
    )

    return render(request, 'events/qr_manage.html', {
        'rehearsal': rehearsal,
        'qr_token': qr_token,
        'qr_image': qr_image,
        'attendances': attendances,
    })


@login_required
def qr_generate(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('events:event_list')

    if request.method != 'POST':
        return redirect('events:qr_manage', pk=pk)

    rehearsal = get_object_or_404(Rehearsal, pk=pk)
    hours = int(request.POST.get('hours', 4))
    expires_at = timezone.now() + timezone.timedelta(hours=hours)

    qr_token, created = RehearsalQRToken.objects.get_or_create(
        rehearsal=rehearsal,
        defaults={'expires_at': expires_at, 'is_active': True},
    )
    if not created:
        import uuid
        qr_token.token = uuid.uuid4()
        qr_token.expires_at = expires_at
        qr_token.is_active = True
        qr_token.save()

    action = '已產生' if created else '已重新產生'
    messages.success(request, f'QR Code {action}，有效期限 {hours} 小時。')
    return redirect('events:qr_manage', pk=pk)


@login_required
def qr_toggle(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('events:event_list')

    if request.method != 'POST':
        return redirect('events:qr_manage', pk=pk)

    rehearsal = get_object_or_404(Rehearsal, pk=pk)
    qr_token = get_object_or_404(RehearsalQRToken, rehearsal=rehearsal)
    qr_token.is_active = not qr_token.is_active
    qr_token.save()
    state = '啟用' if qr_token.is_active else '停用'
    messages.success(request, f'QR Code 已{state}。')
    return redirect('events:qr_manage', pk=pk)


@login_required
def qr_checkin(request, token):
    qr_token = get_object_or_404(RehearsalQRToken.objects.select_related('rehearsal__event', 'rehearsal__venue'), token=token)
    rehearsal = qr_token.rehearsal

    existing = RehearsalAttendance.objects.filter(
        rehearsal=rehearsal, member=request.user
    ).first()

    already_checked_in = (
        existing and existing.status == RehearsalAttendance.Status.PRESENT
    )

    return render(request, 'events/qr_checkin.html', {
        'qr_token': qr_token,
        'rehearsal': rehearsal,
        'is_valid': qr_token.is_valid(),
        'already_checked_in': already_checked_in,
        'existing': existing,
    })


@login_required
def qr_checkin_confirm(request, token):
    if request.method != 'POST':
        return redirect('events:qr_checkin', token=token)

    qr_token = get_object_or_404(RehearsalQRToken, token=token)

    if not qr_token.is_valid():
        messages.error(request, 'QR Code 已失效或過期，無法簽到。')
        return redirect('events:qr_checkin', token=token)

    attendance, _ = RehearsalAttendance.objects.get_or_create(
        rehearsal=qr_token.rehearsal,
        member=request.user,
    )
    if attendance.status == RehearsalAttendance.Status.PRESENT:
        messages.info(request, '您已完成簽到。')
    else:
        attendance.status = RehearsalAttendance.Status.PRESENT
        attendance.checked_in_at = timezone.now()
        attendance.save()
        messages.success(request, '簽到成功！')

    return redirect('events:qr_checkin', token=token)
