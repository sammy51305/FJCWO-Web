from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
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


def _apply_score_form(request, score):
    """把 POST 資料寫進 score 實例（新建或既有皆可），回傳 errors 清單。"""
    score_type = request.POST.get('score_type', '')
    instrument_id = request.POST.get('instrument', '')
    section_id = request.POST.get('section', '')
    parent_score_id = request.POST.get('parent_score', '')
    physical_quantity = request.POST.get('physical_quantity', '0').strip()

    errors = []
    try:
        physical_quantity = int(physical_quantity or 0)
    except ValueError:
        errors.append('實體數量格式錯誤。')
        physical_quantity = 0

    instrument = InstrumentType.objects.filter(pk=instrument_id).first() if instrument_id else None
    section = SectionType.objects.filter(pk=section_id).first() if section_id else None
    parent_score = Score.objects.filter(pk=parent_score_id).first() if parent_score_id else None

    if score_type == Score.ScoreType.FULL:
        # 總譜不應指定樂器/聲部：表單依 score_type 隱藏欄位，這裡直接忽略殘留值
        instrument = None
        section = None

    score.title = request.POST.get('title', '').strip()
    score.composer = request.POST.get('composer', '').strip()
    score.arranger = request.POST.get('arranger', '').strip()
    score.score_type = score_type
    score.instrument = instrument
    score.section = section
    score.copyright_status = request.POST.get('copyright_status', '')
    score.physical_quantity = physical_quantity
    score.source = request.POST.get('source', '')
    score.publisher = request.POST.get('publisher', '').strip()
    score.difficulty = request.POST.get('difficulty', '')
    score.parent_score = parent_score
    score.version_note = request.POST.get('version_note', '').strip()

    file = request.FILES.get('file')
    if file:
        score.file = file

    if not errors:
        try:
            score.full_clean()
        except ValidationError as e:
            for field_errors in e.message_dict.values():
                errors.extend(field_errors)

    return errors


def _score_form_context(score=None):
    return {
        'instruments': InstrumentType.objects.select_related('family')
                       .order_by('family__category', 'family__name', 'name'),
        'sections': SectionType.objects.all(),
        'scores_for_parent': Score.objects.exclude(pk=score.pk).order_by('title') if score else Score.objects.order_by('title'),
        'score_type_choices': Score.ScoreType.choices,
        'copyright_choices': Score.CopyrightStatus.choices,
        'source_choices': Score.Source.choices,
        'difficulty_choices': Score.Difficulty.choices,
    }


def _initial_form_data(score):
    """既有樂譜的欄位值，轉成表單欄位名稱對應的字典，供編輯頁 GET 時預先帶入。"""
    return {
        'title': score.title,
        'composer': score.composer,
        'arranger': score.arranger,
        'score_type': score.score_type,
        'instrument': str(score.instrument_id or ''),
        'section': str(score.section_id or ''),
        'copyright_status': score.copyright_status,
        'physical_quantity': score.physical_quantity,
        'source': score.source,
        'publisher': score.publisher,
        'difficulty': score.difficulty,
        'parent_score': str(score.parent_score_id or ''),
        'version_note': score.version_note,
    }


@login_required
def score_create(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('scores:score_list')

    if request.method == 'POST':
        score = Score()
        errors = _apply_score_form(request, score)

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            score.save()
            messages.success(request, f'樂譜《{score.title}》已新增。')
            return redirect('scores:score_detail', pk=score.pk)

        return render(request, 'scores/score_form.html', {
            'action': 'create',
            'form_data': request.POST,
            **_score_form_context(),
        })

    return render(request, 'scores/score_form.html', {
        'action': 'create',
        'form_data': {},
        **_score_form_context(),
    })


@login_required
def score_edit(request, pk):
    score = get_object_or_404(Score, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('scores:score_detail', pk=pk)

    if request.method == 'POST':
        errors = _apply_score_form(request, score)

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            score.save()
            messages.success(request, f'樂譜《{score.title}》已更新。')
            return redirect('scores:score_detail', pk=score.pk)

        return render(request, 'scores/score_form.html', {
            'action': 'edit',
            'score': score,
            'form_data': request.POST,
            **_score_form_context(score),
        })

    return render(request, 'scores/score_form.html', {
        'action': 'edit',
        'score': score,
        'form_data': _initial_form_data(score),
        **_score_form_context(score),
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

    # 依分類（木管/銅管/打擊/其他）→ 族群 → 樂器 三層建立巢狀結構
    categories_data = []
    for cat_value, cat_label in InstrumentFamily.Category.choices:
        families_in_cat = []
        for family in InstrumentFamily.objects.filter(category=cat_value).prefetch_related('instruments').order_by('name'):
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
            if instruments_data:
                families_in_cat.append({
                    'family': family,
                    'instruments': instruments_data,
                    'single': len(instruments_data) == 1,
                })
        if families_in_cat:
            categories_data.append({
                'category_label': cat_label,
                'families': families_in_cat,
            })

    return render(request, 'scores/score_parts_manage.html', {
        'score': score,
        'categories_data': categories_data,
    })


@login_required
def score_download(request, pk):
    score = get_object_or_404(Score, pk=pk)
    if not score.file:
        raise Http404
    return FileResponse(score.file.open('rb'), as_attachment=True, filename=score.file.name.split('/')[-1])
