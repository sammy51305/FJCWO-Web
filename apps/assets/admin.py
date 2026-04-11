from django.contrib import admin

from .models import AssetBorrow, BandProperty, InstrumentMaintenance


class AssetBorrowInline(admin.TabularInline):
    model = AssetBorrow
    extra = 0
    fields = ['borrower', 'borrowed_at', 'due_date', 'returned_at']
    readonly_fields = ['borrowed_at']


class InstrumentMaintenanceInline(admin.TabularInline):
    model = InstrumentMaintenance
    extra = 0
    fields = ['date', 'description', 'cost', 'performed_by']


@admin.register(BandProperty)
class BandPropertyAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'condition', 'storage_location', 'contact_person']
    list_filter = ['category', 'condition']
    search_fields = ['name', 'storage_location']
    inlines = [AssetBorrowInline, InstrumentMaintenanceInline]


@admin.register(AssetBorrow)
class AssetBorrowAdmin(admin.ModelAdmin):
    list_display = ['asset', 'borrower', 'borrowed_at', 'due_date', 'returned_at']
    list_filter = ['asset__category']
    search_fields = ['borrower__name', 'asset__name']


@admin.register(InstrumentMaintenance)
class InstrumentMaintenanceAdmin(admin.ModelAdmin):
    list_display = ['asset', 'date', 'cost', 'performed_by']
    list_filter = ['asset']
    search_fields = ['asset__name']
