from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import InstrumentFamily
from apps.events.models import EventPartFolder, PerformanceEvent, Setlist

from .models import Score, normalize_drive_url

# 藏譜限幹部：團員下載分譜一律走演出活動的族群資料夾（performance_parts），
# 藏譜資料夾裡有未切割的完整譜（B），不給團員。
DENIED = '權限不足，樂譜庫存僅限幹部。'


def _deny(request):
    messages.error(request, DENIED)
    return redirect('public:index')


def _performed_q(prefix=''):
    """「演過」的條件：演出時間已過、且不是已取消的場次。prefix 用於跨關聯查詢。"""
    return (
        Q(**{f'{prefix}performance_date__lt': timezone.now()})
        & ~Q(**{f'{prefix}status': PerformanceEvent.Status.CANCELLED})
    )


def _setlist_prefetch():
    """藏譜上的演出標籤：所有未取消場次（含即將演出），依日期排列。"""
    return Prefetch(
        'setlists',
        queryset=Setlist.objects.select_related('event')
        .exclude(event__status=PerformanceEvent.Status.CANCELLED)
        .order_by('event__performance_date'),
        to_attr='active_setlists',
    )


def _with_performance_count(qs):
    # 同一場重複列（例如安可）只算一次，所以用 distinct 數場次
    return qs.annotate(
        performance_count=Count(
            'setlists__event', filter=_performed_q('setlists__event__'), distinct=True,
        )
    )


@login_required
def score_list(request):
    """
    藏譜列表（幹部限定）。

    篩選：關鍵字（曲名／作曲／編曲／版本說明）、演出場次、是否已切割分譜；
    排序：曲名或演出次數。另外列兩張待辦卡片：演過但還沒歸檔分譜的藏譜、未入藏的演出曲目。
    """
    if not request.user.is_officer:
        return _deny(request)

    scores = _with_performance_count(Score.objects.all()).prefetch_related(_setlist_prefetch())

    query = request.GET.get('q', '').strip()
    event_id = request.GET.get('event', '')
    cut = request.GET.get('cut', '')
    sort = request.GET.get('sort', '')

    if query:
        scores = scores.filter(
            Q(title__icontains=query) | Q(composer__icontains=query)
            | Q(arranger__icontains=query) | Q(version_note__icontains=query)
        )
    if event_id.isdigit():
        scores = scores.filter(setlists__event_id=event_id).distinct()
    if cut == 'yes':
        scores = scores.exclude(parts_url='')
    elif cut == 'no':
        scores = scores.filter(parts_url='')

    if sort == 'count':
        scores = scores.order_by('-performance_count', 'title')
    else:
        scores = scores.order_by('title', 'arranger', 'version_note')

    page = Paginator(scores, 30).get_page(request.GET.get('page'))

    # 待辦：演過、但藏譜還沒有切割好的分譜（C）——提醒譜務從音樂會資料夾整理回來
    uncut_performed = (
        Score.objects.filter(parts_url='')
        .filter(setlists__event__in=PerformanceEvent.objects.filter(_performed_q()))
        .distinct().order_by('title')
    )
    unarchived = (
        Setlist.objects.filter(score__isnull=True)
        .select_related('event').order_by('-event__performance_date', 'order')
    )

    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'scores/score_list.html', {
        'page_obj': page,
        'scores': page.object_list,
        'events': PerformanceEvent.objects.filter(setlists__score__isnull=False)
                  .exclude(status=PerformanceEvent.Status.CANCELLED).distinct()
                  .order_by('-performance_date'),
        'query': query,
        'selected_event': event_id,
        'cut': cut,
        'sort': sort,
        'page_query': params.urlencode(),
        'uncut_performed': uncut_performed,
        'unarchived': unarchived,
        'now': timezone.now(),
    })


def _apply_score_form(request, score):
    """把 POST 資料寫進 score 實例（新建或既有皆可），回傳 errors 清單。"""
    score.title = request.POST.get('title', '').strip()
    score.composer = request.POST.get('composer', '').strip()
    score.arranger = request.POST.get('arranger', '').strip()
    score.version_note = request.POST.get('version_note', '').strip()
    score.copyright_status = request.POST.get('copyright_status', '')
    score.source = request.POST.get('source', '')
    score.publisher = request.POST.get('publisher', '').strip()
    score.difficulty = request.POST.get('difficulty', '')
    score.drive_url = normalize_drive_url(request.POST.get('drive_url', ''))
    score.parts_url = normalize_drive_url(request.POST.get('parts_url', ''))

    errors = []
    try:
        score.full_clean()
    except ValidationError as e:
        labels = {f.name: f.verbose_name for f in Score._meta.fields}
        for field, field_errors in e.message_dict.items():
            errors.extend(f'{labels.get(field, "")}：{msg}' if field in labels else msg
                          for msg in field_errors)
    return errors


def _warn_if_duplicate(request, score):
    """同曲名＋編曲＋版本說明已經有一筆時提醒（不擋：也可能真的是另一份）。"""
    dup = Score.objects.filter(
        title=score.title, arranger=score.arranger, version_note=score.version_note,
    ).exclude(pk=score.pk)
    if dup.exists():
        messages.warning(
            request,
            f'藏譜裡已經有《{score}》，若是不同版本，請在「版本說明」註明差異。'
        )


