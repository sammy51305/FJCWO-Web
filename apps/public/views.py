from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import AboutSection, CharterContent, Venue, VenueTimeSlot

_WEEKDAY_FIELDS = ['is_sun', 'is_mon', 'is_tue', 'is_wed', 'is_thu', 'is_fri', 'is_sat']


def _parse_time(value):
    try:
        return datetime.strptime(value, '%H:%M').time()
    except (ValueError, TypeError):
        return None


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
        # 我的請假審核結果（核准/拒絕後尚未在首頁看過的通知）
        reviewed_leaves = list(
            LeaveRequest.objects
            .filter(member=request.user, result_seen=False)
            .exclude(status=LeaveRequest.Status.PENDING)
            .select_related('rehearsal__event')
            .order_by('-reviewed_at')
        )
        context['reviewed_leaves'] = reviewed_leaves
        if reviewed_leaves:
            LeaveRequest.objects.filter(
                pk__in=[leave.pk for leave in reviewed_leaves]
            ).update(result_seen=True)
        # 幹部：待審核的校友報到申請數
        if request.user.is_officer:
            from apps.accounts.models import Registration
            context['pending_registrations_count'] = Registration.objects.filter(
                status=Registration.Status.PENDING
            ).count()
    return render(request, 'public/index.html', context)


def about(request):
    sections = AboutSection.objects.filter(is_visible=True)
    return render(request, 'public/about.html', {'sections': sections})


def rules(request):
    charter = CharterContent.objects.first()
    return render(request, 'public/rules.html', {'charter': charter})


