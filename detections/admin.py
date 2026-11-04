from django.contrib import admin
from .models import Detection, DetectionReviewNote


@admin.register(Detection)
class DetectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'camera', 'effective_plate', 'ai_side_classification',
                    'ai_confidence', 'ai_detected_violation', 'status', 'reviewed_by', 'created_at')
    list_filter = ('status', 'ai_side_classification', 'ai_detected_violation')
    search_fields = ('ai_plate_text', 'manual_plate_text')
    readonly_fields = ('created_at', 'reviewed_at', 'ai_workflow_version', 'ai_raw_response')


@admin.register(DetectionReviewNote)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('detection', 'author', 'created_at')
    readonly_fields = ('created_at',)

