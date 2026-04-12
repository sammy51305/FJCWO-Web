from django.db import models


class Venue(models.Model):
    class Type(models.TextChoices):
        PERFORMANCE = 'performance', '演出場地'
        REHEARSAL = 'rehearsal', '排練場地'

    class ParkingStatus(models.TextChoices):
        YES = 'yes', '可停放'
        NO = 'no', '不可停放'
        LIMITED = 'limited', '有限制'

    name = models.CharField('場地名稱', max_length=100)
    type = models.CharField('場地類別', max_length=20, choices=Type)
    address = models.CharField('地址', max_length=200, blank=True)
    capacity = models.PositiveIntegerField('容納人數', null=True, blank=True)
    phone = models.CharField('場地電話', max_length=20, blank=True)
    google_map_url = models.URLField('Google Maps 網址', blank=True)
    contact_person = models.CharField('聯絡人姓名', max_length=50, blank=True)
    contact_phone = models.CharField('聯絡人電話', max_length=20, blank=True)
    transportation = models.TextField('交通方式', blank=True)
    motorcycle_parking = models.CharField('機車停放', max_length=10, choices=ParkingStatus, blank=True)
    car_parking = models.CharField('汽車停放', max_length=10, choices=ParkingStatus, blank=True)
    notes = models.TextField('備註', blank=True)

    class Meta:
        verbose_name = '場地'
        verbose_name_plural = '場地列表'
        ordering = ['name']

    def __str__(self):
        return self.name


class VenueTimeSlot(models.Model):
    venue = models.ForeignKey(
        Venue, on_delete=models.CASCADE,
        related_name='time_slots', verbose_name='場地'
    )
    is_sun = models.BooleanField('週日', default=False)
    is_mon = models.BooleanField('週一', default=False)
    is_tue = models.BooleanField('週二', default=False)
    is_wed = models.BooleanField('週三', default=False)
    is_thu = models.BooleanField('週四', default=False)
    is_fri = models.BooleanField('週五', default=False)
    is_sat = models.BooleanField('週六', default=False)
    start_time = models.TimeField('開始時間')
    end_time = models.TimeField('結束時間')
    fee = models.DecimalField('費用', max_digits=8, decimal_places=0, null=True, blank=True)

    class Meta:
        verbose_name = '場地時段'
        verbose_name_plural = '場地時段列表'
        ordering = ['venue', 'start_time']

    def weekday_display(self):
        days = []
        if self.is_sun: days.append('日')
        if self.is_mon: days.append('一')
        if self.is_tue: days.append('二')
        if self.is_wed: days.append('三')
        if self.is_thu: days.append('四')
        if self.is_fri: days.append('五')
        if self.is_sat: days.append('六')
        return '週' + '／'.join(days) if days else '（未設定）'

    def __str__(self):
        return f'{self.venue.name}｜{self.weekday_display()}（{self.start_time.strftime("%H:%M")}–{self.end_time.strftime("%H:%M")}）'
