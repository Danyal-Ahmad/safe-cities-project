import re
import secrets
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class User(AbstractUser):
    class Meta:
        db_table = 'sc_users'

    DIG = 'DIG'
    SSP = 'SSP'
    SUPERVISOR = 'SUPV'
    OFFICER = 'OFFICER'
    AUDIT = 'AUDIT'
    IT_SUPPORT = 'IT'
    USER = 'USER'

    ROLE_CHOICES = [
        (DIG,        'DIG (Super Admin)'),
        (SSP,        'SSP | Senior Superintendent'),
        (SUPERVISOR, 'Supervisor'),
        (OFFICER,    'Officer'),
        (AUDIT,      'Audit Officer'),
        (IT_SUPPORT, 'IT Support'),
        (USER,       'Registered Citizen'),
    ]

    STAFF_ROLES = (DIG, SSP, SUPERVISOR, OFFICER, AUDIT, IT_SUPPORT)
    CITIZEN_ROLES = (USER,)
    SUPERADMIN_ROLES = (DIG, SSP)
    OPERATIONAL_ROLES = (DIG, SSP, SUPERVISOR, OFFICER, AUDIT)

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=USER)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True,
                             help_text="E.164 format, e.g. +923001234567")
    cnic = models.CharField(max_length=20, null=True, blank=True,
                            help_text="Optional. Used only for challan matching, never for login.")
    is_guest_verified = models.BooleanField(default=False)
    avatar_color = models.CharField(max_length=20, default='#0EA5E9')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True,
                                help_text="Optional profile picture upload.")
    signature = models.ImageField(upload_to='signatures/', null=True, blank=True,
                                   help_text="Officer/staff e-signature used on challan PDF. Transparent PNG preferred.")
    signature_name = models.CharField(max_length=120, null=True, blank=True,
                                        help_text="Printed name beside the signature (defaults to display_name).")
    signature_designation = models.CharField(max_length=120, null=True, blank=True,
                                              help_text="Printed designation under the signature (e.g. 'Enforcement Officer').")
    signature_stamp = models.ImageField(upload_to='stamps/', null=True, blank=True,
                                          help_text="Optional official rubber-stamp image.")
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    staff_id = models.CharField(max_length=30, null=True, blank=True,
                                help_text="Official staff ID, e.g. SC-2026-DIG-001")
    region = models.CharField(max_length=60, null=True, blank=True,
                              help_text="Operational region for SSP/Supervisor (e.g. 'Central Region')")
    designation = models.CharField(max_length=100, null=True, blank=True,
                                    help_text="Official designation (e.g. 'Deputy Inspector General')")
    department = models.CharField(max_length=100, null=True, blank=True,
                                   help_text="Department name (e.g. 'Traffic Enforcement')")

    username = models.CharField(max_length=150, unique=True)
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    def clean(self):
        super().clean()
        if not self.phone and not self.email:
            raise ValidationError("At least one of phone or email must be provided.")
        if self.cnic and not re.match(r'^\d{5}-\d{7}-\d$', self.cnic):
            raise ValidationError({"cnic": "CNIC must be in format NNNNN-NNNNNNN-N."})

    def save(self, *args, **kwargs):
        if not self.avatar_color or self.avatar_color == '#0EA5E9':
            self.avatar_color = {
                self.DIG:        '#6D28D9',
                self.SSP:        '#BE123C',
                self.SUPERVISOR: '#B45309',
                self.OFFICER:    '#1E40AF',
                self.AUDIT:      '#0F766E',
                self.IT_SUPPORT: '#475569',
                self.USER:       '#15803D',
            }.get(self.role, '#1E40AF')
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        if self.first_name:
            return self.get_full_name()
        return self.phone or self.email or self.username

    @property
    def public_id(self):
        from django.utils import timezone
        year = timezone.now().year
        role = self.role
        if role == self.USER:
            prefix = 'CZN'
            return f"{prefix}-{year}-{self.pk:04d}"
        return f"ADM-{year}-{self.pk:03d}"

    @property
    def avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return self.default_avatar_url

    @property
    def default_avatar_url(self):
        from django.templatetags.static import static
        if self.role == self.USER:
            return static('img/default_avatar_user.png')
        return static('img/project_logo.png')

    @property
    def has_custom_avatar(self):
        return bool(self.avatar and hasattr(self.avatar, 'url') and self.avatar.name)

    @property
    def initials(self):
        name = self.first_name or self.display_name
        parts = name.split()
        return ''.join(p[0].upper() for p in parts[:2]) or '?'

    @property
    def is_dig(self):        return self.role == self.DIG
    @property
    def is_ssp(self):        return self.role == self.SSP
    @property
    def is_supervisor(self): return self.role == self.SUPERVISOR
    @property
    def is_officer(self):    return self.role == self.OFFICER
    @property
    def is_audit(self):      return self.role == self.AUDIT
    @property
    def is_it_support(self): return self.role == self.IT_SUPPORT
    @property
    def is_regular_user(self): return self.role == self.USER
    @property
    def is_staff_role(self): return self.role in self.STAFF_ROLES

    @property
    def role_badge(self):
        return {
            self.DIG:        'DIG',
            self.SSP:        'SSP',
            self.SUPERVISOR: 'SUPV',
            self.OFFICER:    'OFFR',
            self.AUDIT:      'AUDT',
            self.IT_SUPPORT: 'IT',
            self.USER:       'USER',
        }.get(self.role, '?')

    @property
    def login_url(self):
        if self.role == self.USER:
            return '/auth/citizen/login/'
        return '/auth/admin/login/'

    @property
    def role_label(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)

    @property
    def is_locked(self):
        if self.locked_until:
            from django.utils import timezone
            return self.locked_until > timezone.now()
        return False

    @property
    def permissions(self):
        from .permissions import get_role_permissions
        return frozenset(get_role_permissions(self.role))

    def has_permission(self, perm_name):
        from .permissions import user_has_permission
        return user_has_permission(self, perm_name)

    def has_any_permission(self, *perm_names):
        from .permissions import user_has_any_permission
        return user_has_any_permission(self, perm_names)

    @property
    def reports_to_role(self):
        from .permissions import get_reports_to
        return get_reports_to(self.role)

    @property
    def manages_roles(self):
        from .permissions import get_manages
        return get_manages(self.role)

    @property
    def role_level(self):
        from .permissions import get_role_level
        return get_role_level(self.role)

    def can_override(self, other_user):
        from .permissions import can_override_user
        return can_override_user(self, other_user)

    def register_failed_login(self, threshold, duration_secs):
        from django.utils import timezone
        import datetime
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= threshold:
            self.locked_until = timezone.now() + datetime.timedelta(seconds=duration_secs)
            self.failed_login_attempts = 0
        self.save()

    def reset_failed_login(self):
        if self.failed_login_attempts > 0 or self.locked_until:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.save()

    def __str__(self):
        return f"{self.display_name} ({self.role})"


