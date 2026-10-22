from django.contrib import admin

from .models import Score, ScoreExchange, ScoreExchangeItem


class ScoreExchangeItemInline(admin.TabularInline):
    model = ScoreExchangeItem
    extra = 1
    fields = ['direction', 'score']


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ['title', 'arranger', 'version_note', 'composer', 'difficulty', 'copyright_status']
    list_filter = ['difficulty', 'copyright_status', 'source']
    search_fields = ['title', 'composer', 'arranger', 'version_note']


@admin.register(ScoreExchange)
class ScoreExchangeAdmin(admin.ModelAdmin):
    list_display = ['other_band', 'exchange_date', 'contact_person']
    search_fields = ['other_band']
    inlines = [ScoreExchangeItemInline]
