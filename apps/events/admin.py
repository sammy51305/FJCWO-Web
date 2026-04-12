from django.contrib import admin

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


@admin.register(Rehearsal)
class RehearsalAdmin(admin.ModelAdmin):
    list_display = ['event', 'sequence', 'date', 'venue', 'time_slot']
    list_filter = ['event']
    search_fields = ['event__name']


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
