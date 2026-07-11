from django.contrib import admin

from apps.notifications.utils import fmt_dt, push_line_message

from .models import (GuestMember, LeaveRequest, PartAssignment,
                     PerformanceAttendance, PerformanceEvent, Rehearsal,
                     RehearsalAttendance, RehearsalQRToken, Setlist)


class RehearsalInline(admin.TabularInline):
    model = Rehearsal
    extra = 1
    fields = ['sequence', 'date', 'venue', 'time_slot']


class SetlistInline(admin.TabularInline):
    model = Setlist
    extra = 1
    fields = ['order', 'score']


@admin.register(PerformanceEvent)
class PerformanceEventAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'performance_date', 'status']
    list_filter = ['type', 'status']
    search_fields = ['name']
    inlines = [RehearsalInline, SetlistInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            push_line_message(
                f'🎼 新演出活動：{obj.name}\n'
                f'類型：{obj.get_type_display()}\n'
                f'預定日期：{fmt_dt(obj.performance_date)}'
            )

    def save_formset(self, request, form, formset, change):
        if formset.model is not Rehearsal:
            super().save_formset(request, form, formset, change)
            return

        existing_pks = {f.instance.pk for f in formset.forms if f.instance.pk}
        super().save_formset(request, form, formset, change)

        for f in formset.forms:
            obj = f.instance
            if obj.pk and obj.pk not in existing_pks and not f.cleaned_data.get('DELETE', False):
                push_line_message(
                    f'📋 新增排練：{obj}\n'
                    f'日期：{fmt_dt(obj.date)}\n'
                    f'地點：{obj.venue.name}'
                )


@admin.register(Rehearsal)
class RehearsalAdmin(admin.ModelAdmin):
    list_display = ['event', 'sequence', 'date', 'venue', 'time_slot']
    list_filter = ['event']
    search_fields = ['event__name']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            push_line_message(
                f'📋 新增排練：{obj}\n'
                f'日期：{fmt_dt(obj.date)}\n'
                f'地點：{obj.venue.name}'
            )
        elif 'date' in form.changed_data or 'venue' in form.changed_data:
            push_line_message(
                f'📋 排練資訊異動：{obj}\n'
                f'日期：{fmt_dt(obj.date)}\n'
                f'地點：{obj.venue.name}'
            )


@admin.register(RehearsalQRToken)
class RehearsalQRTokenAdmin(admin.ModelAdmin):
    list_display = ['rehearsal', 'token', 'expires_at', 'is_active']
    list_filter = ['is_active']


@admin.register(GuestMember)
class GuestMemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'instrument', 'section', 'from_band', 'event']
    list_filter = ['event', 'instrument']
    search_fields = ['name', 'from_band']


@admin.register(RehearsalAttendance)
class RehearsalAttendanceAdmin(admin.ModelAdmin):
    list_display = ['rehearsal', 'member', 'status', 'checked_in_at']
    list_filter = ['status', 'rehearsal__event']
    search_fields = ['member__name']


@admin.register(PerformanceAttendance)
class PerformanceAttendanceAdmin(admin.ModelAdmin):
    list_display = ['event', 'member', 'confirmed', 'checked_in_at']
    list_filter = ['event', 'confirmed']
    search_fields = ['member__name']


@admin.register(Setlist)
class SetlistAdmin(admin.ModelAdmin):
    list_display = ['event', 'order', 'score']
    list_filter = ['event']


@admin.register(PartAssignment)
class PartAssignmentAdmin(admin.ModelAdmin):
    list_display = ['setlist', 'member', 'guest_member', 'instrument', 'section']
    list_filter = ['setlist__event', 'instrument']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['member', 'rehearsal', 'status', 'reviewed_by', 'reviewed_at']
    list_filter = ['status', 'rehearsal__event']
    search_fields = ['member__name']
