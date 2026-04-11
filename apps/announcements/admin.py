from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'visibility', 'published_at', 'created_by']
    list_filter = ['visibility']
    search_fields = ['title', 'content']
