from django import forms
from django.contrib import admin
from django.forms.widgets import TextInput

from .models import Venue, VenueTimeSlot


class TimeHHMMWidget(TextInput):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('attrs', {}).update({'placeholder': 'HH:MM', 'maxlength': '5', 'size': '6'})
        super().__init__(*args, **kwargs)

    def format_value(self, value):
        if value and hasattr(value, 'strftime'):
            return value.strftime('%H:%M')
        if isinstance(value, str) and len(value) == 8:  # HH:MM:SS
            return value[:5]
        return value


class TimeHHMMField(forms.TimeField):
    widget = TimeHHMMWidget

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('input_formats', ['%H:%M'])
        super().__init__(*args, **kwargs)


class VenueTimeSlotForm(forms.ModelForm):
    start_time = TimeHHMMField(label='開始時間')
    end_time = TimeHHMMField(label='結束時間')

    class Meta:
        model = VenueTimeSlot
        fields = '__all__'


class VenueTimeSlotInline(admin.TabularInline):
    model = VenueTimeSlot
    form = VenueTimeSlotForm
    extra = 1
    fields = ['is_sun', 'is_mon', 'is_tue', 'is_wed', 'is_thu', 'is_fri', 'is_sat', 'start_time', 'end_time', 'fee']


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'address', 'capacity']
    list_filter = ['type']
    search_fields = ['name', 'address']
    inlines = [VenueTimeSlotInline]
