from django.contrib.auth.models import AbstractUser
from django.db import models


class InstrumentType(models.Model):
    class Category(models.TextChoices):
        WOODWIND = 'woodwind', '木管'
        BRASS = 'brass', '銅管'
        PERCUSSION = 'percussion', '打擊'
        OTHER = 'other', '其他'

    name = models.CharField('樂器名稱', max_length=50, unique=True)
    category = models.CharField('分類', max_length=20, choices=Category)

    class Meta:
        verbose_name = '樂器'
        verbose_name_plural = '樂器列表'
        ordering = ['category', 'name']

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

    name = models.CharField('真實姓名', max_length=50)
    email = models.EmailField('Email', unique=True)
    role = models.CharField('角色', max_length=10, choices=Role, default=Role.MEMBER)
    instrument = models.ForeignKey(
        InstrumentType, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='樂器'
    )
    section = models.ForeignKey(
        SectionType, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='聲部'
    )
    grad_year = models.PositiveSmallIntegerField('畢業年份', null=True, blank=True)
    phone = models.CharField('電話', max_length=20, blank=True)
    line_user_id = models.CharField('LINE User ID', max_length=100, blank=True)

    REQUIRED_FIELDS = ['name', 'email']

    class Meta:
        verbose_name = '使用者'
        verbose_name_plural = '使用者列表'

    def __str__(self):
        return f'{self.name} ({self.username})'

    def save(self, *args, **kwargs):
        # role=admin 或 superuser 時自動取得 Django Admin 存取權
        if self.is_superuser or self.role == self.Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)

    @property
    def is_officer(self):
        return self.is_superuser or self.role in (self.Role.OFFICER, self.Role.ADMIN)

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN


class Registration(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '待審核'
        APPROVED = 'approved', '已核准'
        REJECTED = 'rejected', '已拒絕'

    name = models.CharField('姓名', max_length=50)
    instrument = models.ForeignKey(
        InstrumentType, on_delete=models.PROTECT, verbose_name='樂器'
    )
    grad_year = models.PositiveSmallIntegerField('畢業年份')
    phone = models.CharField('電話', max_length=20, blank=True)
    email = models.EmailField('Email')
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
        return f'{self.name}（{self.grad_year}屆）'
