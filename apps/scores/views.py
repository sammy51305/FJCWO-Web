from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import InstrumentFamily, InstrumentType
from apps.events.models import PerformanceEvent

from .models import CUSTOM_INSTRUMENT_NAME, Score, normalize_drive_url, validate_drive_url


@login_required
def score_list(request):
    """
    #13-4：清單只列總譜，分譜完全不出現——要看分譜一律從總譜詳情頁進去。

    連帶兩項調整：
    - 「譜種」篩選器移除（清單只剩一種譜種，篩了也沒意義）。
    - 「樂器」篩選器改變語意：總譜本身沒有 instrument 欄位，樂器是分譜才有的屬性，
      直接沿用舊的 `filter(instrument_id=...)` 會永遠篩不出東西。改成篩
      「底下有這個樂器分譜的總譜」，正好對應幹部實際想問的「哪幾首有單簧管分譜」。
    """
    scores = (
        Score.objects.filter(score_type=Score.ScoreType.FULL)
        .select_related('parent_score')
        .annotate(part_count=Count('parts'))
    )

    instrument_id = request.GET.get('instrument', '')
    query = request.GET.get('q', '').strip()

    if instrument_id:
        # 一首總譜底下同一樂器可能有多個聲部，join 會產生重複列，需要 distinct
        scores = scores.filter(parts__instrument_id=instrument_id).distinct()
    if query:
        scores = scores.filter(title__icontains=query)

    scores = scores.order_by('title')
    paginator = Paginator(scores, 30)
    page = paginator.get_page(request.GET.get('page'))

    instruments = InstrumentType.objects.select_related('family').all()

    # 分譜不再出現在清單上之後，沒綁總譜的分譜就沒有任何入口可以走到——
    # 那是資料錯誤（分譜本來就該掛在總譜下），列給幹部看，讓他們點進去補綁定。
    orphan_parts = []
    if request.user.is_officer:
        orphan_parts = list(
            Score.objects.filter(score_type=Score.ScoreType.PART, full_score__isnull=True)
            .select_related('instrument')
            .order_by('title')
        )

    return render(request, 'scores/score_list.html', {
        'page_obj': page,
        'scores': page.object_list,
        'instruments': instruments,
        'selected_instrument': instrument_id,
        'query': query,
        'orphan_parts': orphan_parts,
    })


def _apply_score_form(request, score):
    """把 POST 資料寫進 score 實例（新建或既有皆可），回傳 errors 清單。"""
    score_type = request.POST.get('score_type', '')
    instrument_id = request.POST.get('instrument', '')
    parent_score_id = request.POST.get('parent_score', '')
    full_score_id = request.POST.get('full_score', '')
    physical_quantity = request.POST.get('physical_quantity', '0').strip()

    errors = []
    try:
        physical_quantity = int(physical_quantity or 0)
    except ValueError:
        errors.append('實體數量格式錯誤。')
        physical_quantity = 0

    instrument = InstrumentType.objects.filter(pk=instrument_id).first() if instrument_id else None
    parent_score = Score.objects.filter(pk=parent_score_id).first() if parent_score_id else None
    full_score = Score.objects.filter(pk=full_score_id, score_type=Score.ScoreType.FULL).first() if full_score_id else None

    if score_type == Score.ScoreType.FULL:
        # 總譜不應指定樂器/聲部/所屬總譜：表單依 score_type 隱藏欄位，這裡直接忽略殘留值
        instrument = None
        full_score = None

    score.title = request.POST.get('title', '').strip()
    score.composer = request.POST.get('composer', '').strip()
    score.arranger = request.POST.get('arranger', '').strip()
    score.score_type = score_type
    score.instrument = instrument
    score.copyright_status = request.POST.get('copyright_status', '')
    score.physical_quantity = physical_quantity
    score.source = request.POST.get('source', '')
    score.publisher = request.POST.get('publisher', '').strip()
    score.difficulty = request.POST.get('difficulty', '')
    score.full_score = full_score
    score.parent_score = parent_score
    score.version_note = request.POST.get('version_note', '').strip()

    if 'drive_url' in request.POST:  # 表單一定會送；沒送（舊呼叫端）就保留原值
        score.drive_url = normalize_drive_url(request.POST['drive_url'])
    custom_name = request.POST.get('custom_instrument_name', '').strip()
    # 只有「其他（手填）」這個樂器才用得到手填名稱；其餘一律清空，避免殘留值
    score.custom_instrument_name = custom_name if (instrument and instrument.name == CUSTOM_INSTRUMENT_NAME) else ''

    if not errors:
        try:
            score.full_clean()
        except ValidationError as e:
            for field_errors in e.message_dict.values():
                errors.extend(field_errors)

    return errors


