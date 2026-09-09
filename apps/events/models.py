import datetime as dt
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.public.models import Venue


def day_end(moment):
    """回傳 moment **當天**（本地時區）的 23:59:59.999999。

    #13-7 定案：請假／表態的截止點是「當天 23:59」，不是「開始時刻」。
    `Rehearsal` 只有單一 `date`、沒有結束時間，所以由**日期部分**推算——
    這是刻意的推導，不是欄位缺漏。

    用本地時區的日期而非 UTC 的：資料庫存 UTC，直接取 `.date()` 在台灣時間的
    清晨或深夜會算錯一天（例如台北 8/15 07:00 的排練，UTC 是 8/14 23:00）。
    """
    local = timezone.localtime(moment)
    return timezone.make_aware(
        dt.datetime.combine(local.date(), dt.time.max),
        timezone.get_current_timezone(),
    )


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
        CANCELLED = 'cancelled', '已取消'

    name = models.CharField('活動名稱', max_length=100)
    type = models.CharField('類型', max_length=20, choices=Type)
    performance_date = models.DateTimeField('演出日期時間')
    performance_venue = models.ForeignKey(
        Venue, on_delete=models.PROTECT,
        related_name='performance_events', verbose_name='演出場地'
    )
    status = models.CharField('狀態', max_length=20, choices=Status, default=Status.PLANNING)

    class Meta:
        verbose_name = '演出活動'
        verbose_name_plural = '演出活動列表'
        ordering = ['-performance_date']

    def __str__(self):
        return self.name

    @property
    def intent_deadline(self):
        """出席意願的表態截止：演出當天 23:59（與排練請假同一條規則，#13-7）。"""
        return day_end(self.performance_date)

    @property
    def intent_open(self):
        return timezone.now() <= self.intent_deadline


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

    @property
    def leave_deadline(self):
        """請假截止：排練當天 23:59（#13-7）。

        **不提供補請假路徑**——過了就是過了，狀態直接列為未出席（2026-08-12 定案，
        方向 c 團員事後補請、方向 d 幹部代登記皆不做）。
        """
        return day_end(self.date)

    @property
    def leave_open(self):
        return timezone.now() <= self.leave_deadline

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
    """演出出席：**事前意願（intent）與事後到場（attended）分開記錄**。

    刻意用「三態 intent ＋ 布林 attended」兩個欄位，理由各自獨立：

    - **不共用一個欄位**：共用會失去「說要來但沒到」這個最需要追蹤的情況。
    - **不再用兩個布林**（舊的 `confirmed` + `on_leave`）：那組合有四種狀態，其中
      「confirmed=True 且 on_leave=True」是矛盾的，而且沒有任何程式碼阻止它發生。
      三態用單一欄位承載，矛盾狀態直接不可表示。
    - **沒有紀錄 = 待確認**：團員預設不會有 attendance 列，統計時要從團員名單反推，
      不能只掃這張表——「都沒表態的人」正是幹部要追的對象（#13-5）。
    """

    class Intent(models.TextChoices):
        PENDING = 'pending', '待確認'
        CONFIRMED = 'confirmed', '確認參加'
        DECLINED = 'declined', '不參加'

    event = models.ForeignKey(
        PerformanceEvent, on_delete=models.CASCADE,
        related_name='attendances', verbose_name='演出活動'
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='performance_attendances', verbose_name='團員'
    )
    intent = models.CharField(
        '出席意願', max_length=10, choices=Intent, default=Intent.PENDING,
        help_text='團員事前表態；兩者都沒做的人維持「待確認」，由幹部聯繫'
    )
    intent_at = models.DateTimeField('表態時間', null=True, blank=True)
    decline_reason = models.TextField('無法參加的原因', blank=True)
    attended = models.BooleanField('是否到場', default=False, help_text='演出當天事後登記')
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
        related_name='part_assignments', verbose_name='團員'
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

    def __str__(self):
        return f'{self.setlist} - {self.member.name}'


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
    created_at = models.DateTimeField('申請時間', auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_leaves', verbose_name='審核幹部'
    )
    reviewed_at = models.DateTimeField('審核時間', null=True, blank=True)
    result_seen = models.BooleanField(
        '團員已讀審核結果', default=True,
        help_text='核准/拒絕時設為 False，團員在首頁看到通知後設回 True；預設 True 避免既有資料被當成新結果'
    )

    class Meta:
        verbose_name = '請假申請'
        verbose_name_plural = '請假申請列表'
        unique_together = [['member', 'rehearsal']]

    def __str__(self):
        return f'{self.member.name} - {self.rehearsal}'
