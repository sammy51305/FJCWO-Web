from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.notifications.utils import push_line_message

from .models import Announcement


def _visible_visibilities(user):
    """回傳使用者可見的 visibility，依列表頁「由上而下」的顯示順序排列。

    順序固定為 幹部限定 → 團員限定 → 公開；使用者看不到的那幾層直接不在清單裡，
    所以列表頁的分區與可見性判斷共用同一份規則，不會各寫一套而走鐘。
    """
    if not user.is_authenticated:
        return (Announcement.Visibility.PUBLIC,)
    if user.is_officer:
        return (
            Announcement.Visibility.OFFICER_ONLY,
            Announcement.Visibility.MEMBER_ONLY,
            Announcement.Visibility.PUBLIC,
        )
    return (Announcement.Visibility.MEMBER_ONLY, Announcement.Visibility.PUBLIC)


def _visible_announcements(user):
    """回傳目前使用者可見的已發布公告 QuerySet。"""
    qs = Announcement.objects.filter(published_at__isnull=False).select_related('created_by')
    return qs.filter(visibility__in=_visible_visibilities(user))


def announcement_list(request):
    """公告列表：由上而下分幹部限定／團員限定／公開三區（見 DESIGN 附錄五 #13-3）。"""
    announcements = list(_visible_announcements(request.user))
    labels = dict(Announcement.Visibility.choices)
    sections = [
        {
            'visibility': visibility,
            'label': labels[visibility],
            'items': [ann for ann in announcements if ann.visibility == visibility],
        }
        for visibility in _visible_visibilities(request.user)
    ]
    return render(request, 'announcements/announcement_list.html', {
        'sections': sections,
    })


def announcement_detail(request, pk):
    qs = _visible_announcements(request.user)
    announcement = get_object_or_404(qs, pk=pk)
    return render(request, 'announcements/announcement_detail.html', {
        'announcement': announcement,
    })


@login_required
def announcement_manage(request, pk=None):
    """幹部公告管理頁（含草稿）。"""
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('announcements:announcement_list')

    announcements = Announcement.objects.select_related('created_by').order_by('-id')
    return render(request, 'announcements/announcement_manage.html', {
        'announcements': announcements,
    })


@login_required
def announcement_create(request):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('announcements:announcement_list')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        visibility = request.POST.get('visibility', '')
        event_date = request.POST.get('event_date', '').strip() or None

        errors = []
        if not title:
            errors.append('請填寫標題。')
        if not content:
            errors.append('請填寫內容。')
        if visibility not in Announcement.Visibility.values:
            errors.append('請選擇可見範圍。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            Announcement.objects.create(
                title=title,
                content=content,
                visibility=visibility,
                event_date=event_date,
                created_by=request.user,
            )
            messages.success(request, f'公告《{title}》已儲存為草稿。')
            return redirect('announcements:announcement_manage')

    return render(request, 'announcements/announcement_form.html', {
        'action': 'create',
        'visibility_choices': Announcement.Visibility.choices,
    })


@login_required
def announcement_edit(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('announcements:announcement_list')

    announcement = get_object_or_404(Announcement, pk=pk)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        visibility = request.POST.get('visibility', '')
        event_date = request.POST.get('event_date', '').strip() or None

        errors = []
        if not title:
            errors.append('請填寫標題。')
        if not content:
            errors.append('請填寫內容。')
        if visibility not in Announcement.Visibility.values:
            errors.append('請選擇可見範圍。')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            announcement.title = title
            announcement.content = content
            announcement.visibility = visibility
            announcement.event_date = event_date
            announcement.save()
            messages.success(request, f'公告《{title}》已更新。')
            return redirect('announcements:announcement_manage')

    return render(request, 'announcements/announcement_form.html', {
        'action': 'edit',
        'announcement': announcement,
        'visibility_choices': Announcement.Visibility.choices,
    })


@login_required
def announcement_delete(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('announcements:announcement_list')

    if request.method != 'POST':
        return redirect('announcements:announcement_manage')

    announcement = get_object_or_404(Announcement, pk=pk)
    title = announcement.title
    announcement.delete()
    messages.success(request, f'公告《{title}》已刪除。')
    return redirect('announcements:announcement_manage')


@login_required
def announcement_publish(request, pk):
    if not request.user.is_officer:
        messages.error(request, '權限不足。')
        return redirect('announcements:announcement_list')

    if request.method != 'POST':
        return redirect('announcements:announcement_manage')

    announcement = get_object_or_404(Announcement, pk=pk)
    if announcement.is_published:
        announcement.published_at = None
        announcement.save()
        messages.success(request, f'公告《{announcement.title}》已取消發布。')
    else:
        announcement.published_at = timezone.now()
        announcement.save()
        messages.success(request, f'公告《{announcement.title}》已發布。')
        if announcement.visibility != announcement.Visibility.OFFICER_ONLY:
            push_line_message(f'📢 新公告：{announcement.title}\n請登入系統查看詳情。')
    return redirect('announcements:announcement_manage')
