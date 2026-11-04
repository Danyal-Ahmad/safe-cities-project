from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


class SystemSettings(models.Model):
    class Meta:
        db_table = 'sc_system_settings'

    default_fines = models.JSONField(default=dict, blank=True)
    template_config = models.JSONField(default=dict, blank=True)
    email_template = models.JSONField(default=dict, blank=True)
    due_date_days = models.IntegerField(default=30)
    email_enabled = models.BooleanField(default=False)
    ai_confidence_threshold = models.FloatField(default=0.75,
        help_text="Minimum confidence to accept a car detection (model default target 0.90)")
    ai_config = models.JSONField(default=dict, blank=True,
        help_text="ONNX model runtime settings (input sizes, thresholds, class filters)")
    pdf_logo = models.ImageField(upload_to='settings/', null=True, blank=True)
    pdf_template = models.CharField(
        max_length=100, default='standard_a4', blank=True,
        help_text="Active PDF template key. File template = filename under "
                   "templates/challan/challan_templates/ without .html. "
                   "DB template = 'db:<ChallanTemplate id>'."
    )
    audit_template = models.CharField(
        max_length=100, default='audit_summary_report', blank=True,
        help_text="Active audit document template key. File template = filename under "
                   "templates/audit/audit_templates/ without .html. "
                   "DB template = 'db:<AuditTemplate id>'."
    )
    excise_api_url = models.CharField(max_length=255, null=True, blank=True)
    excise_api_key = models.CharField(max_length=255, null=True, blank=True)
    nadra_api_url = models.CharField(max_length=255, null=True, blank=True,
        help_text='NADRA Verisys / CNIC verification endpoint')
    nadra_api_key = models.CharField(max_length=255, null=True, blank=True)
    integration_mode = models.CharField(
        max_length=10, default='demo',
        choices=[('demo', 'Demo'), ('real', 'Real')],
        help_text='demo: sandbox Excise/NADRA/payments; real: use configured live endpoints',
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True)

    payment_config = models.JSONField(
        default=dict, blank=True,
        help_text="V7.1: Stores JazzCash, EasyPaisa, Stripe, Bank Transfer config."
    )

    DEFAULT_FINES = {
        'wrong_way': 500, 'no_helmet': 300, 'signal_break': 500,
        'over_speed': 800, 'other': 500,
    }
    DEFAULT_TEMPLATE_CONFIG = {
        'header_text': 'SAFE CITY — TRAFFIC ENFORCEMENT',
        'logo_path': '',
        'account_number': 'SAFECITY-CHALLAN-00123456789',
        'footer_text': 'Pay at any National Bank of Pakistan branch or Post Office before the due date.',
        'smtp_host': '', 'smtp_port': 587, 'smtp_user': '', 'smtp_password': '',
        'smtp_from': '', 'smtp_tls': '1',
        'sms_provider': '', 'sms_api_url': '', 'sms_api_key': '',
        'sms_api_secret': '', 'sms_sender': '',
    }
    DEFAULT_AI_CONFIG = {
        'plate_detector': {
            'file': 'NumberPlate_detection_model_int8.onnx',
            'input_name': 'input',
            'input_shape': [1, 3, 560, 560],
            'input_layout': 'NCHW',
            'input_normalize': 'imagenet',
            'output_dets': 'dets',
            'output_labels': 'labels',
            'max_detections': 300,
            'num_classes': 91,
            'car_class_id': 3,
            'vehicle_class_ids': [3, 4, 6, 8],
            'person_class_id': -1,
            'plate_class_ids': [1],
            'confidence_threshold': 0.15,
            'nms_style': 'score_sort',
            'max_box_area_ratio': 0.22,
            'min_box_area_ratio': 0.0008,
            'box_tighten': 0.88,
        },
        'side_classifier': {
            'file': 'car_side_Classifier_model_int8.onnx',
            'input_name': 'input',
            'input_shape': [1, 224, 224, 3],
            'input_layout': 'NHWC',
            'input_normalize': '-1_1',
            'output_name': 'dense',
            'output_shape': [1, 1],
            'back_threshold': 0.50,
            'min_side_confidence': 0.55,
        },
        'car_only': True,
        'reject_person': False,
    }
    DEFAULT_EMAIL_TEMPLATE = {
        'subject': 'New E-Challan Issued — {ticket_no}',
        'body': 'A new e-challan has been issued for vehicle {plate_number}. View: {view_link}',
    }

    @classmethod
    def get(cls):
        instance = cls.objects.first()
        if not instance:
            instance = cls.objects.create(
                default_fines=cls.DEFAULT_FINES,
                template_config=cls.DEFAULT_TEMPLATE_CONFIG,
                email_template=cls.DEFAULT_EMAIL_TEMPLATE,
                ai_config=cls.DEFAULT_AI_CONFIG,
                ai_confidence_threshold=0.75,
            )
        tc = dict(cls.DEFAULT_TEMPLATE_CONFIG)
        if isinstance(instance.template_config, dict):
            tc.update({k: v for k, v in instance.template_config.items() if v not in (None, '')})
        instance.template_config = tc
        ai = dict(cls.DEFAULT_AI_CONFIG)
        if isinstance(instance.ai_config, dict):
            ai.update(instance.ai_config)
        instance.ai_config = ai
        fines = dict(cls.DEFAULT_FINES)
        if isinstance(instance.default_fines, dict):
            fines.update(instance.default_fines)
        instance.default_fines = fines
        return instance

    def get_fine(self, violation_type):
        return self.default_fines.get(violation_type, self.DEFAULT_FINES.get(violation_type, 500))

    def __str__(self):
        return "System Settings (singleton)"


