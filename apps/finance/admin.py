from django.contrib import admin

from .models import FeePeriod, FinanceRecord, MembershipFee, PaymentConfig


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
    list_display = ['member', 'period', 'amount', 'status', 'payment_method',
                    'paid_at', 'collected_by', 'account_last5']
    list_filter = ['status', 'payment_method', 'period']
    search_fields = ['member__name']


@admin.register(PaymentConfig)
class PaymentConfigAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'updated_at']