def _score_form_context(score=None):
    full_scores = Score.objects.filter(score_type=Score.ScoreType.FULL)
    if score:
        full_scores = full_scores.exclude(pk=score.pk)
    return {
        'instruments': InstrumentType.objects.select_related('family')
                       .order_by('family__category', 'family__name', 'name'),
        'custom_instrument_id': InstrumentType.objects.filter(name=CUSTOM_INSTRUMENT_NAME).values_list('pk', flat=True).first(),
        'scores_for_parent': Score.objects.exclude(pk=score.pk).order_by('title') if score else Score.objects.order_by('title'),
        'full_scores': full_scores.order_by('title'),
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
        'copyright_status': score.copyright_status,
        'physical_quantity': score.physical_quantity,
        'source': score.source,
        'publisher': score.publisher,
        'difficulty': score.difficulty,
        'full_score': str(score.full_score_id or ''),
        'parent_score': str(score.parent_score_id or ''),
        'version_note': score.version_note,
        'drive_url': score.drive_url,
        'custom_instrument_name': score.custom_instrument_name,
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
def score_delete(request, pk):
    """
    刪除樂譜限管理員（admin 角色或 superuser），跟演出活動／場地／團員通訊錄的刪除權限一致。
    若已被排入演出曲目單（Setlist）或對外交換紀錄（ScoreExchangeItem）引用（PROTECT）會被擋下；
    刪除總譜會連帶刪除底下所有分譜（Score.full_score 為 CASCADE，屬既有預期行為）。
    刪掉分譜後導回所屬總譜而不是清單——#13-4 之後清單不列分譜，導回清單等於把人丟在找不到
    原本那首曲子的地方。
    """
    score = get_object_or_404(Score, pk=pk)
    if not (request.user.is_superuser or request.user.is_admin_role):
        messages.error(request, '權限不足，僅管理員可刪除樂譜。')
        return redirect('scores:score_detail', pk=pk)

    if request.method == 'POST':
        title = str(score)
        # #13-4 之後清單不列分譜，刪完分譜再導回清單就找不回原本那首曲子了。
        # 先記下所屬總譜，刪完導回去，讓幹部可以接著處理同一首的其他分譜。
        parent_pk = score.full_score_id
        try:
            score.delete()
            messages.success(request, f'已刪除樂譜《{title}》。')
        except ProtectedError:
            messages.error(
                request,
                f'《{title}》已被演出曲目單或對外交換紀錄引用，請先處理相關資料後再刪除。'
            )
            return redirect('scores:score_detail', pk=pk)
        if parent_pk:
            return redirect('scores:score_detail', pk=parent_pk)
        return redirect('scores:score_list')
    return redirect('scores:score_detail', pk=pk)


@login_required
def score_detail(request, pk):
    score = get_object_or_404(
        Score.objects.select_related('instrument', 'parent_score')
                     .prefetch_related('parts__instrument'),
        pk=pk,
    )
    versions = score.versions.select_related('instrument')

    return render(request, 'scores/score_detail.html', {
        'score': score,
        'versions': versions,
    })


def _parts_manage_context(score, values=None):
    """
    分譜管理頁的資料：大分類 → 族群 → 樂器，每種樂器一格 Google 連結。
    「其他（手填）」不在固定清單裡，另外列成「手填樂器」區（可新增多列）。

    values：POST 驗證失敗時，把使用者剛填的值帶回來（避免整頁填的連結白費）。
    """
    values = values or {}
    existing = {}
    custom_parts = []
    for part in score.parts.select_related('instrument').order_by('pk'):
        if part.is_custom_instrument:
            custom_parts.append({'name': part.custom_instrument_name, 'url': part.drive_url})
        else:
            existing.setdefault(part.instrument_id, part)

    categories_data = []
    for cat_value, cat_label in InstrumentFamily.Category.choices:
        families_in_cat = []
        families = (
            InstrumentFamily.objects.filter(category=cat_value)
            .prefetch_related('instruments').order_by('name')
        )
        for family in families:
            instruments_data = []
            for instrument in family.instruments.order_by('name'):
                if instrument.name == CUSTOM_INSTRUMENT_NAME:
                    continue
                part = existing.get(instrument.pk)
                key = f'url_{instrument.pk}'
                instruments_data.append({
                    'instrument': instrument,
                    'field': key,
                    'url': values.get(key, part.drive_url if part else ''),
                })
            if instruments_data:
                families_in_cat.append({'family': family, 'instruments': instruments_data})
        if families_in_cat:
            categories_data.append({'category_label': cat_label, 'families': families_in_cat})

    if 'custom_name' in values:
        custom_parts = [
            {'name': n, 'url': u}
            for n, u in zip(values.getlist('custom_name'), values.getlist('custom_url'))
        ]

    instrument_options = [
        {'field': f'url_{i.pk}', 'name': i.name}
        for i in InstrumentType.objects.exclude(name=CUSTOM_INSTRUMENT_NAME)
    ]
    return {
        'score': score,
        'categories_data': categories_data,
        'custom_parts': custom_parts,
        'instrument_options': instrument_options,
    }


def _parse_parts_post(post):
    """
    讀分譜管理頁的 POST，回傳 (樂器連結 {樂器pk: url}, 手填 [(名稱, url)], 錯誤清單)。
    連結欄位全部選填：空白代表這首曲子沒有這個樂器。
    """
    errors = []
    urls = {}
    for key, value in post.items():
        if not key.startswith('url_'):
            continue
        value = normalize_drive_url(value)
        if not value:
            continue
        try:
            inst_id = int(key[len('url_'):])
        except ValueError:
            continue
        instrument = InstrumentType.objects.filter(pk=inst_id).first()
        if not instrument or instrument.name == CUSTOM_INSTRUMENT_NAME:
            continue
        try:
            validate_drive_url(value)
        except ValidationError as e:
            errors.append(f'{instrument.name}：{e.messages[0]}')
            continue
        urls[inst_id] = value

    customs = []
    seen_names = set()
    for name, url in zip(post.getlist('custom_name'), post.getlist('custom_url')):
        name, url = name.strip(), normalize_drive_url(url)
        if not name and not url:
            continue
        if not name or not url:
            errors.append(f'手填樂器「{name or url}」：名稱與連結都要填。')
            continue
        if name in seen_names:
            errors.append(f'手填樂器「{name}」重複了。')
            continue
        try:
            validate_drive_url(url)
        except ValidationError as e:
            errors.append(f'{name}：{e.messages[0]}')
            continue
        seen_names.add(name)
        customs.append((name, url))
    return urls, customs, errors


@login_required
def score_parts_manage(request, pk):
    """
    分譜連結管理（幹部）。樂譜檔案放在樂團的 Google Drive，這裡只貼連結：
    每種樂器一格、全部選填（空白 = 這首沒有這個樂器），至少要填一個。
    再次送出時，以送出的內容為準——清空的格子會把原有分譜移除。
    """
    score = get_object_or_404(Score, pk=pk, score_type=Score.ScoreType.FULL)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('scores:score_detail', pk=pk)

    if request.method == 'POST':
        urls, customs, errors = _parse_parts_post(request.POST)
        if not errors and not urls and not customs:
            errors.append('請至少填一個樂器的連結。')
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'scores/score_parts_manage.html',
                          _parts_manage_context(score, values=request.POST))

        custom_instrument = InstrumentType.objects.filter(name=CUSTOM_INSTRUMENT_NAME).first()
        keep = set()

        def upsert(instrument, custom_name, url):
            part = Score.objects.filter(
                full_score=score, instrument=instrument, custom_instrument_name=custom_name,
            ).order_by('pk').first()
            if part is None:
                part = Score(
                    full_score=score, instrument=instrument, custom_instrument_name=custom_name,
                    title=score.title, score_type=Score.ScoreType.PART,
                    copyright_status=score.copyright_status,
                )
            part.drive_url = url
            part.save()
            keep.add(part.pk)

        for inst_id, url in urls.items():
            upsert(InstrumentType.objects.get(pk=inst_id), '', url)
        if customs and custom_instrument:
            for name, url in customs:
                upsert(custom_instrument, name, url)

        stale = score.parts.exclude(pk__in=keep)
        removed = stale.count()
        try:
            stale.delete()
        except ProtectedError:
            removed = 0
            messages.warning(request, '有些舊分譜已被其他資料引用，無法移除。')
        messages.success(request, f'已儲存 {len(keep)} 份分譜連結' + (f'，移除 {removed} 份。' if removed else '。'))
        return redirect('scores:score_parts_manage', pk=pk)

    return render(request, 'scores/score_parts_manage.html', _parts_manage_context(score))


