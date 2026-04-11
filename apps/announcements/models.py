from django.conf import settings
from django.db import models


class Announcement(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = 'public', '公開'
        MEMBER_ONLY = 'member_only', '團員限定'
        OFFICER_ONLY = 'officer_only', '幹部限定'

    title = models.CharField('標題', max_length=200)
    content = models.TextField('內容')
    visibility = models.CharField('可見範圍', max_length=20, choices=Visibility, default=Visibility.MEMBER_ONLY)
    event_date = models.DateField('活動日期', null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='announcements', verbose_name='發布者'
    )
    published_at = models.DateTimeField('發布時間', null=True, blank=True)

    class Meta:
        verbose_name = '公告'
        verbose_name_plural = '公告列表'
        ordering = ['-published_at', '-id']

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.published_at is not None