@login_required
def rules_edit(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('public:rules')

    charter, _ = CharterContent.objects.get_or_create(pk=1)

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        charter.content = content
        charter.save()
        messages.success(request, '組織章程已更新。')
        return redirect('public:rules')

    return render(request, 'public/rules_edit.html', {'charter': charter})


@login_required
def about_manage(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('public:about')

    sections = AboutSection.objects.all()
    return render(request, 'public/about_manage.html', {'sections': sections})


@login_required
def about_create(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('public:about')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        order = request.POST.get('order', '0').strip()
        is_visible = request.POST.get('is_visible') == 'on'

        errors = []
        if not title:
            errors.append('請填寫標題。')
        if not content:
            errors.append('請填寫內容。')
        if not order.isdigit():
            errors.append('顯示順序請填入數字。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            AboutSection.objects.create(
                title=title, content=content,
                order=int(order), is_visible=is_visible,
            )
            messages.success(request, f'區塊《{title}》已新增。')
            return redirect('public:about_manage')

    next_order = (AboutSection.objects.order_by('-order').values_list('order', flat=True).first() or 0) + 1
    return render(request, 'public/about_form.html', {
        'action': 'create',
        'next_order': next_order,
    })


@login_required
def about_edit(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('public:about')

    section = get_object_or_404(AboutSection, pk=pk)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        order = request.POST.get('order', '0').strip()
        is_visible = request.POST.get('is_visible') == 'on'

        errors = []
        if not title:
            errors.append('請填寫標題。')
        if not content:
            errors.append('請填寫內容。')
        if not order.isdigit():
            errors.append('顯示順序請填入數字。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            section.title = title
            section.content = content
            section.order = int(order)
            section.is_visible = is_visible
            section.save()
            messages.success(request, f'區塊《{title}》已更新。')
            return redirect('public:about_manage')

    return render(request, 'public/about_form.html', {
        'action': 'edit',
        'section': section,
    })


@login_required
def about_delete(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('public:about')

    if request.method != 'POST':
        return redirect('public:about_manage')

    section = get_object_or_404(AboutSection, pk=pk)
    title = section.title
    section.delete()
    messages.success(request, f'區塊《{title}》已刪除。')
    return redirect('public:about_manage')


def _apply_venue_form(request, venue):
    """把 POST 資料寫進 venue 實例（新建或既有皆可），回傳 errors 清單"""
    name = request.POST.get('name', '').strip()
    venue_type = request.POST.get('type', '')
    capacity = request.POST.get('capacity', '').strip()

    errors = []
    if not name:
        errors.append('請填寫場地名稱。')
    if venue_type not in Venue.Type.values:
        errors.append('請選擇場地類別。')

    capacity_value = None
    if capacity:
        try:
            capacity_value = int(capacity)
        except ValueError:
            errors.append('容納人數格式錯誤。')

    venue.name = name
    venue.type = venue_type
    venue.address = request.POST.get('address', '').strip()
    venue.capacity = capacity_value
    venue.phone = request.POST.get('phone', '').strip()
    venue.google_map_url = request.POST.get('google_map_url', '').strip()
    venue.contact_person = request.POST.get('contact_person', '').strip()
    venue.contact_phone = request.POST.get('contact_phone', '').strip()
    venue.transportation = request.POST.get('transportation', '').strip()
    venue.motorcycle_parking = request.POST.get('motorcycle_parking', '')
    venue.car_parking = request.POST.get('car_parking', '')
    venue.notes = request.POST.get('notes', '').strip()

    return errors


def _venue_form_context():
    return {
        'type_choices': Venue.Type.choices,
        'parking_choices': Venue.ParkingStatus.choices,
    }


@login_required
def venue_list(request):
    """場地管理列表：幹部可查詢/篩選，新增/編輯；管理員可刪除"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('public:index')

    venues = Venue.objects.all()

    query = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '')

    if query:
        venues = venues.filter(Q(name__icontains=query) | Q(address__icontains=query))
    if type_filter in Venue.Type.values:
        venues = venues.filter(type=type_filter)

    venues = venues.prefetch_related('time_slots').order_by('name')

    return render(request, 'public/venue_list.html', {
        'venues': venues,
        'query': query,
        'type_filter': type_filter,
        'type_choices': Venue.Type.choices,
    })


@login_required
def venue_create(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('public:venue_list')

    if request.method == 'POST':
        venue = Venue()
        errors = _apply_venue_form(request, venue)

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            venue.save()
            messages.success(request, f'場地《{venue.name}》已新增，可在下方新增時段。')
            return redirect('public:venue_edit', pk=venue.pk)

        return render(request, 'public/venue_form.html', {
            'action': 'create',
            'form_data': request.POST,
            **_venue_form_context(),
        })

    return render(request, 'public/venue_form.html', {
        'action': 'create',
        'form_data': {},
        **_venue_form_context(),
    })


@login_required
def venue_edit(request, pk):
    venue = get_object_or_404(Venue, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('public:venue_list')

    if request.method == 'POST' and 'add_timeslot' in request.POST:
        start_time = _parse_time(request.POST.get('start_time', ''))
        end_time = _parse_time(request.POST.get('end_time', ''))
        fee = request.POST.get('fee', '').strip()
        weekdays = {field: request.POST.get(field) == 'on' for field in _WEEKDAY_FIELDS}

        errors = []
        if not start_time or not end_time:
            errors.append('請填寫正確的開始／結束時間（格式 HH:MM）。')
        if not any(weekdays.values()):
            errors.append('請至少勾選一個星期。')

        fee_value = None
        if fee:
            try:
                fee_value = int(fee)
            except ValueError:
                errors.append('費用格式錯誤。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            VenueTimeSlot.objects.create(
                venue=venue, start_time=start_time, end_time=end_time, fee=fee_value, **weekdays
            )
            messages.success(request, '已新增時段。')
        return redirect('public:venue_edit', pk=venue.pk)

    if request.method == 'POST':
        errors = _apply_venue_form(request, venue)

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            venue.save()
            messages.success(request, f'場地《{venue.name}》已更新。')
            return redirect('public:venue_list')

        return render(request, 'public/venue_form.html', {
            'action': 'edit',
            'venue': venue,
            'form_data': request.POST,
            'time_slots': venue.time_slots.all(),
            **_venue_form_context(),
        })

    form_data = {
        'name': venue.name,
        'type': venue.type,
        'address': venue.address,
        'capacity': venue.capacity,
        'phone': venue.phone,
        'google_map_url': venue.google_map_url,
        'contact_person': venue.contact_person,
        'contact_phone': venue.contact_phone,
        'transportation': venue.transportation,
        'motorcycle_parking': venue.motorcycle_parking,
        'car_parking': venue.car_parking,
        'notes': venue.notes,
    }

    return render(request, 'public/venue_form.html', {
        'action': 'edit',
        'venue': venue,
        'form_data': form_data,
        'time_slots': venue.time_slots.all(),
        **_venue_form_context(),
    })


@login_required
def venue_timeslot_delete(request, pk):
    slot = get_object_or_404(VenueTimeSlot, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('public:venue_list')

    if request.method == 'POST':
        venue_pk = slot.venue_id
        slot.delete()
        messages.success(request, '已刪除時段。')
        return redirect('public:venue_edit', pk=venue_pk)
    return redirect('public:venue_list')


@login_required
def venue_delete(request, pk):
    """刪除場地限管理員（admin 角色或 superuser）；若已被演出/排練引用（PROTECT）會被資料庫擋下"""
    venue = get_object_or_404(Venue, pk=pk)
    if not (request.user.is_superuser or request.user.is_admin_role):
        messages.error(request, '權限不足，僅管理員可刪除場地。')
        return redirect('public:venue_list')

    if request.method == 'POST':
        name = venue.name
        try:
            venue.delete()
            messages.success(request, f'已刪除場地《{name}》。')
        except ProtectedError:
            messages.error(request, f'場地《{name}》已被演出活動或排練引用，請先處理相關紀錄後再刪除。')
    return redirect('public:venue_list')
