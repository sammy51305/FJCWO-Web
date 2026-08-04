from django.contrib import admin

from .models import FeePeriod, FinanceRecord, MembershipFee


@admin.register(FinanceRecord)
class FinanceRecordAdmin(admin.ModelAdmin):
    list_display = ['date', 'type', 'category', 'amount', 'description', 'created_by']
    list_filter = ['type', 'category']
    search_fields = ['description']
    date_hierarchy = 'date'


@admin.register(FeePeriod)
class FeePeriodAdmin(admin.ModelAdmin):
    list_display = ['year', 'term', 'amount', 'start_date', 'end_date', 'created_by']
    list_filter = ['year', 'term']


@admin.register(MembershipFee)
class MembershipFeeAdmin(admin.ModelAdmin):
    list_display = ['member', 'period', 'amount', 'status', 'paid_at', 'collected_by']
    list_filter = ['status', 'period']
    search_fields = ['member__name']
