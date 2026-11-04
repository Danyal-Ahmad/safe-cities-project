from django.contrib import admin
from .models import LiveFeed, CameraAssignment


@admin.register(LiveFeed)
class LiveFeedAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'camera', 'location_label', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'location_label')


@admin.register(CameraAssignment)
class CameraAssignmentAdmin(admin.ModelAdmin):
    list_display = ('camera', 'officer', 'assigned_by', 'is_active', 'assigned_at')
    list_filter = ('is_active',)
    search_fields = ('camera__camera_id', 'officer__first_name', 'officer__email')

