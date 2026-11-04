from django.contrib import admin
from .models import Camera


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ('camera_id', 'location', 'legal_direction', 'is_active', 'is_streaming',
                    'health_status', 'is_enrolled', 'last_frame_at', 'installed_date')
    list_filter = ('is_active', 'is_streaming', 'health_status', 'legal_direction')
    search_fields = ('camera_id', 'location', 'rtsp_url')
    readonly_fields = ('api_key', 'installed_date', 'last_frame_at', 'last_health_check')

