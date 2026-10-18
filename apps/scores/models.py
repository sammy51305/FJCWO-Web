import re
from urllib.parse import urlparse, urlunparse

from django.core.exceptions import ValidationError
from django.db import models

# 樂譜檔案存放在樂團的 Google Drive：Render 免費方案的磁碟在重新部署時會清空，
# 系統不再自己存檔，只記連結。限定 Google 網域，避免把團員導到任意外站。
DRIVE_HOSTS = {'drive.google.com', 'docs.google.com'}

# 「其他」族群裡的固定樂器：選它代表「特殊樂器，由譜務在 custom_instrument_name 手填名稱」。
CUSTOM_INSTRUMENT_NAME = '其他（手填）'


def normalize_drive_url(value):
    """
    去頭尾空白，並拿掉網址裡的瀏覽器帳號編號 `/u/數字/`。

    從瀏覽器複製的連結常帶 `/drive/u/1/folders/…`（`1` 是「這個瀏覽器裡的第二個 Google 帳號」），
    別人點進去可能被帶去錯的帳號或要求選帳號。連結一律存成不帶帳號編號的版本。
    只處理 Google Drive／Docs 網域；其他網址原樣回傳，交給 validate_drive_url 擋掉。
    """
    value = (value or '').strip()
    parsed = urlparse(value)
    if parsed.hostname not in DRIVE_HOSTS:
        return value
    path = re.sub(r'/u/\d+(?=/|$)', '', parsed.path)
    return urlunparse(parsed._replace(path=path))


def validate_drive_url(value):
    parsed = urlparse(value)
    if parsed.scheme != 'https' or parsed.hostname not in DRIVE_HOSTS:
        raise ValidationError('請貼 Google Drive 連結（https://drive.google.com/… 或 https://docs.google.com/…）。')


class Score(models.Model):
    class ScoreType(models.TextChoices):
        FULL = 'full', '總譜'
        PART = 'part', '分譜'

    class CopyrightStatus(models.TextChoices):
        PUBLIC_DOMAIN = 'public_domain', '公版'
        COPYRIGHTED = 'copyrighted', '有版權'
        LICENSED = 'licensed', '已授權'

    class Source(models.TextChoices):
        PURCHASED = 'purchased', '購買'
        EXCHANGE = 'exchange', '與他團交換'
        DONATION = 'donation', '捐贈'

    class Difficulty(models.TextChoices):
        BEGINNER = 'beginner', '初級'
        INTERMEDIATE = 'intermediate', '中級'
        ADVANCED = 'advanced', '高級'

    title = models.CharField('曲名', max_length=200)
    composer = models.CharField('作曲家', max_length=100, blank=True)
    arranger = models.CharField('編曲者', max_length=100, blank=True)
    score_type = models.CharField('譜種', max_length=10, choices=ScoreType)
    instrument = models.ForeignKey(
        'accounts.InstrumentType', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='樂器'
    )
    custom_instrument_name = models.CharField(
        '樂器名稱（手填）', max_length=100, blank=True,
        help_text=f'樂器選「{CUSTOM_INSTRUMENT_NAME}」時必填，例如：手搖鈴。'
    )
    copyright_status = models.CharField('版權狀態', max_length=20, choices=CopyrightStatus)
    physical_quantity = models.PositiveSmallIntegerField('實體紙本數量', default=0)
    drive_url = models.URLField(
        'Google Drive 連結', max_length=500, blank=True, validators=[validate_drive_url],
        help_text='樂譜放在樂團的 Google Drive，這裡貼分享連結，團員由此下載。'
    )
    full_score = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='parts', verbose_name='所屬總譜',
        limit_choices_to={'score_type': 'full'}
    )
    parent_score = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='versions', verbose_name='基於版本'
    )
    version_note = models.TextField('改版說明', blank=True)
    source = models.CharField('來源', max_length=20, choices=Source, blank=True)
    publisher = models.CharField('出版商', max_length=100, blank=True)
    difficulty = models.CharField('難度', max_length=20, choices=Difficulty, blank=True)

    class Meta:
        verbose_name = '樂譜'
        verbose_name_plural = '樂譜列表'
        ordering = ['title']

    @property
    def is_custom_instrument(self):
        return bool(self.instrument_id) and self.instrument.name == CUSTOM_INSTRUMENT_NAME

    @property
    def instrument_label(self):
        """畫面上顯示的樂器名：手填樂器顯示手填的名稱，其餘顯示樂器主檔名稱。"""
        if self.is_custom_instrument and self.custom_instrument_name:
            return self.custom_instrument_name
        return self.instrument.name if self.instrument_id else ''

    def save(self, *args, **kwargs):
        # 不論從哪條路進來（表單、分譜管理頁、Admin、批次），存進去的連結都是整理過的版本
        self.drive_url = normalize_drive_url(self.drive_url)
        super().save(*args, **kwargs)

    def clean(self):
        if self.score_type == self.ScoreType.FULL:
            if self.instrument or self.custom_instrument_name:
                raise ValidationError('總譜不應指定樂器。')
            if self.full_score:
                raise ValidationError('總譜不應指定所屬總譜。')
        elif self.score_type == self.ScoreType.PART:
            if not self.instrument:
                raise ValidationError('分譜必須指定樂器。')
            if self.full_score and self.full_score.score_type != self.ScoreType.FULL:
                raise ValidationError('所屬總譜必須是總譜類型。')
            if self.is_custom_instrument and not self.custom_instrument_name.strip():
                raise ValidationError(f'樂器選「{CUSTOM_INSTRUMENT_NAME}」時，請填寫樂器名稱。')
            if not self.is_custom_instrument and self.custom_instrument_name:
                raise ValidationError(f'只有樂器選「{CUSTOM_INSTRUMENT_NAME}」時才能手填樂器名稱。')

    def __str__(self):
        if self.score_type == self.ScoreType.PART and self.instrument:
            return f'{self.title}（{self.instrument_label}）'
        return self.title


class ScoreExchange(models.Model):
    other_band = models.CharField('對方樂團', max_length=100)
    contact_person = models.CharField('對方聯絡人', max_length=50, blank=True)
    contact_phone = models.CharField('對方聯絡電話', max_length=20, blank=True)
    exchange_date = models.DateField('交換日期')
    notes = models.TextField('備註', blank=True)

    class Meta:
        verbose_name = '樂譜交換'
        verbose_name_plural = '樂譜交換列表'
        ordering = ['-exchange_date']

    def __str__(self):
        return f'{self.exchange_date} 與 {self.other_band} 交換'


class ScoreExchangeItem(models.Model):
    class Direction(models.TextChoices):
        GIVE = 'give', '給出'
        RECEIVE = 'receive', '收入'

    exchange = models.ForeignKey(
        ScoreExchange, on_delete=models.CASCADE,
        related_name='items', verbose_name='交換事件'
    )
    direction = models.CharField('方向', max_length=10, choices=Direction)
    score = models.ForeignKey(
        Score, on_delete=models.PROTECT,
        related_name='exchange_items', verbose_name='樂譜'
    )

    class Meta:
        verbose_name = '交換明細'
        verbose_name_plural = '交換明細列表'

    def __str__(self):
        return f'{self.get_direction_display()} {self.score.title}'
