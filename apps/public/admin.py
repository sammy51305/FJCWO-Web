from django.contrib import admin

from .models import Venue


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'address', 'capacity']
    list_filter = ['type']
    search_fields = ['name', 'address']