@receiver(post_save, sender=SystemSettings)
def enforce_singleton(sender, instance, created, **kwargs):
    if created and SystemSettings.objects.count() > 1:
        SystemSettings.objects.exclude(pk=instance.pk).delete()


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                              null=True, related_name='audit_entries')
    action = models.CharField(max_length=80)
    target_model = models.CharField(max_length=50)
    target_id = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True, default="")
    device = models.CharField(max_length=120, blank=True, default="",
                              help_text="Human-readable device summary (browser / OS / type).")

    class Meta:
        db_table = 'sc_audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['actor', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['target_model', 'target_id']),
        ]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} — {self.actor} — {self.action}"

    @staticmethod
    def parse_device(user_agent_str):
        try:
            import user_agents
            ua = user_agents.parse(user_agent_str or '')
            family = getattr(ua.browser, 'family', '') or 'Unknown browser'
            os_family = getattr(ua.os, 'family', '') or 'Unknown OS'
            device = getattr(ua.device, 'family', '') or ''
            brand = getattr(ua.device, 'brand', '') or ''
            dtype = 'Mobile' if ua.is_mobile else ('Tablet' if ua.is_tablet else
                                                   ('Bot' if ua.is_bot else 'Desktop'))
            parts = [dtype]
            if brand:
                parts.append(brand)
            if device and device.lower() != 'other':
                parts.append(device)
            summary = ' / '.join(parts[:3])
            return f"{family} on {os_family}"[:120], summary[:120]
        except Exception:
            return ('', '')

    @classmethod
    def write(cls, request, action, target_model='', target_id=None, **details):
        actor = None
        ip = None
        ua_str = ''
        device = ''
        if request is not None:
            user = getattr(request, 'user', None)
            if user is not None and getattr(user, 'is_authenticated', False):
                actor = user
            ip = request.META.get('HTTP_X_FORWARDED_FOR')
            if ip:
                ip = ip.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            ua_str = (request.META.get('HTTP_USER_AGENT') or '')[:400]
            if ua_str:
                device, _ = cls.parse_device(ua_str)
        return cls.objects.create(
            actor=actor, action=action,
            target_model=target_model, target_id=target_id,
            details=details, ip_address=ip,
            user_agent=ua_str, device=device or '',
        )


