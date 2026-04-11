from django.conf import settings
from django.db import models


class FinanceRecord(models.Model):
    class Type(models.TextChoices):
        INCOME = 'income', '收入'
        EXPENSE = 'expense', '支出'

    class Category(models.TextChoices):
        VENUE = 'venue', '場地費'
        INSTRUCTOR = 'instructor', '師資費'
        INSTRUMENT_PURCHASE = 'instrument_purchase', '樂器購置費'
        INSTRUMENT_MAINTENANCE = 'instrument_maintenance', '樂器保養費'
        SCORE = 'score', '樂譜費'
        MEMBERSHIP = 'membership', '會費'
        OTHER = 'other', '其他'

    type = models.CharField('類型', max_length=10, choices=Type)
    category = models.CharField('分類', max_length=30, choices=Category)
    amount = models.DecimalField('金額', max_digits=10, decimal_places=0)
    date = models.DateField('日期')
    description = models.TextField('說明')
    attachment = models.FileField('收據掃描檔', upload_to='finance/', blank=True)
    related_event = models.ForeignKey(
        'events.PerformanceEvent', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='finance_records', verbose_name='關聯演出活動'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='finance_records', verbose_name='登記者'
    )

    class Meta:
        verbose_name = '財務紀錄'
        verbose_name_plural = '財務紀錄列表'
        ordering = ['-date']

    def __str__(self):
        return f'{self.date} {self.get_type_display()} {self.amount}'


class MembershipFee(models.Model):
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='membership_fees', verbose_name='團員'
    )
    period = models.CharField('繳費期別', max_length=50)
    amount = models.DecimalField('金額', max_digits=8, decimal_places=0)
    paid_at = models.DateField('繳費日期', null=True, blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='collected_fees', verbose_name='收款幹部'
    )

    class Meta:
        verbose_name = '會費繳納紀錄'
        verbose_name_plural = '會費繳納紀錄列表'
        ordering = ['-period', 'member__name']
        unique_together = [['member', 'period']]

    def __str__(self):
        return f'{self.member.name} {self.period}'

    @property
    def is_paid(self):
        return self.paid_at is not None
