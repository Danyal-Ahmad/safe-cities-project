from django.contrib import admin
from .models import ChallanAppeal


@admin.register(ChallanAppeal)
class AppealAdmin(admin.ModelAdmin):
    list_display = ('id', 'challan', 'submitted_by', 'status', 'is_escalated', 'reviewed_by', 'created_at')
    list_filter = ('status', 'is_escalated', 'created_at')
    search_fields = ('challan__ticket_no', 'challan__plate_number', 'submitted_by__phone')
    readonly_fields = ('created_at', 'reviewed_at', 'escalated_at', 'dig_reviewed_at')

