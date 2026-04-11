from django.contrib import admin

from .models import FinanceRecord, MembershipFee


@admin.register(FinanceRecord)
class FinanceRecordAdmin(admin.ModelAdmin):
    list_display = ['date', 'type', 'category', 'amount', 'description', 'created_by']
    list_filter = ['type', 'category']
    search_fields = ['description']
    date_hierarchy = 'date'


@admin.register(MembershipFee)
class MembershipFeeAdmin(admin.ModelAdmin):
    list_display = ['member', 'period', 'amount', 'paid_at', 'collected_by']
    list_filter = ['period']
    search_fields = ['member__name']
