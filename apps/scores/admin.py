from django.contrib import admin

from .models import Score, ScoreExchange, ScoreExchangeItem


class ScoreExchangeItemInline(admin.TabularInline):
    model = ScoreExchangeItem
    extra = 1
    fields = ['direction', 'score']


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ['title', 'composer', 'score_type', 'instrument', 'section', 'difficulty', 'physical_quantity']
    list_filter = ['score_type', 'difficulty', 'copyright_status', 'source', 'instrument__category']
    search_fields = ['title', 'composer', 'arranger']


@admin.register(ScoreExchange)
class ScoreExchangeAdmin(admin.ModelAdmin):
    list_display = ['other_band', 'exchange_date', 'contact_person']
    search_fields = ['other_band']
    inlines = [ScoreExchangeItemInline]