class LoginEvent(models.Model):
    """Immutable record of every authentication attempt on the platform.

    Captures the account, portal, outcome, source IP and full device
    fingerprint (browser / OS / device type) so auditors can reconstruct
    who accessed the system, from where and with what device.
    """
    PORTAL_ADMIN = 'admin'
    PORTAL_CITIZEN = 'citizen'
    PORTAL_CHOICES = [(PORTAL_ADMIN, 'Staff Portal'), (PORTAL_CITIZEN, 'Citizen Portal')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='login_events')
    username_attempted = models.CharField(max_length=150)
    portal = models.CharField(max_length=10, choices=PORTAL_CHOICES, default=PORTAL_ADMIN)
    success = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=120, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True, default="")
    browser = models.CharField(max_length=120, blank=True, default="")
    os = models.CharField(max_length=120, blank=True, default="")
    device_type = models.CharField(max_length=30, blank=True, default="")
    device_brand = models.CharField(max_length=80, blank=True, default="")
    device_summary = models.CharField(max_length=160, blank=True, default="")
    session_key = models.CharField(max_length=64, blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'sc_login_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['success', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]

    def __str__(self):
        who = self.user.username if self.user else self.username_attempted
        return f"{self.timestamp:%Y-%m-%d %H:%M} — {who} — {'OK' if self.success else 'FAIL'}"

    @classmethod
    def record(cls, request, username, success, portal=PORTAL_ADMIN,
               user=None, failure_reason=''):
        ip = None
        ua_str = ''
        parsed = ('', '', '', '', '')
        if request is not None:
            ip = request.META.get('HTTP_X_FORWARDED_FOR')
            if ip:
                ip = ip.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            ua_str = (request.META.get('HTTP_USER_AGENT') or '')[:400]
            parsed = cls._parse_ua(ua_str)
        browser, os_name, device_type, device_brand, device_summary = parsed
        session_key = ''
        if success and request is not None and hasattr(request, 'session'):
            session_key = request.session.session_key or ''
        try:
            return cls.objects.create(
                user=user if (user is not None and getattr(user, 'is_authenticated', False)) else None,
                username_attempted=(username or '')[:150],
                portal=portal, success=success,
                failure_reason=(failure_reason or '')[:120],
                ip_address=ip, user_agent=ua_str,
                browser=browser[:120], os=os_name[:120],
                device_type=device_type[:30], device_brand=device_brand[:80],
                device_summary=device_summary[:160],
                session_key=session_key[:64],
            )
        except Exception:
            return None

    @staticmethod
    def _parse_ua(ua_str):
        try:
            import user_agents
            ua = user_agents.parse(ua_str or '')
            browser = getattr(ua.browser, 'family', '') or 'Unknown'
            os_name = getattr(ua.os, 'family', '') or 'Unknown'
            device_type = ('Mobile' if ua.is_mobile else 'Tablet' if ua.is_tablet else
                           'Bot' if ua.is_bot else 'Desktop')
            brand = getattr(ua.device, 'brand', '') or ''
            family = getattr(ua.device, 'family', '') or ''
            summary_parts = [device_type]
            if brand:
                summary_parts.append(brand)
            if family and family.lower() != 'other':
                summary_parts.append(family)
            return browser, os_name, device_type, brand, ' / '.join(summary_parts)
        except Exception:
            return ('', '', '', '', '')


class Alert(models.Model):
    SEVERITY_INFO = 'info'
    SEVERITY_SUCCESS = 'success'
    SEVERITY_WARNING = 'warning'
    SEVERITY_DANGER = 'danger'
    SEVERITY_CHOICES = [
        (SEVERITY_INFO,    'Info'),
        (SEVERITY_SUCCESS, 'Success'),
        (SEVERITY_WARNING, 'Warning'),
        (SEVERITY_DANGER,  'Danger'),
    ]
    AUDIENCE_ALL = 'all'
    AUDIENCE_STAFF = 'staff'
    AUDIENCE_CITIZENS = 'citizens'
    AUDIENCE_DIG = 'dig'
    AUDIENCE_SSP = 'ssp'
    AUDIENCE_SUPERVISOR = 'supervisor'
    AUDIENCE_OFFICER = 'officer'
    AUDIENCE_AUDIT = 'audit'
    AUDIENCE_IT = 'it'
    AUDIENCE_CHOICES = [
        (AUDIENCE_ALL,        'Everyone'),
        (AUDIENCE_STAFF,      'All Staff'),
        (AUDIENCE_CITIZENS,   'All Citizens'),
        (AUDIENCE_DIG,        'DIG only'),
        (AUDIENCE_SSP,        'SSP only'),
        (AUDIENCE_SUPERVISOR, 'Supervisors only'),
        (AUDIENCE_OFFICER,    'Officers only'),
        (AUDIENCE_AUDIT,      'Audit Officers only'),
        (AUDIENCE_IT,         'IT Support only'),
    ]
    title = models.CharField(max_length=200)
    message = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default=SEVERITY_INFO)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name='alerts_created')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional expiry timestamp")

    class Meta:
        db_table = 'sc_alerts'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['is_active', 'audience'])]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title} ({self.audience})"

    @classmethod
    def get_for_user(cls, user):
        from django.utils import timezone
        qs = cls.objects.filter(is_active=True)
        if user.is_authenticated:
            role = user.role
            audiences = [cls.AUDIENCE_ALL, cls.AUDIENCE_STAFF]
            if role == 'USER':
                audiences.append(cls.AUDIENCE_CITIZENS)
            elif role == 'DIG':
                audiences.extend([cls.AUDIENCE_DIG])
            elif role == 'SSP':
                audiences.extend([cls.AUDIENCE_SSP])
            elif role == 'SUPV':
                audiences.extend([cls.AUDIENCE_SUPERVISOR])
            elif role == 'OFFICER':
                audiences.extend([cls.AUDIENCE_OFFICER])
            elif role == 'AUDIT':
                audiences.extend([cls.AUDIENCE_AUDIT])
            elif role == 'IT':
                audiences.extend([cls.AUDIENCE_IT])
            qs = qs.filter(audience__in=audiences)
        else:
            qs = qs.none()
        now = timezone.now()
        return qs.filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))