@login_required
def performance_parts(request, pk):
    """
    演出分譜下載入口：依登入者的樂器族群，篩選出這場演出曲目單裡用得到的分譜。

    關聯路徑：PerformanceEvent → Setlist.score（總譜）→ Score.parts（分譜）。
    篩選層級：User.instrument 指向「樂器族群」(InstrumentFamily)，Score.instrument 指向
    「具體樂器」(InstrumentType)，兩者差一層，因此用 instrument__family 比對族群——
    同族群底下各具體樂器的分譜全部列出，由團員自行判斷要下載哪一份
    （呼應「不強制指定聲部」的設計）。
    """
    event = get_object_or_404(PerformanceEvent, pk=pk)
    user_family = request.user.instrument

    groups = []
    if user_family:
        parts = (
            Score.objects
            .filter(
                score_type=Score.ScoreType.PART,
                full_score__setlists__event=event,
                instrument__family=user_family,
            )
            .select_related('instrument', 'full_score')
            .distinct()
            .order_by('full_score__title', 'instrument__name', 'custom_instrument_name')
        )
        # 依所屬總譜（曲目）分組，方便前端一首一首列；parts 已依 full_score__title 排序，
        # dict 保留插入順序，group 自然照曲名排列
        grouped = {}
        for part in parts:
            grouped.setdefault(
                part.full_score_id,
                {'full_score': part.full_score, 'parts': []},
            )['parts'].append(part)
        groups = list(grouped.values())

    return render(request, 'scores/performance_parts.html', {
        'event': event,
        'groups': groups,
        'user_family': user_family,
    })
