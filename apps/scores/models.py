import re
from urllib.parse import urlparse, urlunparse

from django.core.exceptions import ValidationError
from django.db import models

# 樂譜檔案存放在樂團的 Google Drive：Render 免費方案的磁碟在重新部署時會清空，
# 系統不再自己存檔，只記連結。限定 Google 網域，避免把團員導到任意外站。
DRIVE_HOSTS = {'drive.google.com', 'docs.google.com'}

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
    """
    藏譜：一首曲子（的一個版本）一筆。

    檔案放在帳號 1 的 Google Drive「根目錄/藏譜/<樂曲名>」，內含指揮總譜（A）與未切割譜（B）；
    演出過後，譜務把切割好的分譜（C）從音樂會資料夾整理回「<樂曲名>/分譜」，填進 parts_url。
    同一首曲名的不同版本（編曲、縮編…）各建一筆，以編曲者與版本說明區分。
    演出用的分譜不在這裡，而是掛在演出活動的族群資料夾（events.EventPartFolder）。
    """

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
    version_note = models.CharField(
        '版本說明', max_length=100, blank=True,
        help_text='同一首曲名有多個版本時用來區分，例如：縮編版、2020 新版。'
    )
    copyright_status = models.CharField('版權狀態', max_length=20, choices=CopyrightStatus, blank=True)
    source = models.CharField('來源', max_length=20, choices=Source, blank=True)
    publisher = models.CharField('出版商', max_length=100, blank=True)
    difficulty = models.CharField('難度', max_length=20, choices=Difficulty, blank=True)
    drive_url = models.URLField(
        '藏譜資料夾連結', max_length=500, validators=[validate_drive_url],
        help_text='帳號 1 的「根目錄/藏譜/<樂曲名>」資料夾，內含總譜（A）與未切割譜（B）。'
    )
    parts_url = models.URLField(
        '分譜資料夾連結', max_length=500, blank=True, validators=[validate_drive_url],
        help_text='演出後整理回藏譜的切割分譜（C），通常是「<樂曲名>/分譜」。尚未切割就留空。'
    )

    class Meta:
        verbose_name = '藏譜'
        verbose_name_plural = '藏譜列表'
        ordering = ['title', 'arranger', 'version_note']

    def save(self, *args, **kwargs):
        # 不論從哪條路進來（表單、Admin、批次），存進去的連結都是整理過的版本
        self.drive_url = normalize_drive_url(self.drive_url)
        self.parts_url = normalize_drive_url(self.parts_url)
        super().save(*args, **kwargs)

    @property
    def is_cut(self):
        """已有切割好的分譜（C）。"""
        return bool(self.parts_url)

    def __str__(self):
        extra = '、'.join(x for x in (
            f'{self.arranger} 編' if self.arranger else '', self.version_note) if x)
        return f'{self.title}（{extra}）' if extra else self.title


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
