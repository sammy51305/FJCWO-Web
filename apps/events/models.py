import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.public.models import Venue


class PerformanceEvent(models.Model):
    class Type(models.TextChoices):
        CONCERT = 'concert', '音樂會'
        COMPETITION = 'competition', '比賽'
        RECORDING = 'recording', '錄音'
        JOINT = 'joint', '聯演'

    class Status(models.TextChoices):
        PLANNING = 'planning', '籌備中'
        CONFIRMED = 'confirmed', '確認'
        FINISHED = 'finished', '已結束'

    name = models.CharField('活動名稱', max_length=100)
    type = models.CharField('類型', max_length=20, choices=Type)
    performance_date = models.DateTimeField('演出日期時間')
    performance_venue = models.ForeignKey(
        Venue, on_delete=models.PROTECT,
        related_name='performance_events', verbose_name='演出場地'
    )
    status = models.CharField('狀態', max_length=20, choices=Status, default=Status.PLANNING)
    venue_time_slot = models.ForeignKey(
        'band_public.VenueTimeSlot', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='performance_events', verbose_name='演出時段'
    )

    class Meta:
        verbose_name = '演出活動'
        verbose_name_plural = '演出活動列表'
        ordering = ['-performance_date']

    def __str__(self):
        return self.name


class Rehearsal(models.Model):
    event = models.ForeignKey(
        PerformanceEvent, on_delete=models.CASCADE,
        related_name='rehearsals', verbose_name='所屬演出活動'
    )
    sequence = models.PositiveSmallIntegerField('第幾次排練')
    date = models.DateTimeField('排練日期時間')
    venue = models.ForeignKey(
        Venue, on_delete=models.PROTECT,
        related_name='rehearsals', verbose_name='排練場地'
    )
    summary_progress = models.TextField('今日進度', blank=True)
    summary_improve = models.TextField('待改進事項', blank=True)
    summary_next = models.TextField('下次排練重點', blank=True)
    summary_notes = models.TextField('給團員備註', blank=True)
    summary_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rehearsal_summaries', verbose_name='填寫者'
    )
    time_slot = models.ForeignKey(
        'band_public.VenueTimeSlot', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rehearsals', verbose_name='時段'
    )

    class Meta:
        verbose_name = '排練'
        verbose_name_plural = '排練列表'
        ordering = ['event', 'sequence']
        unique_together = [['event', 'sequence']]

    def __str__(self):
        return f'{self.event.name} 第{self.sequence}次排練'


