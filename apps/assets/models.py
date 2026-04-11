from django.conf import settings
from django.db import models


class BandProperty(models.Model):
    class Category(models.TextChoices):
        INSTRUMENT = 'instrument', '樂器'
        STAND = 'stand', '譜架'
        AUDIO = 'audio', '音響設備'
        UNIFORM = 'uniform', '制服'
        OTHER = 'other', '其他'

    class Condition(models.TextChoices):
        GOOD = 'good', '良好'
        NEEDS_MAINTENANCE = 'needs_maintenance', '需保養'
        IN_REPAIR = 'in_repair', '送修中'

    name = models.CharField('財產名稱', max_length=100)
    category = models.CharField('類別', max_length=20, choices=Category)
    purchase_date = models.DateField('購入日期', null=True, blank=True)
    purchase_cost = models.DecimalField('購入費用', max_digits=10, decimal_places=0, null=True, blank=True)
    condition = models.CharField('狀態', max_length=20, choices=Condition, default=Condition.GOOD)
    storage_location = models.CharField('保管位置', max_length=100, blank=True)
    contact_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='managed_properties', verbose_name='負責幹部'
    )
    notes = models.TextField('備註', blank=True)

    class Meta:
        verbose_name = '公用財產'
        verbose_name_plural = '公用財產列表'
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name}（{self.get_category_display()}）'


class AssetBorrow(models.Model):
    asset = models.ForeignKey(
        BandProperty, on_delete=models.CASCADE,
        related_name='borrows', verbose_name='借用財產'
    )
    borrower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='borrows', verbose_name='借用者'
    )
    borrowed_at = models.DateField('借出日期')
    due_date = models.DateField('預計歸還日期', null=True, blank=True)
    returned_at = models.DateField('實際歸還日期', null=True, blank=True)
    notes = models.TextField('備註', blank=True)

    class Meta:
        verbose_name = '財產借用紀錄'
        verbose_name_plural = '財產借用紀錄列表'
        ordering = ['-borrowed_at']

    def __str__(self):
        return f'{self.borrower.name} 借用 {self.asset.name}'

    @property
    def is_returned(self):
        return self.returned_at is not None


class InstrumentMaintenance(models.Model):
    asset = models.ForeignKey(
        BandProperty, on_delete=models.CASCADE,
        related_name='maintenances', verbose_name='樂器'
    )
    date = models.DateField('保養日期')
    description = models.TextField('保養內容')
    cost = models.DecimalField('費用', max_digits=10, decimal_places=0, null=True, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='maintained_instruments', verbose_name='負責人'
    )

    class Meta:
        verbose_name = '樂器保養紀錄'
        verbose_name_plural = '樂器保養紀錄列表'
        ordering = ['-date']

    def __str__(self):
        return f'{self.asset.name} {self.date} 保養'