class Banner(models.Model):
    PLACEMENT_TOP = 'top'
    PLACEMENT_BOTTOM = 'bottom'
    PLACEMENT_AD = 'ad'
    PLACEMENT_POPUP = 'popup'
    PLACEMENT_CHOICES = [
        (PLACEMENT_TOP, 'Top of page'),
        (PLACEMENT_BOTTOM, 'Bottom of page'),
        (PLACEMENT_AD, 'Banner — Public Service Announcement Space'),
        (PLACEMENT_POPUP, 'POPUP banner'),
    ]
    AUDIENCE_ALL = 'all'
    AUDIENCE_STAFF = 'staff'
    AUDIENCE_CITIZENS = 'citizens'
    AUDIENCE_DIG = 'dig'
    AUDIENCE_SSP = 'ssp'
    AUDIENCE_SUPERVISOR = 'supervisor'
    AUDIENCE_OFFICER = 'officer'
    AUDIENCE_AUDIT = 'audit'
    AUDIENCE_IT = 'it'
    AUDIENCE_CHOICES = [
        (AUDIENCE_ALL,        'Everyone'),
        (AUDIENCE_STAFF,      'All Staff'),
        (AUDIENCE_CITIZENS,   'All Citizens'),
        (AUDIENCE_DIG,        'DIG only'),
        (AUDIENCE_SSP,        'SSP only'),
        (AUDIENCE_SUPERVISOR, 'Supervisors only'),
        (AUDIENCE_OFFICER,    'Officers only'),
        (AUDIENCE_AUDIT,      'Audit Officers only'),
        (AUDIENCE_IT,         'IT Support only'),
    ]
    BANNER_TYPE_IMAGE = 'image'
    BANNER_TYPE_HTML = 'html'
    BANNER_TYPE_CHOICES = [
        (BANNER_TYPE_IMAGE, 'Image Banner'),
        (BANNER_TYPE_HTML, 'Custom HTML/Code'),
    ]
    title = models.CharField(max_length=200, help_text="Internal title for management")
    banner_type = models.CharField(max_length=10, choices=BANNER_TYPE_CHOICES, default=BANNER_TYPE_IMAGE)
    image = models.ImageField(upload_to='banners/', null=True, blank=True, help_text="Upload banner image")
    image_link = models.URLField(max_length=500, blank=True, default='', help_text="URL to open when banner is clicked")
    html_content = models.TextField(blank=True, default='', help_text="Raw HTML content (for custom code banners)")
    placement = models.CharField(max_length=10, choices=PLACEMENT_CHOICES, default=PLACEMENT_TOP)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    bg_color = models.CharField(max_length=20, default='#1F4E79', help_text="CSS color for banner background")
    text_color = models.CharField(max_length=20, default='#FFFFFF', help_text="CSS color for banner text")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name='banners_created')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    priority = models.IntegerField(
        default=0,
        help_text="Higher priority banners appear first. Default 0. Use 100 for critical announcements."
    )
    start_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Optional scheduled start time. Banner won't display before this timestamp."
    )
    show_on_home_only = models.BooleanField(
        default=True,
        help_text="V7.1: Restrict banner to the public home page only (challans:home)."
    )
    auto_hide_after_search = models.BooleanField(
        default=True,
        help_text="V7.1: Auto-hide the banner once the visitor submits a challan search."
    )

    class Meta:
        db_table = 'sc_banners'
        ordering = ['-priority', '-created_at']

    def __str__(self):
        return f"[Banner] {self.title} ({self.audience})"

    @property
    def effective_bg_color(self):
        return self.bg_color or '#1F4E79'

    @classmethod
    def get_for_user(cls, user, placement='top'):
        from django.utils import timezone
        qs = cls.objects.filter(is_active=True, placement=placement)
        now = timezone.now()
        qs = qs.filter(models.Q(start_at__isnull=True) | models.Q(start_at__lte=now))
        qs = qs.filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
        if user.is_authenticated:
            role = user.role
            audiences = [cls.AUDIENCE_ALL]
            if role in ('DIG', 'SSP', 'SUPV', 'OFFICER', 'AUDIT', 'IT'):
                audiences.append(cls.AUDIENCE_STAFF)
            else:
                audiences.append(cls.AUDIENCE_CITIZENS)
            if role == 'DIG':
                audiences.append(cls.AUDIENCE_DIG)
            elif role == 'SSP':
                audiences.append(cls.AUDIENCE_SSP)
            elif role == 'SUPV':
                audiences.append(cls.AUDIENCE_SUPERVISOR)
            elif role == 'OFFICER':
                audiences.append(cls.AUDIENCE_OFFICER)
            elif role == 'AUDIT':
                audiences.append(cls.AUDIENCE_AUDIT)
            elif role == 'IT':
                audiences.append(cls.AUDIENCE_IT)
            qs = qs.filter(audience__in=audiences)
        else:
            qs = qs.filter(audience=cls.AUDIENCE_ALL)
        return qs


