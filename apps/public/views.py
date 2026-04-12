from django.shortcuts import render
from django.utils import timezone


def index(request):
    context = {}
    if request.user.is_authenticated:
        from apps.events.models import LeaveRequest, Rehearsal
        # 下次排練（最近一場未來的排練）
        context['next_rehearsal'] = (
            Rehearsal.objects
            .filter(date__gt=timezone.now())
            .select_related('event', 'venue')
            .order_by('date')
            .first()
        )
        # 我的待審請假
        context['pending_leaves'] = (
            LeaveRequest.objects
            .filter(member=request.user, status=LeaveRequest.Status.PENDING)
            .select_related('rehearsal__event')
            .order_by('rehearsal__date')
        )
        # 幹部：待審核的校友報到申請數
        if request.user.is_officer:
            from apps.accounts.models import Registration
            context['pending_registrations_count'] = Registration.objects.filter(
                status=Registration.Status.PENDING
            ).count()
    return render(request, 'public/index.html', context)


def about(request):
    return render(request, 'public/about.html')


def rules(request):
    return render(request, 'public/rules.html')
