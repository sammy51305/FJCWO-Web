import re

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from .fields import EncryptedDateField, EncryptedTextField

# 接受兩種證號（2026-09-07 放寬）：
#   中華民國身分證：1 個英文字母 + 9 位數字，如 A123456789
#   居留證統一證號：2 個英文字母 + 8 位數字，如 AB12345678
# 團裡有港澳團員，在台長住者持居留證統一證號，只收身分證會把他們擋在申請頁外。
# 刻意只驗格式、不驗檢查碼——目的是擋打錯，不是做身分驗證。
# 兩者皆無的人由幹部在後台留空：公開申請頁維持必填、幹部端允許留空——
# 公開頁擋的是隨手亂填，幹部端擋的是本來就不存在的東西。
_NATIONAL_ID_RES = (
    re.compile(r'^[A-Za-z][0-9]{9}$'),      # 身分證
    re.compile(r'^[A-Za-z]{2}[0-9]{8}$'),   # 居留證
)


def validate_national_id(value):
    if value and not any(pattern.match(value) for pattern in _NATIONAL_ID_RES):
        raise ValidationError(
            '證號格式錯誤（身分證為 1 個英文字母加 9 位數字，居留證為 2 個英文字母加 8 位數字）。'
        )


def mask_national_id(value):
    """身分證字號遮蔽成只剩末四碼，如 A123456789 → ******6789。

    列表與報表一律用這個，不顯示完整值（見 DESIGN 附錄五 #13-1 決定一）。
    """
    if not value:
        return ''
    return '*' * max(len(value) - 4, 0) + value[-4:]


class InstrumentFamily(models.Model):
    class Category(models.TextChoices):
        WOODWIND = 'woodwind', '木管'
        BRASS = 'brass', '銅管'
        PERCUSSION = 'percussion', '打擊'
        OTHER = 'other', '其他'

    name = models.CharField('族群名稱', max_length=50, unique=True)
    category = models.CharField('分類', max_length=20, choices=Category)

    class Meta:
        verbose_name = '樂器族群'
        verbose_name_plural = '樂器族群列表'
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name}（{self.get_category_display()}）'


class InstrumentType(models.Model):
    name = models.CharField('樂器名稱', max_length=50, unique=True)
    family = models.ForeignKey(
        InstrumentFamily, on_delete=models.PROTECT,
        verbose_name='族群', related_name='instruments'
    )

    class Meta:
        verbose_name = '樂器'
        verbose_name_plural = '樂器列表'
        ordering = ['family__category', 'family__name', 'name']

    def __str__(self):
        return self.name


class SectionType(models.Model):
    name = models.CharField('聲部名稱', max_length=50, unique=True)

    class Meta:
        verbose_name = '聲部'
        verbose_name_plural = '聲部列表'

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        MEMBER = 'member', '團員'
        OFFICER = 'officer', '幹部'
        ADMIN = 'admin', '管理員'
        GUEST = 'guest', '槍手'

    name = models.CharField('真實姓名', max_length=50)
    # email 可空：槍手（role=GUEST）常沒有 email。保留 unique（Postgres 允許多個 NULL 不衝突），
    # 所以「無 email」必須存成 NULL，不能存空字串 ''（多個 '' 會違反 unique）。
    email = models.EmailField('Email', unique=True, null=True, blank=True)
    role = models.CharField('角色', max_length=10, choices=Role, default=Role.MEMBER)
    instrument = models.ForeignKey(
        InstrumentFamily, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='樂器'
    )
    section = models.ForeignKey(
        SectionType, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='聲部'
    )
    grad_year = models.PositiveSmallIntegerField('畢業年份', null=True, blank=True)
    phone = models.CharField('手機', max_length=20, blank=True)
    from_band = models.CharField('來自樂團', max_length=100, blank=True, help_text='僅槍手（role=guest）適用')
    # ── 以下三個是敏感個資，列表與報表不顯示完整值（見 DESIGN 附錄五 #13-1 決定一）──
    # 這三個欄位在 DB 裡是密文（#13-1 決定二）。view / template / form 用起來與一般欄位無異，
    # 加解密只發生在 DB 邊界，見 apps/accounts/fields.py。
    birth_date = EncryptedDateField('出生年月日', null=True, blank=True)
    address = EncryptedTextField('住址', form_max_length=200, blank=True)
    national_id = EncryptedTextField(
        '身分證字號／居留證號', form_max_length=10, blank=True,
        validators=[validate_national_id],
        help_text='用途為每年的政府名單申報（見 DESIGN 附錄五 #4）',
    )
    # 使用者自己填的 LINE 帳號，與下面的 line_user_id（LINE Bot 取得的內部 id）是兩回事，不可混用
    # 入團申請表單的「輔大入學年 / 就讀科系」原文照存（如「99級/織品系」）。
    # 刻意不自動拆成 grad_year——那一格塞了兩種資訊、實際填法有六七種變體
    # （有人只填數字、有人填「非校友」、有人填兩個學位），自動解析必然產生錯資料，
    # 而錯資料比沒資料難處理。grad_year（西元畢業年份）維持原語意、匯入時留空。
    alumni_info = models.CharField('入學年／科系', max_length=100, blank=True)
    line_id = models.CharField('LINE ID', max_length=100, blank=True)
    line_user_id = models.CharField('LINE User ID', max_length=100, blank=True)
    must_change_password = models.BooleanField(
        '需重設密碼', default=False,
        help_text='幹部代為建立帳號時設為 True，登入後會被強制導向設定新密碼頁面'
    )

    REQUIRED_FIELDS = ['name']

    class Meta:
        verbose_name = '使用者'
        verbose_name_plural = '使用者列表'

    def __str__(self):
        return f'{self.name} ({self.username})'

    def save(self, *args, **kwargs):
        # role=admin 時取得 Django Admin 完整控制權（is_superuser 授予所有 model 權限）
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        elif self.is_superuser:
            self.is_staff = True
        super().save(*args, **kwargs)

    @property
    def is_officer(self):
        return self.is_superuser or self.role in (self.Role.OFFICER, self.Role.ADMIN)

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_guest(self):
        return self.role == self.Role.GUEST

    @property
    def masked_national_id(self):
        """給列表／報表用的遮蔽值。做成 property 而非在各 template 自己遮，
        是為了讓「不顯示完整值」只有一份實作，日後新增頁面不會漏（DESIGN #13-1 決定一）。"""
        return mask_national_id(self.national_id)