def _score_form_context():
    return {
        'copyright_choices': Score.CopyrightStatus.choices,
        'source_choices': Score.Source.choices,
        'difficulty_choices': Score.Difficulty.choices,
    }


def _initial_form_data(score):
    """既有藏譜的欄位值，供編輯頁 GET 時預先帶入。"""
    return {
        'title': score.title,
        'composer': score.composer,
        'arranger': score.arranger,
        'version_note': score.version_note,
        'copyright_status': score.copyright_status,
        'source': score.source,
        'publisher': score.publisher,
        'difficulty': score.difficulty,
        'drive_url': score.drive_url,
        'parts_url': score.parts_url,
    }


@login_required
def score_create(request):
    if not request.user.is_officer:
        return _deny(request)

    if request.method == 'POST':
        score = Score()
        errors = _apply_score_form(request, score)
        if not errors:
            score.save()
            _warn_if_duplicate(request, score)
            messages.success(request, f'藏譜《{score}》已新增。')
            return redirect('scores:score_detail', pk=score.pk)
        for error in errors:
            messages.error(request, error)
        form_data = request.POST
    else:
        form_data = {}

    return render(request, 'scores/score_form.html', {
        'action': 'create',
        'form_data': form_data,
        **_score_form_context(),
    })


@login_required
def score_edit(request, pk):
    if not request.user.is_officer:
        return _deny(request)
    score = get_object_or_404(Score, pk=pk)

    if request.method == 'POST':
        errors = _apply_score_form(request, score)
        if not errors:
            score.save()
            _warn_if_duplicate(request, score)
            messages.success(request, f'藏譜《{score}》已更新。')
            return redirect('scores:score_detail', pk=score.pk)
        for error in errors:
            messages.error(request, error)
        form_data = request.POST
    else:
        form_data = _initial_form_data(score)

    return render(request, 'scores/score_form.html', {
        'action': 'edit',
        'score': score,
        'form_data': form_data,
        **_score_form_context(),
    })


@login_required
def score_detail(request, pk):
    if not request.user.is_officer:
        return _deny(request)
    score = get_object_or_404(
        _with_performance_count(Score.objects.all()).prefetch_related(_setlist_prefetch()),
        pk=pk,
    )
    return render(request, 'scores/score_detail.html', {'score': score, 'now': timezone.now()})


@login_required
def score_delete(request, pk):
    """
    刪除藏譜限管理員（admin 角色或 superuser），跟演出活動／場地／團員通訊錄的刪除權限一致。
    已排進演出曲目單（Setlist）或對外交換紀錄（ScoreExchangeItem）引用時（PROTECT）會被擋下。
    """
    score = get_object_or_404(Score, pk=pk)
    if not (request.user.is_superuser or request.user.is_admin_role):
        messages.error(request, '權限不足，僅管理員可刪除藏譜。')
        return redirect('scores:score_detail', pk=pk)

    if request.method == 'POST':
        title = str(score)
        try:
            score.delete()
        except ProtectedError:
            messages.error(
                request,
                f'《{title}》已被演出曲目單或對外交換紀錄引用，請先處理相關資料後再刪除。'
            )
            return redirect('scores:score_detail', pk=pk)
        messages.success(request, f'已刪除藏譜《{title}》。')
        return redirect('scores:score_list')
    return redirect('scores:score_detail', pk=pk)


@login_required
def performance_parts(request, pk):
    """
    演出分譜下載入口。分譜（C）放在帳號 2「…/<年月日音樂會名稱>/<族群>/<樂器>」，
    系統記到族群資料夾這層（EventPartFolder），團員下載整個族群資料夾即可（Drive 會打包成 zip）。

    團員：只看到自己族群（User.instrument）的資料夾。
    幹部：典藏資料夾（帳號 1）、總譜資料夾（A）與所有族群資料夾。
    系統只控制「顯示哪些連結」，真正擋檔案的是 Drive 的分享設定（見 DESIGN §4.19）。
    """
    event = get_object_or_404(PerformanceEvent, pk=pk)
    user_family = request.user.instrument
    folders = EventPartFolder.objects.filter(event=event).select_related('family')

    context = {'event': event, 'user_family': user_family}
    if request.user.is_officer:
        context['all_folders'] = _folders_by_category(folders)
    else:
        context['my_folder'] = folders.filter(family=user_family).first() if user_family else None
    return render(request, 'scores/performance_parts.html', context)


def _folders_by_category(folders):
    """族群資料夾依「類別 → 族群」排好；沒貼連結的族群也列出（顯示尚無連結）。"""
    by_family = {f.family_id: f for f in folders}
    result = []
    for cat_value, cat_label in InstrumentFamily.Category.choices:
        families = InstrumentFamily.objects.filter(category=cat_value).order_by('pk')
        rows = [{'family': fam, 'folder': by_family.get(fam.pk)} for fam in families]
        if rows:
            result.append({'label': cat_label, 'rows': rows})
    return result
