import re

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

# 身分證字號格式：1 個英文字母 + 9 位數字。
# 刻意只驗格式、不驗檢查碼——居留證號等變體規則不同，驗太嚴會擋掉真實存在的號碼；
# 這裡的目的是擋打錯，不是做身分驗證。
_NATIONAL_ID_RE = re.compile(r'^[A-Za-z][0-9]{9}$')


def validate_national_id(value):
    if value and not _NATIONAL_ID_RE.match(value):
        raise ValidationError('身分證字號格式錯誤（應為 1 個英文字母加 9 位數字）。')


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
    birth_date = models.DateField('出生年月日', null=True, blank=True)
    address = models.CharField('住址', max_length=200, blank=True)
    national_id = models.CharField(
        '身分證字號', max_length=10, blank=True,
        validators=[validate_national_id],
        help_text='用途為每年的政府名單申報（見 DESIGN 附錄五 #4）',
    )
    # 使用者自己填的 LINE 帳號，與下面的 line_user_id（LINE Bot 取得的內部 id）是兩回事，不可混用
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
    instrument = models.ForeignKey(
        InstrumentType, on_delete=models.PROTECT,
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
    birth_date = models.DateField('出生年月日', null=True, blank=True)
    address = models.CharField('住址', max_length=200, blank=True)
    national_id = models.CharField(
        '身分證字號', max_length=10, blank=True, validators=[validate_national_id]
    )
    line_id = models.CharField('LINE ID', max_length=100, blank=True)
    status = models.CharField('狀態', max_length=10, choices=Status, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_registrations', verbose_name='審核幹部'
    )
    reviewed_at = models.DateTimeField('審核時間', null=True, blank=True)
    created_at = models.DateTimeField('申請時間', auto_now_add=True)

    class Meta:
        verbose_name = '校友報到申請'
        verbose_name_plural = '校友報到申請列表'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name}（{self.grad_year}屆）' if self.grad_year else self.name

    @property
    def masked_national_id(self):
        return mask_national_id(self.national_id)