class Registration(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '待審核'
        APPROVED = 'approved', '已核准'
        REJECTED = 'rejected', '已拒絕'

    name = models.CharField('姓名', max_length=50)
    # 樂器、聲部、畢業年份自 2026-08-29 起改為選填（#13-1）；
    # 依樂器分組的頁面因此要能處理 null（通訊錄 §4.2 的「未分類」、演出分譜 §4.19 的守衛）。
    # 2026-09-07 由 InstrumentType（細）改指 InstrumentFamily（族群，粗）：入團申請表單填的是
    # 「豎笛」「薩克斯風」這種粗分類，對不到 Bb 豎笛／中音薩克斯風等細項，族群這層剛好一對一。
    # 另兩個好處：與 User.instrument 同一層（核准建帳號時不必再 .family 轉換）、
    # 分譜（Score.instrument）仍用 InstrumentType 保有細分——Bb 豎笛與低音豎笛是不同分譜，
    # 那層不能合併。
    instrument = models.ForeignKey(
        InstrumentFamily, on_delete=models.PROTECT,
        null=True, blank=True, verbose_name='樂器'
    )
    section = models.ForeignKey(
        SectionType, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='聲部'
    )
    grad_year = models.PositiveSmallIntegerField('畢業年份', null=True, blank=True)
    phone = models.CharField('手機', max_length=20, blank=True)
    email = models.EmailField('Email')
    # ── 敏感個資，比照 User，核准建帳號時整批帶過去 ──
    # 同 User：DB 存密文（#13-1 決定二）
    birth_date = EncryptedDateField('出生年月日', null=True, blank=True)
    address = EncryptedTextField('住址', form_max_length=200, blank=True)
    national_id = EncryptedTextField(
        '身分證字號／居留證號', form_max_length=10, blank=True,
        validators=[validate_national_id]
    )
    # 入團申請表單的「輔大入學年 / 就讀科系」原文照存（如「99級/織品系」）。
    # 刻意不自動拆成 grad_year——那一格塞了兩種資訊、實際填法有六七種變體
    # （有人只填數字、有人填「非校友」、有人填兩個學位），自動解析必然產生錯資料，
    # 而錯資料比沒資料難處理。grad_year（西元畢業年份）維持原語意、匯入時留空。
    alumni_info = models.CharField('入學年／科系', max_length=100, blank=True)
    line_id = models.CharField('LINE ID', max_length=100, blank=True)
    status = models.CharField('狀態', max_length=10, choices=Status, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_registrations', verbose_name='審核幹部'
    )
    reviewed_at = models.DateTimeField('審核時間', null=True, blank=True)
    created_at = models.DateTimeField('申請時間', auto_now_add=True)

    class Meta:
        verbose_name = '入團申請'
        verbose_name_plural = '入團申請列表'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name}（{self.grad_year}屆）' if self.grad_year else self.name

    @property
    def masked_national_id(self):
        return mask_national_id(self.national_id)
