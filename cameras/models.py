import uuid
from django.db import models


class Camera(models.Model):
    camera_id = models.CharField(max_length=50, unique=True,
                                 help_text="Unique camera identifier (auto-assigned on enrollment).")
    api_key = models.UUIDField(default=uuid.uuid4, editable=False,
                               help_text="Per-camera API key transmitted as Bearer token by the camera worker.")
    enrollment_token = models.UUIDField(null=True, blank=True, editable=False,
                                        help_text="One-time token used during camera self-enrollment.")
    is_enrolled = models.BooleanField(default=False,
                                      help_text="True after the camera has completed self-enrollment.")

    location = models.CharField(max_length=255,
                                help_text="Physical location of the camera (e.g. 'Main Boulevard, Sector III').")
    latitude = models.FloatField(null=True, blank=True,
                                 help_text="GPS latitude for map/heatmap (optional).")
    longitude = models.FloatField(null=True, blank=True,
                                  help_text="GPS longitude for map/heatmap (optional).")
    legal_direction = models.CharField(max_length=10, choices=[
        ('N', 'North'), ('S', 'South'), ('E', 'East'), ('W', 'West'),
    ], default='N', help_text="Pool / mounting direction of this camera (N/S/E/W). "
                              "Used for physical placement labelling only — does NOT decide what counts as a violation.")

    VIOLATION_SIDE_BACK = 'back'
    VIOLATION_SIDE_FRONT = 'front'
    VIOLATION_SIDE_CHOICES = [
        (VIOLATION_SIDE_BACK,  'Back side = violation (default)'),
        (VIOLATION_SIDE_FRONT, 'Front side = violation (inverted)'),
    ]
    violation_side = models.CharField(
        max_length=5, choices=VIOLATION_SIDE_CHOICES, default=VIOLATION_SIDE_BACK,
        help_text=(
            "Which side of the car (as classified by the ONNX model) counts as a "
            "wrong-way violation at THIS camera. Default = back. Flip to 'front' "
            "if this camera is mounted to capture oncoming traffic (e.g. on the "
            "opposite side of the road)."
        ),
    )
    auto_confirm_threshold = models.FloatField(
        default=0.70,
        help_text=(
            "Minimum combined AI confidence (plate detection + side classification) "
            "for the system to AUTO-CONFIRM a violation and create a Challan without "
            "officer review. Detections below this threshold go to the officer "
            "review queue. Default = 0.70 (70%)."
        ),
    )

    rtsp_url = models.CharField(max_length=500, null=True, blank=True,
                                help_text="RTSP stream URL: rtsp://user:pass@192.168.1.100:554/stream")
    http_snapshot_url = models.CharField(max_length=500, null=True, blank=True,
                                         help_text="HTTP snapshot URL (alternative to RTSP): http://user:pass@192.168.1.100/snapshot.jpg")
    is_streaming = models.BooleanField(default=True,
                                       help_text="When True, the camera worker polls this camera for frames.")
    capture_interval = models.IntegerField(default=5,
                                           help_text="Seconds between frame captures by the camera worker.")

    is_active = models.BooleanField(default=True)
    installed_date = models.DateField(auto_now_add=True)
    last_frame_at = models.DateTimeField(null=True, blank=True,
                                         help_text="Timestamp of last frame received from this camera.")
    last_health_check = models.DateTimeField(null=True, blank=True)
    health_status = models.CharField(max_length=20, default='unknown',
                                     choices=[('online', 'Online'), ('offline', 'Offline'), ('unknown', 'Unknown'), ('degraded', 'Degraded')])

    notes = models.TextField(null=True, blank=True,
                             help_text="Internal notes about this camera (maintenance, issues, etc.)")

    class Meta:
        db_table = 'sc_cameras'
        ordering = ['-installed_date']
        indexes = [
            models.Index(fields=['is_active', 'is_streaming']),
            models.Index(fields=['enrollment_token']),
        ]

    def __str__(self):
        return f"{self.camera_id} — {self.location}"

    def is_violation_side(self, classified_side: str) -> bool:
        return classified_side == self.violation_side

    def is_allowed_side(self, classified_side: str) -> bool:
        return classified_side == self.allowed_side

    @property
    def allowed_side(self) -> str:
        return self.VIOLATION_SIDE_FRONT if self.violation_side == self.VIOLATION_SIDE_BACK else self.VIOLATION_SIDE_BACK

    @property
    def allow_side(self) -> str:
        return self.allowed_side

    def toggle(self):
        self.is_active = not self.is_active
        self.save()

    def mark_online(self):
        from django.utils import timezone
        self.last_frame_at = timezone.now()
        self.health_status = 'online'
        self.last_health_check = timezone.now()
        self.save(update_fields=['last_frame_at', 'health_status', 'last_health_check'])

    def mark_offline(self):
        from django.utils import timezone
        self.health_status = 'offline'
        self.last_health_check = timezone.now()
        self.save(update_fields=['health_status', 'last_health_check'])

