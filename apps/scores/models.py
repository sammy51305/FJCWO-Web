from django.core.exceptions import ValidationError
from django.db import models


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
    section = models.ForeignKey(
        'accounts.SectionType', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='聲部'
    )
    copyright_status = models.CharField('版權狀態', max_length=20, choices=CopyrightStatus)
    physical_quantity = models.PositiveSmallIntegerField('實體紙本數量', default=0)
    file = models.FileField('樂譜 PDF', upload_to='scores/', blank=True)
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

    def clean(self):
        if self.score_type == self.ScoreType.FULL:
            if self.instrument or self.section:
                raise ValidationError('總譜不應指定樂器或聲部。')
        elif self.score_type == self.ScoreType.PART:
            if not self.instrument:
                raise ValidationError('分譜必須指定樂器。')

    def __str__(self):
        if self.score_type == self.ScoreType.PART and self.instrument:
            return f'{self.title}（{self.instrument.name}）'
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
