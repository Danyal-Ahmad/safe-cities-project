from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, OfficerProfile, VehicleRegistration, PasswordResetToken,
    DigProfile, SspProfile, SupervisorProfile, ItProfile, AuditorProfile, CitizenProfile,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'phone', 'staff_id', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'phone', 'cnic', 'staff_id', 'first_name', 'last_name')
    ordering = ('role', 'username')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Safe City', {
            'fields': ('role', 'phone', 'cnic', 'staff_id', 'region', 'designation', 'department',
                       'avatar', 'avatar_color', 'is_guest_verified', 'failed_login_attempts',
                       'locked_until', 'last_login_ip'),
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Safe City', {'fields': ('role', 'email', 'phone', 'cnic')}),
    )


@admin.register(OfficerProfile)
class OfficerProfileAdmin(admin.ModelAdmin):
    list_display = ('officer', 'badge_number', 'rank', 'station', 'is_field_active', 'updated_at')
    search_fields = ('officer__username', 'badge_number', 'station')


@admin.register(DigProfile)
class DigProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'rank', 'command_region', 'authority_level', 'updated_at')


@admin.register(SspProfile)
class SspProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'rank', 'region', 'district', 'updated_at')


@admin.register(SupervisorProfile)
class SupervisorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'rank', 'team_name', 'region', 'shift_type', 'updated_at')


@admin.register(ItProfile)
class ItProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'specialization', 'on_call', 'updated_at')


@admin.register(AuditorProfile)
class AuditorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'audit_scope', 'clearance_level', 'updated_at')


@admin.register(CitizenProfile)
class CitizenProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'province', 'is_verified', 'total_challans', 'updated_at')
    search_fields = ('user__username', 'user__cnic', 'city')


@admin.register(VehicleRegistration)
class VehicleRegistrationAdmin(admin.ModelAdmin):
    list_display = ('plate_number', 'owner', 'vehicle_type', 'make', 'is_primary', 'created_at')
    search_fields = ('plate_number', 'owner__username')


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'used_at', 'ip_address')
    search_fields = ('user__username', 'token')

