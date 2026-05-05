from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import AboutSection, CharterContent


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
