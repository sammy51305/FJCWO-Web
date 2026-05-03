from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import InstrumentFamily, InstrumentType, SectionType

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

    instruments = InstrumentType.objects.select_related('family').all()

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
        Score.objects.select_related('instrument', 'section', 'parent_score')
                     .prefetch_related('parts__instrument', 'parts__section'),
        pk=pk,
    )
    versions = score.versions.select_related('instrument')

    return render(request, 'scores/score_detail.html', {
        'score': score,
        'versions': versions,
    })


@login_required
def score_parts_manage(request, pk):
    score = get_object_or_404(Score, pk=pk, score_type=Score.ScoreType.FULL)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('scores:score_detail', pk=pk)

    sections = list(SectionType.objects.all())

    # 現有分譜 map：key = "{instrument_id}_{section_id}"
    existing = {}
    for part in score.parts.select_related('instrument', 'section'):
        key = f'{part.instrument_id}_{part.section_id or 0}'
        existing[key] = part

    if request.method == 'POST':
        uploaded = 0
        for field_name, file in request.FILES.items():
            if not field_name.startswith('file_'):
                continue
            try:
                _, inst_id_str, sect_id_str = field_name.split('_', 2)
                inst_id = int(inst_id_str)
                sect_id = int(sect_id_str)
            except (ValueError, AttributeError):
                continue

            instrument = InstrumentType.objects.filter(pk=inst_id).first()
            if not instrument:
                continue
            section = SectionType.objects.filter(pk=sect_id).first() if sect_id else None

            part, _ = Score.objects.get_or_create(
                full_score=score,
                instrument=instrument,
                section=section,
                defaults={
                    'title': score.title,
                    'score_type': Score.ScoreType.PART,
                    'copyright_status': score.copyright_status,
                },
            )
            part.file = file
            part.save()
            uploaded += 1

        if uploaded:
            messages.success(request, f'已上傳 {uploaded} 份分譜。')
        else:
            messages.warning(request, '未偵測到上傳檔案。')
        return redirect('scores:score_parts_manage', pk=pk)

    # 建立巢狀結構供 template 使用
    families_data = []
    for family in InstrumentFamily.objects.prefetch_related('instruments').order_by('category', 'name'):
        instruments_data = []
        for instrument in family.instruments.order_by('name'):
            sections_data = []
            for section in sections:
                key = f'{instrument.pk}_{section.pk}'
                sections_data.append({
                    'section': section,
                    'key': key,
                    'existing_part': existing.get(key),
                })
            instruments_data.append({
                'instrument': instrument,
                'sections': sections_data,
            })
        families_data.append({
            'family': family,
            'instruments': instruments_data,
        })

    return render(request, 'scores/score_parts_manage.html', {
        'score': score,
        'families_data': families_data,
    })


@login_required
def score_download(request, pk):
    score = get_object_or_404(Score, pk=pk)
    if not score.file:
        raise Http404
    return FileResponse(score.file.open('rb'), as_attachment=True, filename=score.file.name.split('/')[-1])
