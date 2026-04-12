from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from apps.accounts.models import InstrumentType

from .models import Score


@login_required
def score_list(request):
    scores = Score.objects.select_related('instrument', 'section', 'parent_score')

    score_type = request.GET.get('type', '')
    instrument_id = request.GET.get('instrument', '')
    query = request.GET.get('q', '').strip()

    if score_type in ('full', 'part'):
        scores = scores.filter(score_type=score_type)
    if instrument_id:
        scores = scores.filter(instrument_id=instrument_id)
    if query:
        scores = scores.filter(title__icontains=query)

    scores = scores.order_by('title')
    paginator = Paginator(scores, 30)
    page = paginator.get_page(request.GET.get('page'))

    instruments = InstrumentType.objects.all()

    return render(request, 'scores/score_list.html', {
        'page_obj': page,
        'scores': page.object_list,
        'instruments': instruments,
        'selected_type': score_type,
        'selected_instrument': instrument_id,
        'query': query,
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


@login_required
def score_download(request, pk):
    score = get_object_or_404(Score, pk=pk)
    if not score.file:
        raise Http404
    return FileResponse(score.file.open('rb'), as_attachment=True, filename=score.file.name.split('/')[-1])
