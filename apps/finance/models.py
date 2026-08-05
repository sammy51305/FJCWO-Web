from django.conf import settings
from django.core.validators import MinValueValidator
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
    amount = models.DecimalField('金額', max_digits=10, decimal_places=0,
                                 validators=[MinValueValidator(1)])
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


class FeePeriod(models.Model):
    """
    會費期別主檔（附錄五 §9 P1）。幹部/管理員建立某一期，金額全團固定、繳費時段不定可調。
    建立後每位在團團員對這期天然就是「應繳未繳」（報表以團員 × 期別 join 導出，不預建列）。
    """
    class Term(models.TextChoices):
        FIRST = 'first', '上期'
        SECOND = 'second', '下期'

    year = models.PositiveIntegerField('年份')
    term = models.CharField('期', max_length=10, choices=Term)
    amount = models.DecimalField('團費金額', max_digits=8, decimal_places=0,
                                 validators=[MinValueValidator(1)])
    start_date = models.DateField('繳費開始日', null=True, blank=True)
    end_date = models.DateField('繳費截止日', null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_fee_periods', verbose_name='建立者'
    )

    class Meta:
        verbose_name = '會費期別'
        verbose_name_plural = '會費期別列表'
        ordering = ['-year', 'term']
        unique_together = [['year', 'term']]

    def __str__(self):
        return f'{self.year} {self.get_term_display()}'


class MembershipFee(models.Model):
    class Status(models.TextChoices):
        UNPAID = 'unpaid', '應繳未繳'
        REPORTED = 'reported', '待確認'
        PAID = 'paid', '已繳'
        VOID = 'void', '作廢'

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', '現金'
        TRANSFER = 'transfer', '轉帳'

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='membership_fees', verbose_name='團員'
    )
    period = models.ForeignKey(
        FeePeriod, on_delete=models.PROTECT,
        related_name='fees', verbose_name='期別'
    )
    amount = models.DecimalField('金額', max_digits=8, decimal_places=0,
                                 validators=[MinValueValidator(1)],
                                 help_text='繳費當下自期別金額快照，之後改期別金額不竄改此筆')
    status = models.CharField('狀態', max_length=10, choices=Status, default=Status.UNPAID)
    payment_method = models.CharField('繳費方式', max_length=10, choices=PaymentMethod,
                                      default=PaymentMethod.CASH)
    account_last5 = models.CharField('匯款帳號末五碼', max_length=5, blank=True,
                                     help_text='轉帳繳費時填，供財務對帳；確認後可清除')
    paid_at = models.DateField('繳費日期', null=True, blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='collected_fees', verbose_name='收款幹部（現金）'
    )
    finance_record = models.ForeignKey(
        'FinanceRecord', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='membership_fee', verbose_name='對應收入紀錄',
        help_text='確認繳費時自動產生的那筆收支明細收入，作廢/退回時連動移除'
    )
    result_seen = models.BooleanField(
        '團員已讀審核結果', default=True,
        help_text='幹部確認/作廢時設為 False，團員在首頁看到通知後設回 True；預設 True 避免既有資料被當成新結果'
    )

    class Meta:
        verbose_name = '會費繳納紀錄'
        verbose_name_plural = '會費繳納紀錄列表'
        ordering = ['-period__year', '-period__term', 'member__name']
        unique_together = [['member', 'period']]

    def __str__(self):
        return f'{self.member.name} {self.period}'

    @property
    def is_paid(self):
        return self.status == self.Status.PAID


class PaymentConfig(models.Model):
    """
    轉帳收款設定（附錄五 §9 P4，單一列 pk=1，比照 CharterContent）。
    幹部上傳樂團帳戶 QRCode 與帳號文字，供團員掃碼轉帳；用 FileField 存圖檔（免 Pillow 依賴）。
    """
    qrcode = models.FileField('收款 QR Code 圖檔', upload_to='payment/', blank=True)
    account_info = models.TextField('轉帳帳號資訊', blank=True,
                                    help_text='銀行/分行、戶名、帳號等文字，顯示在申報頁供團員轉帳')
    updated_at = models.DateTimeField('更新時間', auto_now=True)

    class Meta:
        verbose_name = '轉帳收款設定'
        verbose_name_plural = '轉帳收款設定'

    def __str__(self):
        return '轉帳收款設定'
