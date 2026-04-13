import base64
import io
import uuid

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.scores.models import Score

from apps.accounts.models import User

from .models import (
    LeaveRequest, PerformanceEvent, Rehearsal,
    RehearsalAttendance, RehearsalQRToken, Setlist,
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
        'now': timezone.now(),
    })


@login_required
def leave_request_create(request, rehearsal_pk):
    rehearsal = get_object_or_404(Rehearsal.objects.select_related('event'), pk=rehearsal_pk)
    existing = LeaveRequest.objects.filter(member=request.user, rehearsal=rehearsal).first()

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if rehearsal.date <= timezone.now():
            messages.error(request, '排練已結束，無法申請請假。')
        elif not reason:
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
            # 同步出席紀錄：核准請假 → 標記為請假
            attendance, _ = RehearsalAttendance.objects.get_or_create(
                rehearsal=leave.rehearsal,
                member=leave.member,
            )
            attendance.status = RehearsalAttendance.Status.LEAVE
            attendance.save()
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
    checkin_url = None
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
        'checkin_url': checkin_url,
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
    try:
        hours = max(1, min(24, int(request.POST.get('hours', 4))))
    except (ValueError, TypeError):
        hours = 4
    expires_at = timezone.now() + timezone.timedelta(hours=hours)

    existing = RehearsalQRToken.objects.filter(rehearsal=rehearsal).first()
    if existing:
        existing.token = uuid.uuid4()
        existing.expires_at = expires_at
        existing.is_active = True
        existing.save()
        messages.success(request, f'QR Code 已重新產生，有效期限 {hours} 小時。')
    else:
        RehearsalQRToken.objects.create(
            rehearsal=rehearsal, expires_at=expires_at, is_active=True,
        )
        messages.success(request, f'QR Code 已產生，有效期限 {hours} 小時。')
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


@login_required
def leave_stats(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('events:event_list')

    # 選擇演出活動（預設最近一場）
    events = PerformanceEvent.objects.order_by('-performance_date')
    selected_event_id = request.GET.get('event', '')
    selected_event = None

    rehearsal_rows = []
    member_rows = []

    if not selected_event_id and events.exists():
        selected_event_id = str(events.first().pk)

    if selected_event_id:
        selected_event = events.filter(pk=selected_event_id).first()

    if selected_event:
        rehearsals = list(
            selected_event.rehearsals.order_by('sequence')
        )
        leaves = (
            LeaveRequest.objects
            .filter(rehearsal__event=selected_event)
            .select_related('member', 'rehearsal', 'reviewed_by')
        )

        # 每場排練的申請統計
        from collections import defaultdict
        rehearsal_counts = defaultdict(lambda: {'pending': 0, 'approved': 0, 'rejected': 0})
        member_leave_map = defaultdict(list)  # member_id → [LeaveRequest, ...]

        for leave in leaves:
            rehearsal_counts[leave.rehearsal_id][leave.status] += 1
            member_leave_map[leave.member_id].append(leave)

        for rehearsal in rehearsals:
            counts = rehearsal_counts[rehearsal.pk]
            rehearsal_rows.append({
                'rehearsal': rehearsal,
                'pending': counts['pending'],
                'approved': counts['approved'],
                'rejected': counts['rejected'],
                'total': counts['pending'] + counts['approved'] + counts['rejected'],
            })

        # 每位有申請紀錄的團員統計，按申請次數遞減
        for member_id, member_leaves in member_leave_map.items():
            member = member_leaves[0].member
            approved = sum(1 for l in member_leaves if l.status == 'approved')
            pending = sum(1 for l in member_leaves if l.status == 'pending')
            rejected = sum(1 for l in member_leaves if l.status == 'rejected')
            member_rows.append({
                'member': member,
                'total': len(member_leaves),
                'approved': approved,
                'pending': pending,
                'rejected': rejected,
            })
        member_rows.sort(key=lambda r: r['total'], reverse=True)

    return render(request, 'events/leave_stats.html', {
        'events': events,
        'selected_event': selected_event,
        'selected_event_id': selected_event_id,
        'rehearsal_rows': rehearsal_rows,
        'member_rows': member_rows,
    })


@login_required
def attendance_report(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('events:event_detail', pk=pk)

    event = get_object_or_404(
        PerformanceEvent.objects.select_related('performance_venue'), pk=pk
    )
    rehearsals = list(event.rehearsals.select_related('venue').order_by('sequence'))
    members = list(
        User.objects.filter(is_active=True)
        .exclude(role=User.Role.ADMIN)
        .select_related('instrument', 'section')
        .order_by('instrument__category', 'instrument__name', 'name')
    )

    attendance_map = {
        (a.rehearsal_id, a.member_id): a.status
        for a in RehearsalAttendance.objects.filter(
            rehearsal_id__in=[r.pk for r in rehearsals]
        )
    }

    # 每場排練的統計數字
    for rehearsal in rehearsals:
        counts = {'present': 0, 'leave': 0, 'absent': 0}
        for member in members:
            s = attendance_map.get((rehearsal.pk, member.pk))
            if s:
                counts[s] += 1
        counts['no_record'] = len(members) - sum(counts.values())
        rehearsal.stats = counts

    # 每位團員的橫列資料
    member_rows = []
    for member in members:
        statuses = [attendance_map.get((r.pk, member.pk)) for r in rehearsals]
        present_count = statuses.count('present')
        total = len(rehearsals)
        member_rows.append({
            'member': member,
            'statuses': statuses,
            'present_count': present_count,
            'total': total,
            'rate': round(present_count / total * 100) if total else 0,
        })

    return render(request, 'events/attendance_report.html', {
        'event': event,
        'rehearsals': rehearsals,
        'member_rows': member_rows,
    })


@login_required
def setlist_manage(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('events:event_detail', pk=pk)

    event = get_object_or_404(PerformanceEvent, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            score_id = request.POST.get('score_id')
            order = request.POST.get('order', '').strip()
            if not score_id or not order:
                messages.error(request, '請選擇曲目並填寫演出順序。')
            elif Setlist.objects.filter(event=event, order=order).exists():
                messages.error(request, f'演出順序 {order} 已被使用。')
            else:
                score = get_object_or_404(Score, pk=score_id, score_type=Score.ScoreType.FULL)
                Setlist.objects.create(event=event, score=score, order=order)
                messages.success(request, f'已新增《{score.title}》。')

        elif action == 'remove':
            item_id = request.POST.get('item_id')
            item = get_object_or_404(Setlist, pk=item_id, event=event)
            title = item.score.title
            item.delete()
            messages.success(request, f'已移除《{title}》。')

        return redirect('events:setlist_manage', pk=pk)

    setlists = event.setlists.select_related('score').order_by('order')
    available_scores = Score.objects.filter(score_type=Score.ScoreType.FULL).order_by('title')
    used_score_ids = list(setlists.values_list('score_id', flat=True))

    return render(request, 'events/setlist_manage.html', {
        'event': event,
        'setlists': setlists,
        'available_scores': available_scores,
        'used_score_ids': used_score_ids,
        'next_order': (setlists.last().order + 1) if setlists.exists() else 1,
    })
