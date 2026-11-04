from django.contrib import admin
from .models import SystemSettings, AuditLog


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'email_enabled', 'due_date_days', 'ai_confidence_threshold', 'updated_at')
    def has_add_permission(self, request):
        return not SystemSettings.objects.exists()


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'actor', 'action', 'target_model', 'target_id', 'ip_address')
    list_filter = ('action', 'target_model', 'timestamp')
    search_fields = ('action', 'actor__phone', 'actor__email')
    readonly_fields = ('actor', 'action', 'target_model', 'target_id', 'timestamp', 'details', 'ip_address')
    date_hierarchy = 'timestamp'
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