class OfficerProfile(models.Model):
    class Meta:
        db_table = 'sc_officer_profiles'

    officer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='officer_profile')
    can_review_detections = models.BooleanField(default=True)
    can_review_appeals = models.BooleanField(default=True)
    can_flag_for_dig = models.BooleanField(default=True)
    can_view_own_performance = models.BooleanField(default=True)
    can_add_internal_notes = models.BooleanField(default=True)
    can_live_tracking = models.BooleanField(default=True)
    can_live_monitor = models.BooleanField(default=False)
    can_record_payment = models.BooleanField(default=False)
    can_manage_blacklist = models.BooleanField(default=False)
    badge_number = models.CharField(max_length=40, blank=True, default='')
    belt_number = models.CharField(max_length=40, blank=True, default='')
    rank = models.CharField(max_length=60, blank=True, default='Enforcement Officer')
    unit = models.CharField(max_length=100, blank=True, default='')
    station = models.CharField(max_length=100, blank=True, default='')
    shift_preference = models.CharField(max_length=20, blank=True, default='DAY',
                                        choices=[('DAY', 'Day'), ('NIGHT', 'Night'), ('ROTATING', 'Rotating')])
    joining_date = models.DateField(null=True, blank=True)
    is_field_active = models.BooleanField(default=True)
    max_daily_challans = models.PositiveIntegerField(default=50)
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='officer_profiles_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"OfficerProfile for {self.officer.display_name}"

    @classmethod
    def get_for(cls, user):
        profile, _ = cls.objects.get_or_create(officer=user)
        return profile

    def can(self, permission_name):
        return getattr(self, permission_name, False)




