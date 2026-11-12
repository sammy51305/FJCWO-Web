import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


def _new_category_code():
    """幹部在後台新增的分類自動配一個代碼（內建分類的代碼由資料遷移寫入，見 0012）。"""
    return f'c{uuid.uuid4().hex[:10]}'


class FinanceCategory(models.Model):
    """
    收支分類（可由幹部／管理員在後台自行增減，2026-11 由寫死的 TextChoices 改為資料表）。

    - 紀錄以 `code`（不會變的代碼）指向分類，所以改名不影響舊紀錄。
    - 已有紀錄用的分類刪不掉（PROTECT）：不想再用就取消「啟用」，舊紀錄照常顯示。
    - 「團費」是系統分類（is_system）：確認繳費時系統自動寫入，不能改名、停用或刪除。
    """
    class Kind(models.TextChoices):
        INCOME = 'income', '僅收入'
        EXPENSE = 'expense', '僅支出'
        BOTH = 'both', '收入與支出皆可'

    MEMBERSHIP_CODE = 'membership'

    code = models.CharField('代碼', max_length=30, unique=True, editable=False,
                            default=_new_category_code)
    name = models.CharField('名稱', max_length=30, unique=True)
    kind = models.CharField('適用', max_length=10, choices=Kind, default=Kind.BOTH)
    sort_order = models.PositiveIntegerField('排序', default=100,
                                             help_text='數字小的排前面')
    is_active = models.BooleanField('啟用', default=True,
                                    help_text='取消勾選＝新增收支時不再列出，舊紀錄不受影響')
    is_system = models.BooleanField('系統分類', default=False, editable=False)

    class Meta:
        verbose_name = '收支分類'
        verbose_name_plural = '收支分類列表'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name

    def fits(self, type_):
        """這個分類能不能用在 type_（'income' / 'expense'）的收支上。"""
        return self.kind == self.Kind.BOTH or self.kind == type_

    @classmethod
    def membership(cls):
        """團費分類。資料遷移已建好；get_or_create 是保險（例如資料被清空的測試環境）。"""
        obj, _ = cls.objects.get_or_create(
            code=cls.MEMBERSHIP_CODE,
            defaults={'name': '團費', 'kind': cls.Kind.INCOME, 'sort_order': 70,
                      'is_system': True},
        )
        return obj


class FinanceRecord(models.Model):
    class Type(models.TextChoices):
        INCOME = 'income', '收入'
        EXPENSE = 'expense', '支出'

    type = models.CharField('類型', max_length=10, choices=Type)
    # to_field='code' + db_column='category'：資料庫裡仍是原本那欄，存的值（venue、membership…）不變
    category = models.ForeignKey(
        FinanceCategory, to_field='code', db_column='category',
        on_delete=models.PROTECT, related_name='records', verbose_name='分類',
    )
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
    團費期別主檔（附錄五 §9 P1）。幹部/管理員建立某一期，金額全團固定、繳費時段不定可調。
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
    student_amount = models.DecimalField(
        '學生團費', max_digits=8, decimal_places=0, null=True, blank=True,
        validators=[MinValueValidator(1)],
        help_text='學生（User.is_student）適用的金額；留空＝學生也繳一般金額'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_fee_periods', verbose_name='建立者'
    )

    class Meta:
        verbose_name = '團費期別'
        verbose_name_plural = '團費期別列表'
        ordering = ['-year', 'term']
        unique_together = [['year', 'term']]

    def __str__(self):
        return f'{self.year} {self.get_term_display()}'

    def amount_for(self, member):
        """這位團員這期應繳多少。全系統「金額快照」一律走這裡，不要直接取 self.amount——
        否則學生的金額會在幹部登記、團員申報、幹部確認任一步被蓋回一般金額。"""
        if self.student_amount and getattr(member, 'is_student', False):
            return self.student_amount
        return self.amount


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
        verbose_name = '團費收繳紀錄'
        verbose_name_plural = '團費收繳紀錄列表'
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
    幹部設定樂團收款帳戶（QRCode 圖檔＋銀行代號/名稱/戶名/帳號），供團員在申報頁選「轉帳」時掃碼或複製匯款。
    用 FileField 存 QRCode 圖檔（免 Pillow 依賴）。帳號存檔時自動去除 dash 與空白，
    確保複製出來即為可直接輸入銀行 App 的純數字（見 save()）。
    """
    qrcode = models.FileField('收款 QR Code 圖檔', upload_to='payment/', blank=True)
    bank_code = models.CharField('銀行代號', max_length=10, blank=True, default='',
                                 help_text='轉帳用的金融機構代號，如 004；顯示在申報頁供團員複製')
    bank_name = models.CharField('銀行名稱', max_length=50, blank=True, default='',
                                 help_text='對應銀行名稱，如 臺灣銀行；幹部選代號時自動帶入')
    account_name = models.CharField('戶名', max_length=100, blank=True, default='',
                                    help_text='收款帳戶戶名，供團員匯款前確認收款單位')
    account_number = models.CharField('帳號', max_length=30, blank=True, default='',
                                      help_text='收款帳號；存檔時自動去除 dash 與空白')
    updated_at = models.DateTimeField('更新時間', auto_now=True)

    class Meta:
        verbose_name = '轉帳收款設定'
        verbose_name_plural = '轉帳收款設定'

    def save(self, *args, **kwargs):
        # 帳號一律 normalize 成純數字（去 dash 與空白），複製出來即可直接匯款
        if self.account_number:
            self.account_number = self.account_number.replace('-', '').replace(' ', '').strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return '轉帳收款設定'
