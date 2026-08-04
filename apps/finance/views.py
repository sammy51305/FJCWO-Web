from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.accounts.models import User
from apps.events.models import PerformanceEvent

from .models import FeePeriod, FinanceRecord, MembershipFee


@login_required
def membership_fee_report(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('/')

    # 期別主檔（附錄五 §9）：從新到舊
    periods = FeePeriod.objects.all()

    selected_period_id = request.GET.get('period', '')
    selected_period = None
    if selected_period_id:
        selected_period = periods.filter(pk=selected_period_id).first()
    elif periods:
        selected_period = periods.first()

    rows = []
    paid_count = unpaid_count = no_record_count = 0

    if selected_period:
        members = (
            User.objects.filter(is_active=True)
            .exclude(role__in=[User.Role.ADMIN, User.Role.GUEST])
            .select_related('instrument')
            .order_by('instrument__category', 'instrument__name', 'name')
        )
        fee_map = {
            f.member_id: f
            for f in MembershipFee.objects.filter(period=selected_period).select_related('collected_by')
        }
        for member in members:
            fee = fee_map.get(member.pk)
            # 無列、或已作廢 → 視為無紀錄（應繳未繳）
            if fee is None or fee.status == MembershipFee.Status.VOID:
                status = 'no_record'
                no_record_count += 1
            elif fee.status == MembershipFee.Status.PAID:
                status = 'paid'
                paid_count += 1
            else:  # unpaid / reported
                status = 'unpaid'
                unpaid_count += 1
            rows.append({'member': member, 'fee': fee, 'status': status})

    return render(request, 'finance/membership_fee_report.html', {
        'periods': periods,
        'selected_period': selected_period,
        'rows': rows,
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
        'no_record_count': no_record_count,
    })


# ── 會費期別主檔（FeePeriod）CRUD ─────────────────────────────
# 幹部可新增/編輯期別；刪除限管理員（比照其他管理員限定刪除）。


def _parse_fee_period_form(request):
    """解析期別表單，回傳 (cleaned:dict, errors:list)。"""
    errors = []
    year_raw = request.POST.get('year', '').strip()
    term = request.POST.get('term', '')
    amount_raw = request.POST.get('amount', '').strip()

    try:
        year = int(year_raw)
        if year < 2000 or year > 2100:
            errors.append('年份需在 2000～2100 之間。')
    except (ValueError, TypeError):
        year = None
        errors.append('年份必須是數字。')

    if term not in FeePeriod.Term.values:
        errors.append('請選擇上期或下期。')

    try:
        amount = int(amount_raw)
        if amount < 1:
            errors.append('團費金額必須大於 0。')
    except (ValueError, TypeError):
        amount = None
        errors.append('團費金額必須是數字。')

    cleaned = {
        'year': year, 'term': term, 'amount': amount,
        'start_date': parse_date(request.POST.get('start_date', '').strip() or ''),
        'end_date': parse_date(request.POST.get('end_date', '').strip() or ''),
    }
    return cleaned, errors


@login_required
def fee_period_list(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('/')
    periods = FeePeriod.objects.all()
    return render(request, 'finance/fee_period_list.html', {'periods': periods})


@login_required
def fee_period_create(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('finance:fee_period_list')

    if request.method == 'POST':
        cleaned, errors = _parse_fee_period_form(request)
        if not errors and FeePeriod.objects.filter(year=cleaned['year'], term=cleaned['term']).exists():
            errors.append('這個年份與期別已存在。')
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'finance/fee_period_form.html', {
                'action': 'create', 'form_data': request.POST,
                'term_choices': FeePeriod.Term.choices,
            })
        FeePeriod.objects.create(created_by=request.user, **cleaned)
        messages.success(request, f'已新增期別 {cleaned["year"]} {dict(FeePeriod.Term.choices)[cleaned["term"]]}。')
        return redirect('finance:fee_period_list')

    return render(request, 'finance/fee_period_form.html', {
        'action': 'create', 'form_data': {}, 'term_choices': FeePeriod.Term.choices,
    })


@login_required
def fee_period_edit(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('finance:fee_period_list')

    period = get_object_or_404(FeePeriod, pk=pk)
    if request.method == 'POST':
        cleaned, errors = _parse_fee_period_form(request)
        if not errors and FeePeriod.objects.filter(
                year=cleaned['year'], term=cleaned['term']).exclude(pk=period.pk).exists():
            errors.append('這個年份與期別已存在。')
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'finance/fee_period_form.html', {
                'action': 'edit', 'period': period, 'form_data': request.POST,
                'term_choices': FeePeriod.Term.choices,
            })
        for k, v in cleaned.items():
            setattr(period, k, v)
        period.save()
        messages.success(request, '期別已更新。')
        return redirect('finance:fee_period_list')

    form_data = {
        'year': period.year, 'term': period.term, 'amount': period.amount,
        'start_date': period.start_date.isoformat() if period.start_date else '',
        'end_date': period.end_date.isoformat() if period.end_date else '',
    }
    return render(request, 'finance/fee_period_form.html', {
        'action': 'edit', 'period': period, 'form_data': form_data,
        'term_choices': FeePeriod.Term.choices,
    })


@login_required
def fee_period_delete(request, pk):
    """刪除期別限管理員；已有繳費紀錄（PROTECT）時擋下。"""
    period = get_object_or_404(FeePeriod, pk=pk)
    if not (request.user.is_superuser or request.user.is_admin_role):
        messages.error(request, '權限不足，僅管理員可刪除期別。')
        return redirect('finance:fee_period_list')
    if request.method == 'POST':
        try:
            label = str(period)
            period.delete()
            messages.success(request, f'已刪除期別 {label}。')
        except ProtectedError:
            messages.error(request, '此期別已有繳費紀錄，無法刪除。')
    return redirect('finance:fee_period_list')


# ── 收支明細（FinanceRecord）前端 CRUD ─────────────────────────
# 幹部限定；刪除限管理員（財務資料敏感）。金額一律驗正數（>0）。


def _apply_finance_form(request, record):
    """把 POST 資料寫進 FinanceRecord（新建/既有皆可），回傳 errors 清單（全中文）。"""
    errors = []
    type_ = request.POST.get('type', '')
    category = request.POST.get('category', '')
    description = request.POST.get('description', '').strip()
    amount_raw = request.POST.get('amount', '').strip()
    date_raw = request.POST.get('date', '').strip()
    event_id = request.POST.get('related_event', '')

    if type_ not in FinanceRecord.Type.values:
        errors.append('請選擇收入或支出。')
    if category not in FinanceRecord.Category.values:
        errors.append('請選擇分類。')
    if not description:
        errors.append('請填寫說明。')

    amount = None
    try:
        amount = int(amount_raw)
    except (ValueError, TypeError):
        errors.append('金額必須是數字。')
    else:
        if amount < 1:
            errors.append('金額必須大於 0。')

    date_val = parse_date(date_raw) if date_raw else None
    if not date_val:
        errors.append('請填寫有效日期。')

    if not errors:
        record.type = type_
        record.category = category
        record.description = description
        record.amount = amount
        record.date = date_val
        record.related_event = (
            PerformanceEvent.objects.filter(pk=event_id).first() if event_id else None
        )
        file = request.FILES.get('attachment')
        if file:
            record.attachment = file
    return errors


def _finance_form_context(action, record=None, form_data=None):
    return {
        'action': action,
        'record': record,
        'form_data': form_data if form_data is not None else {},
        'events': PerformanceEvent.objects.order_by('-performance_date'),
        'type_choices': FinanceRecord.Type.choices,
        'category_choices': FinanceRecord.Category.choices,
    }


@login_required
def finance_list(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('/')

    records = FinanceRecord.objects.select_related('created_by', 'related_event')
    type_filter = request.GET.get('type', '')
    if type_filter in FinanceRecord.Type.values:
        records = records.filter(type=type_filter)
    records = list(records.order_by('-date', '-id'))

    income = sum(r.amount for r in records if r.type == FinanceRecord.Type.INCOME)
    expense = sum(r.amount for r in records if r.type == FinanceRecord.Type.EXPENSE)

    return render(request, 'finance/finance_list.html', {
        'records': records,
        'type_filter': type_filter,
        'income': income,
        'expense': expense,
        'balance': income - expense,
    })


@login_required
def finance_create(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('finance:finance_list')

    if request.method == 'POST':
        record = FinanceRecord(created_by=request.user)
        errors = _apply_finance_form(request, record)
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'finance/finance_form.html',
                          _finance_form_context('create', form_data=request.POST))
        record.save()
        messages.success(request, '已新增一筆收支紀錄。')
        return redirect('finance:finance_list')

    return render(request, 'finance/finance_form.html', _finance_form_context('create'))


@login_required
def finance_edit(request, pk):
    record = get_object_or_404(FinanceRecord, pk=pk)
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('finance:finance_list')

    if request.method == 'POST':
        errors = _apply_finance_form(request, record)
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'finance/finance_form.html',
                          _finance_form_context('edit', record=record, form_data=request.POST))
        record.save()
        messages.success(request, '已更新收支紀錄。')
        return redirect('finance:finance_list')

    form_data = {
        'type': record.type,
        'category': record.category,
        'amount': record.amount,
        'date': record.date.isoformat() if record.date else '',
        'description': record.description,
        'related_event': str(record.related_event_id or ''),
    }
    return render(request, 'finance/finance_form.html',
                  _finance_form_context('edit', record=record, form_data=form_data))


@login_required
def finance_delete(request, pk):
    """刪除收支紀錄限管理員（財務資料敏感，比照樂譜/團員/演出的刪除權限）。"""
    record = get_object_or_404(FinanceRecord, pk=pk)
    if not (request.user.is_superuser or request.user.is_admin_role):
        messages.error(request, '權限不足，僅管理員可刪除財務紀錄。')
        return redirect('finance:finance_list')

    if request.method == 'POST':
        record.delete()
        messages.success(request, '已刪除該筆收支紀錄。')
    return redirect('finance:finance_list')


@login_required
def receipt_download(request, pk):
    """下載收據掃描檔，幹部限定。"""
    record = get_object_or_404(FinanceRecord, pk=pk)
    if not request.user.is_officer:
        raise Http404
    if not record.attachment:
        raise Http404
    return FileResponse(
        record.attachment.open('rb'), as_attachment=True,
        filename=record.attachment.name.split('/')[-1],
    )


# ── 會費登記（MembershipFee）前端 ──────────────────────────────


@login_required
def fee_edit(request):
    """
    會費登記／編輯（幹部限定）。以 member + period(FeePeriod) 定位一筆 MembershipFee
    （get_or_create），設定狀態（已繳/未繳）與收款幹部；金額由期別固定金額快照，幹部不填。
    從會費繳納報表每列進入。
    """
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('finance:membership_fee_report')

    members = (
        User.objects.filter(is_active=True)
        .exclude(role__in=[User.Role.ADMIN, User.Role.GUEST])
        .order_by('instrument__category', 'instrument__name', 'name')
    )
    periods = FeePeriod.objects.all()

    if request.method == 'POST':
        member_id = request.POST.get('member', '')
        period_id = request.POST.get('period', '')
        paid = request.POST.get('paid') == 'on'
        paid_at_raw = request.POST.get('paid_at', '').strip()

        errors = []
        member = User.objects.filter(pk=member_id).first() if member_id else None
        period = FeePeriod.objects.filter(pk=period_id).first() if period_id else None
        if not member:
            errors.append('請選擇團員。')
        if not period:
            errors.append('請選擇期別。')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'finance/fee_form.html', {
                'members': members, 'periods': periods,
                'form_data': request.POST,
                'today': timezone.localdate().isoformat(),
            })

        paid_at = (parse_date(paid_at_raw) or timezone.localdate()) if paid else None
        S = MembershipFee.Status
        fee, _ = MembershipFee.objects.get_or_create(
            member=member, period=period, defaults={'amount': period.amount},
        )
        fee.amount = period.amount   # 金額快照：以期別當下的固定金額為準
        fee.status = S.PAID if paid else S.UNPAID
        fee.paid_at = paid_at
        fee.collected_by = request.user if paid else None
        fee.save()
        messages.success(request, f'已更新 {member.name} 的「{period}」會費紀錄。')
        return redirect(f"{reverse('finance:membership_fee_report')}?period={period.pk}")

    selected_member_id = request.GET.get('member', '')
    period_id = request.GET.get('period', '')
    fee = None
    if selected_member_id and period_id:
        fee = MembershipFee.objects.filter(member_id=selected_member_id, period_id=period_id).first()
    form_data = {
        'member': selected_member_id,
        'period': period_id,
        'paid': fee.is_paid if fee else False,
        'paid_at': fee.paid_at.isoformat() if fee and fee.paid_at else timezone.localdate().isoformat(),
    }
    return render(request, 'finance/fee_form.html', {
        'members': members, 'periods': periods,
        'form_data': form_data,
        'today': timezone.localdate().isoformat(),
    })
