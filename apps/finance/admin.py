from django.contrib import admin

from .models import FeePeriod, FinanceCategory, FinanceRecord, MembershipFee, PaymentConfig


@admin.register(FinanceCategory)
class FinanceCategoryAdmin(admin.ModelAdmin):
    """收支分類：幹部／管理員自己增減。已有紀錄用的刪不掉（改成取消「啟用」即可）；
    系統分類（會費）不能改名、停用或刪除，因為確認繳費時系統會自動寫入。"""
    list_display = ['name', 'kind', 'sort_order', 'is_active', 'is_system']
    list_editable = ['sort_order']      # is_active 不放這裡：清單頁擋不住系統分類被停用
    list_filter = ['kind', 'is_active']
    ordering = ['sort_order', 'id']

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.is_system:
            return ['name', 'kind', 'is_active']
        return []

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)


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
    list_display = ['__str__', 'bank_code', 'bank_name', 'account_name', 'account_number', 'updated_at']