class DigProfile(models.Model):
    """DIG (Deputy Inspector General) - command authority profile."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dig_profile',
                                limit_choices_to={'role': User.DIG})
    badge_number = models.CharField(max_length=40, blank=True, default='')
    rank = models.CharField(max_length=80, blank=True, default='Deputy Inspector General')
    command_region = models.CharField(max_length=100, blank=True, default='Central')
    office_address = models.CharField(max_length=255, blank=True, default='')
    office_phone = models.CharField(max_length=30, blank=True, default='')
    authority_level = models.CharField(max_length=20, default='FULL',
                                       choices=[('FULL', 'Full command'), ('ACTING', 'Acting'), ('LIMITED', 'Limited')])
    can_manage_all_staff = models.BooleanField(default=True)
    can_override_appeals = models.BooleanField(default=True)
    can_purge_data = models.BooleanField(default=True)
    can_edit_system_settings = models.BooleanField(default=True)
    appointment_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_dig_profiles'
        verbose_name = 'DIG profile'
        verbose_name_plural = 'DIG profiles'

    def __str__(self):
        return f"DIG: {self.user.display_name}"


class SspProfile(models.Model):
    """SSP (Senior Superintendent of Police) - regional senior command."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ssp_profile',
                                limit_choices_to={'role': User.SSP})
    badge_number = models.CharField(max_length=40, blank=True, default='')
    rank = models.CharField(max_length=80, blank=True, default='Senior Superintendent of Police')
    division = models.CharField(max_length=100, blank=True, default='')
    district = models.CharField(max_length=100, blank=True, default='')
    region = models.CharField(max_length=100, blank=True, default='Central Region')
    office_address = models.CharField(max_length=255, blank=True, default='')
    office_phone = models.CharField(max_length=30, blank=True, default='')
    can_review_high_value = models.BooleanField(default=True)
    can_approve_escalations = models.BooleanField(default=True)
    can_view_regional_analytics = models.BooleanField(default=True)
    high_value_threshold = models.PositiveIntegerField(default=5000,
        help_text='Fine amount (PKR) above which SSP attention is required')
    appointment_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_ssp_profiles'
        verbose_name = 'SSP profile'
        verbose_name_plural = 'SSP profiles'

    def __str__(self):
        return f"SSP: {self.user.display_name} ({self.region})"


class SupervisorProfile(models.Model):
    """Shift Supervisor - team and shift oversight."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='supervisor_profile',
                                limit_choices_to={'role': User.SUPERVISOR})
    badge_number = models.CharField(max_length=40, blank=True, default='')
    rank = models.CharField(max_length=80, blank=True, default='Shift Supervisor')
    team_name = models.CharField(max_length=100, blank=True, default='')
    region = models.CharField(max_length=100, blank=True, default='')
    station = models.CharField(max_length=100, blank=True, default='')
    max_team_size = models.PositiveIntegerField(default=12)
    can_assign_shifts = models.BooleanField(default=True)
    can_view_team_performance = models.BooleanField(default=True)
    can_reassign_cameras = models.BooleanField(default=False)
    shift_type = models.CharField(max_length=20, blank=True, default='ROTATING',
                                  choices=[('DAY', 'Day'), ('NIGHT', 'Night'), ('ROTATING', 'Rotating')])
    appointment_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_supervisor_profiles'
        verbose_name = 'Supervisor profile'
        verbose_name_plural = 'Supervisor profiles'

    def __str__(self):
        return f"Supervisor: {self.user.display_name}"


class ItProfile(models.Model):
    """IT Support - systems, cameras, PDF, backups."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='it_profile',
                                limit_choices_to={'role': User.IT_SUPPORT})
    employee_id = models.CharField(max_length=40, blank=True, default='')
    rank = models.CharField(max_length=80, blank=True, default='IT Support Engineer')
    specialization = models.CharField(max_length=100, blank=True, default='Infrastructure',
        help_text='e.g. Infrastructure, CCTV, Database, Network')
    department = models.CharField(max_length=100, blank=True, default='IT Wing')
    can_manage_cameras = models.BooleanField(default=True)
    can_edit_pdf_settings = models.BooleanField(default=True)
    can_manage_payment_methods = models.BooleanField(default=True)
    can_run_backups = models.BooleanField(default=True)
    can_view_system_health = models.BooleanField(default=True)
    can_live_tracking = models.BooleanField(default=True)
    on_call = models.BooleanField(default=False)
    appointment_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_it_profiles'
        verbose_name = 'IT profile'
        verbose_name_plural = 'IT profiles'

    def __str__(self):
        return f"IT: {self.user.display_name}"


