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