class Notification(models.Model):
    CATEGORY_CHOICES = [
        ('appeal_submit', 'Appeal Submitted'),
        ('appeal_pending', 'Appeal Pending Review'),
        ('appeal_approved', 'Appeal Approved'),
        ('appeal_rejected', 'Appeal Rejected'),
        ('appeal_escalated', 'Appeal Escalated'),
        ('camera', 'Camera Event'),
        ('challan', 'Challan Event'),
        ('payment_verification', 'Payment Verification'),
        ('system', 'System Event'),
        ('other', 'Other'),
    ]
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    target_url = models.CharField(max_length=500, blank=True, default='',
                                   help_text="URL to navigate to when clicked (e.g. /dig/appeal/5/override/)")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sc_notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.recipient.display_name}: {self.title}"


class Shift(models.Model):
    officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='shifts')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='shifts_assigned')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sc_shifts'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['officer', 'start_time']),
            models.Index(fields=['start_time', 'end_time']),
        ]

    def __str__(self):
        return f"{self.officer.display_name}: {self.start_time:%d-%b %H:%M} \u2192 {self.end_time:%H:%M}"

    @staticmethod
    def auto_assign_officer(start_time, end_time):
        from datetime import timedelta
        from accounts.models import User

        window_start = start_time - timedelta(days=7)

        all_shifts = list(Shift.objects.all().only('officer_id', 'start_time', 'end_time'))

        def _as_dt(v):
            from datetime import datetime, time as dtime, date
            from django.utils import timezone as dj_tz
            if v is None:
                return None
            if isinstance(v, datetime):
                if dj_tz.is_naive(v):
                    try:
                        return dj_tz.make_aware(v, dj_tz.get_current_timezone())
                    except Exception:
                        return v
                return v
            if isinstance(v, dtime):
                base = start_time.date() if hasattr(start_time, 'date') else date.today()
                try:
                    return dj_tz.make_aware(datetime.combine(base, v), dj_tz.get_current_timezone())
                except Exception:
                    return datetime.combine(base, v)
            return v

        overlapping_ids = set()
        for sh in all_shifts:
            s0, e0 = _as_dt(sh.start_time), _as_dt(sh.end_time)
            if s0 is None or e0 is None:
                continue
            try:
                if s0 < end_time and e0 > start_time:
                    overlapping_ids.add(sh.officer_id)
            except TypeError:
                continue

        officers = list(
            User.objects.filter(role=User.OFFICER, is_active=True)
            .exclude(pk__in=overlapping_ids)
        )
        if not officers:
            return None

        def score(officer):
            recent = 0
            last = None
            for sh in all_shifts:
                if sh.officer_id != officer.pk:
                    continue
                s0 = _as_dt(sh.start_time)
                if s0 is None:
                    continue
                try:
                    if s0 >= window_start:
                        recent += 1
                    if last is None or s0 > last:
                        last = s0
                except TypeError:
                    continue
            return (recent, last or window_start)

        officers.sort(key=score)
        return officers[0] if officers else None


