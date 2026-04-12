from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import PerformanceEvent, Rehearsal


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
