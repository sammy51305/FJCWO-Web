from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import InstrumentType, Registration, SectionType, User


@admin.register(InstrumentType)
class InstrumentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'category']
    list_filter = ['category']
    search_fields = ['name']


@admin.register(SectionType)
class SectionTypeAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('樂團資料', {
            'fields': ('name', 'role', 'instrument', 'section', 'grad_year', 'phone', 'line_user_id')
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('樂團資料', {
            'fields': ('name', 'email', 'role', 'instrument', 'section', 'grad_year')
        }),
    )
    list_display = ['username', 'name', 'email', 'role', 'instrument', 'section']
    list_filter = ['role', 'instrument__category', 'is_active']
    search_fields = ['username', 'name', 'email']


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ['name', 'grad_year', 'instrument', 'status', 'created_at', 'reviewed_by']
    list_filter = ['status', 'instrument']
    search_fields = ['name', 'email']