class ChallanTemplate(models.Model):
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True, default="")
    file = models.FileField(upload_to="challan_templates/%Y/%m/", blank=True, null=True)
    html_content = models.TextField(blank=True, default="")
    design_json = models.TextField(blank=True, default="",
                                   help_text="Challan Studio structured document (blocks + theme).")
    is_active = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_challan_templates'
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_active:
            ChallanTemplate.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class AuditTemplate(models.Model):
    """Government-style audit document template (Audit Studio designs).

    Layouts are rendered by the audit PDF service with period statistics,
    signatures of the Audit Officer and the countersigning DIG.
    """
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True, default="")
    html_content = models.TextField(blank=True, default="")
    design_json = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='audit_templates_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_audit_templates'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_active:
            AuditTemplate.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class AuditDocument(models.Model):
    """A generated, signed audit document over a chosen period."""
    template_key = models.CharField(max_length=120,
                                    help_text="File template key or 'db:<AuditTemplate id>'.")
    title = models.CharField(max_length=200)
    period_from = models.DateField()
    period_to = models.DateField()
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='audit_documents')
    pdf_file = models.FileField(upload_to='audit/docs/%Y/%m/', null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sc_audit_documents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.period_from} → {self.period_to})"


class BlacklistEntry(models.Model):
    """Flagged vehicle plates blocked from normal processing."""
    plate_number = models.CharField(max_length=20, unique=True, db_index=True)
    reason = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='blacklist_entries_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'sc_blacklist'
        ordering = ['-created_at']
        verbose_name_plural = 'Blacklist entries'

    def __str__(self):
        return f"{self.plate_number} — {self.reason[:40]}"
