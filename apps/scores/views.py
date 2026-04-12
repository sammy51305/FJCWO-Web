from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.accounts.models import InstrumentType

from .models import Score


@login_required
def score_list(request):
    scores = Score.objects.select_related('instrument', 'section', 'parent_score')

    score_type = request.GET.get('type', '')   # 'full' | 'part' | ''
    instrument_id = request.GET.get('instrument', '')

    if score_type in ('full', 'part'):
        scores = scores.filter(score_type=score_type)
    if instrument_id:
        scores = scores.filter(instrument_id=instrument_id)

    instruments = InstrumentType.objects.all()

    return render(request, 'scores/score_list.html', {
        'scores': scores.order_by('title'),
        'instruments': instruments,
        'selected_type': score_type,
        'selected_instrument': instrument_id,
    })


@login_required
def score_detail(request, pk):
    score = get_object_or_404(
        Score.objects.select_related('instrument', 'section', 'parent_score'),
        pk=pk,
    )
    versions = score.versions.select_related('instrument')

    return render(request, 'scores/score_detail.html', {
        'score': score,
        'versions': versions,
    })