class AuditorProfile(models.Model):
    """Audit Officer - compliance and financial/operational audit."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='auditor_profile',
                                limit_choices_to={'role': User.AUDIT})
    employee_id = models.CharField(max_length=40, blank=True, default='')
    rank = models.CharField(max_length=80, blank=True, default='Internal Audit Officer')
    audit_scope = models.CharField(max_length=100, blank=True, default='Full system',
        help_text='e.g. Financial, Operational, Full system')
    department = models.CharField(max_length=100, blank=True, default='Internal Audit')
    can_view_financial_audit = models.BooleanField(default=True)
    can_view_operational_audit = models.BooleanField(default=True)
    can_export_audit_logs = models.BooleanField(default=True)
    can_view_anomalies = models.BooleanField(default=True)
    can_view_user_activity = models.BooleanField(default=True)
    clearance_level = models.CharField(max_length=20, default='STANDARD',
                                       choices=[('STANDARD', 'Standard'), ('ELEVATED', 'Elevated'), ('FULL', 'Full')])
    appointment_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_auditor_profiles'
        verbose_name = 'Auditor profile'
        verbose_name_plural = 'Auditor profiles'

    def __str__(self):
        return f"Auditor: {self.user.display_name}"


class CitizenProfile(models.Model):
    """Registered citizen - owner details for challans and appeals."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='citizen_profile',
                                limit_choices_to={'role': User.USER})
    father_name = models.CharField(max_length=120, blank=True, default='')
    address = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=80, blank=True, default='')
    province = models.CharField(max_length=80, blank=True, default='')
    postal_code = models.CharField(max_length=20, blank=True, default='')
    preferred_language = models.CharField(max_length=10, default='en',
                                          choices=[('en', 'English'), ('ur', 'Urdu')])
    notification_email = models.BooleanField(default=True)
    notification_sms = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    total_challans = models.PositiveIntegerField(default=0)
    total_paid = models.PositiveIntegerField(default=0)
    total_unpaid = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_citizen_profiles'
        verbose_name = 'Citizen profile'
        verbose_name_plural = 'Citizen profiles'

    def __str__(self):
        return f"Citizen: {self.user.display_name}"


from django.db.models.signals import post_save
from django.dispatch import receiver

_ROLE_PROFILE_MAP = {
    User.DIG: (DigProfile, 'dig_profile'),
    User.SSP: (SspProfile, 'ssp_profile'),
    User.SUPERVISOR: (SupervisorProfile, 'supervisor_profile'),
    User.OFFICER: (OfficerProfile, 'officer_profile'),
    User.IT_SUPPORT: (ItProfile, 'it_profile'),
    User.AUDIT: (AuditorProfile, 'auditor_profile'),
    User.USER: (CitizenProfile, 'citizen_profile'),
}


@receiver(post_save, sender=User)
def ensure_role_profile(sender, instance, created, **kwargs):
    """Create matching role profile row; OfficerProfile uses related_name officer_profile."""
    mapping = _ROLE_PROFILE_MAP.get(instance.role)
    if not mapping:
        return
    model, related = mapping
    if related == 'officer_profile':
        OfficerProfile.objects.get_or_create(officer=instance)
    else:
        model.objects.get_or_create(user=instance)


class VehicleRegistration(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='registered_vehicles')
    plate_number = models.CharField(max_length=20, help_text="e.g. LRN-795")
    vehicle_type = models.CharField(max_length=20, default='car')
    make = models.CharField(max_length=50, null=True, blank=True, help_text="e.g. Honda Civic")
    year = models.CharField(max_length=4, null=True, blank=True)
    color = models.CharField(max_length=20, null=True, blank=True)
    is_primary = models.BooleanField(default=False, help_text="Primary vehicle for notifications")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sc_vehicle_registrations'
        ordering = ['-created_at']
        unique_together = ('owner', 'plate_number')

    def __str__(self):
        return f"{self.plate_number} | {self.owner.display_name}"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='password_reset_tokens')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'sc_password_reset_tokens'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['token', 'used_at'])]

    def __str__(self):
        return f"ResetToken({self.user_id}) {self.token[:8]}…{'used' if self.used_at else 'active'}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class AdminPasswordResetRequest(models.Model):
    """Request from a staff/admin who forgot their password.
    The user is NOT allowed to reset their own password directly - instead, a
    request is created and DIG is notified to perform the reset."""

    STATUS_PENDING = 'PENDING'
    STATUS_RESOLVED = 'RESOLVED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending DIG Action'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='admin_reset_requests',
    )
    requested_by_email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='admin_resets_performed',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    reason_note = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'sc_admin_password_reset_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['target_user', 'status']),
        ]

    def __str__(self):
        return f"AdminResetReq(user={self.target_user_id}, status={self.status})"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(hours=72)