class RehearsalQRToken(models.Model):
    rehearsal = models.OneToOneField(
        Rehearsal, on_delete=models.CASCADE,
        related_name='qr_token', verbose_name='所屬排練'
    )
    token = models.UUIDField('Token', default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField('建立時間', auto_now_add=True)
    expires_at = models.DateTimeField('到期時間')
    is_active = models.BooleanField('是否啟用', default=True)

    class Meta:
        verbose_name = 'QR Code Token'
        verbose_name_plural = 'QR Code Token 列表'

    def __str__(self):
        return f'{self.rehearsal} QR Token'

    def is_valid(self):
        return self.is_active and timezone.now() <= self.expires_at


class GuestMember(models.Model):
    name = models.CharField('姓名', max_length=50)
    instrument = models.ForeignKey(
        'accounts.InstrumentType', on_delete=models.PROTECT, verbose_name='樂器'
    )
    section = models.ForeignKey(
        'accounts.SectionType', on_delete=models.PROTECT, verbose_name='聲部'
    )
    from_band = models.CharField('來自樂團', max_length=100, blank=True)
    event = models.ForeignKey(
        PerformanceEvent, on_delete=models.CASCADE,
        related_name='guest_members', verbose_name='參與演出'
    )
    phone = models.CharField('聯絡電話', max_length=20, blank=True)

    class Meta:
        verbose_name = '客座團員'
        verbose_name_plural = '客座團員列表'

    def __str__(self):
        return f'{self.name}（{self.from_band}）'


class RehearsalAttendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', '出席'
        LEAVE = 'leave', '請假'
        ABSENT = 'absent', '缺席'

    rehearsal = models.ForeignKey(
        Rehearsal, on_delete=models.CASCADE,
        related_name='attendances', verbose_name='排練'
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='rehearsal_attendances', verbose_name='團員'
    )
    status = models.CharField('狀態', max_length=10, choices=Status, default=Status.ABSENT)
    checked_in_at = models.DateTimeField('簽到時間', null=True, blank=True)

    class Meta:
        verbose_name = '排練出席紀錄'
        verbose_name_plural = '排練出席紀錄列表'
        unique_together = [['rehearsal', 'member']]

    def __str__(self):
        return f'{self.rehearsal} - {self.member.name}'


class PerformanceAttendance(models.Model):
    event = models.ForeignKey(
        PerformanceEvent, on_delete=models.CASCADE,
        related_name='attendances', verbose_name='演出活動'
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='performance_attendances', verbose_name='團員'
    )
    confirmed = models.BooleanField('是否到場', default=False)
    checked_in_at = models.DateTimeField('確認到場時間', null=True, blank=True)
    notes = models.TextField('備註', blank=True)

    class Meta:
        verbose_name = '演出出席確認'
        verbose_name_plural = '演出出席確認列表'
        unique_together = [['event', 'member']]

    def __str__(self):
        return f'{self.event.name} - {self.member.name}'


class Setlist(models.Model):
    event = models.ForeignKey(
        PerformanceEvent, on_delete=models.CASCADE,
        related_name='setlists', verbose_name='演出活動'
    )
    score = models.ForeignKey(
        'scores.Score', on_delete=models.PROTECT,
        related_name='setlists', verbose_name='曲目'
    )
    order = models.PositiveSmallIntegerField('演出順序')

    class Meta:
        verbose_name = '演出曲目'
        verbose_name_plural = '演出曲目列表'
        ordering = ['event', 'order']
        unique_together = [['event', 'order']]

    def __str__(self):
        return f'{self.event.name} #{self.order} {self.score.title}'


class PartAssignment(models.Model):
    setlist = models.ForeignKey(
        Setlist, on_delete=models.CASCADE,
        related_name='part_assignments', verbose_name='演出曲目'
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='part_assignments', verbose_name='正式團員'
    )
    guest_member = models.ForeignKey(
        GuestMember, on_delete=models.CASCADE,
        null=True, blank=True, related_name='part_assignments', verbose_name='客座團員'
    )
    instrument = models.ForeignKey(
        'accounts.InstrumentType', on_delete=models.PROTECT, verbose_name='樂器'
    )
    section = models.ForeignKey(
        'accounts.SectionType', on_delete=models.PROTECT, verbose_name='聲部'
    )
    score_part = models.ForeignKey(
        'scores.Score', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_parts', verbose_name='對應分譜'
    )

    class Meta:
        verbose_name = '分譜分配'
        verbose_name_plural = '分譜分配列表'

    def clean(self):
        if self.member and self.guest_member:
            raise ValidationError('正式團員與客座團員只能填一個。')
        if not self.member and not self.guest_member:
            raise ValidationError('正式團員與客座團員必須填一個。')

    def __str__(self):
        person = self.member.name if self.member else self.guest_member.name
        return f'{self.setlist} - {person}'


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '待審核'
        APPROVED = 'approved', '核准'
        REJECTED = 'rejected', '拒絕'

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='leave_requests', verbose_name='申請者'
    )
    rehearsal = models.ForeignKey(
        Rehearsal, on_delete=models.CASCADE,
        related_name='leave_requests', verbose_name='排練'
    )
    reason = models.TextField('請假原因')
    status = models.CharField('狀態', max_length=10, choices=Status, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_leaves', verbose_name='審核幹部'
    )
    reviewed_at = models.DateTimeField('審核時間', null=True, blank=True)

    class Meta:
        verbose_name = '請假申請'
        verbose_name_plural = '請假申請列表'
        unique_together = [['member', 'rehearsal']]

    def __str__(self):
        return f'{self.member.name} - {self.rehearsal}'
