from django.db import models
from django.conf import settings
from cameras.models import Camera


class Detection(models.Model):
    PENDING = 'pending_review'
    CONFIRMED = 'confirmed'
    REJECTED = 'rejected'
    FLAGGED = 'flagged_for_dig'
    MANUAL = 'manually_added'
    STATUS_CHOICES = [
        (PENDING, 'Pending Review'),
        (CONFIRMED, 'Confirmed'),
        (REJECTED, 'Rejected (False Positive)'),
        (FLAGGED, 'Flagged for DIG'),
        (MANUAL, 'Manually Added'),
    ]
    SIDE_FRONT = 'front'
    SIDE_BACK = 'back'
    SIDE_CHOICES = [(SIDE_FRONT, 'Front'), (SIDE_BACK, 'Back')]

    camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, related_name='detections',
                               null=True, blank=True,
                               help_text="Null for detections from video uploads, or after the source camera "
                                         "record has been deleted. Detections/evidence are preserved even if "
                                         "the camera is removed (SET_NULL, not CASCADE) — deleting a camera "
                                         "must never destroy violation evidence or challan history.")
    raw_image = models.ImageField(upload_to='detections/raw/%Y/%m/%d/')
    plate_crop_image = models.ImageField(upload_to='detections/plate/%Y/%m/%d/', null=True, blank=True)

    ai_plate_text = models.CharField(max_length=20, null=True, blank=True)
    ai_province = models.CharField(max_length=10, null=True, blank=True)
    ai_series = models.CharField(max_length=10, null=True, blank=True)
    ai_registration_year = models.CharField(max_length=4, null=True, blank=True)
    ai_side_classification = models.CharField(max_length=5, choices=SIDE_CHOICES, null=True, blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)
    ai_detected_violation = models.BooleanField(default=False)
    ai_workflow_version = models.CharField(max_length=50, null=True, blank=True)
    ai_raw_response = models.JSONField(default=dict, blank=True)

    source_video_upload = models.ForeignKey('video_processor.VideoUpload', on_delete=models.SET_NULL,
                                             null=True, blank=True, related_name='pipeline_detections')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='reviewed_detections')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(null=True, blank=True)

    manual_plate_text = models.CharField(max_length=20, null=True, blank=True)
    manual_violation_type = models.CharField(max_length=20, null=True, blank=True)
    is_manually_annotated = models.BooleanField(default=False)

    manual_q1_image = models.ImageField(upload_to='detections/manual/q1/%Y/%m/%d/', null=True, blank=True,
                                         help_text="Top-left quadrant of the manually annotated frame.")
    manual_q2_image = models.ImageField(upload_to='detections/manual/q2/%Y/%m/%d/', null=True, blank=True,
                                         help_text="Top-right quadrant of the manually annotated frame.")
    manual_q3_image = models.ImageField(upload_to='detections/manual/q3/%Y/%m/%d/', null=True, blank=True,
                                         help_text="Bottom-left quadrant of the manually annotated frame.")
    manual_q4_image = models.ImageField(upload_to='detections/manual/q4/%Y/%m/%d/', null=True, blank=True,
                                         help_text="Bottom-right quadrant of the manually annotated frame.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Evidence crops used on e-challan PDF (full frame = raw_image)
    vehicle_image = models.ImageField(upload_to='detections/vehicle/%Y/%m/%d/', null=True, blank=True)
    plate_image = models.ImageField(upload_to='detections/plate/%Y/%m/%d/', null=True, blank=True)

    class Meta:
        db_table = 'sc_detections'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['camera', 'created_at']),
            models.Index(fields=['reviewed_by', 'reviewed_at']),
        ]

    def __str__(self):
        plate = self.manual_plate_text or self.ai_plate_text or '—'
        return f"Detection {self.id} — {plate} ({self.get_status_display()})"

    @property
    def effective_plate(self):
        return self.manual_plate_text or self.ai_plate_text or ''

    @property
    def effective_violation_type(self):
        return self.manual_violation_type or ('wrong_way' if self.ai_detected_violation else None)

    @property
    def effective_plate_image(self):
        """C5 FIX: Return the canonical plate crop image regardless of which field was populated.

        ``plate_crop_image`` is populated by the AI ingest pipeline.
        ``plate_image`` is populated by manual annotation / officer review.
        Templates and PDF service should use this property rather than picking
        one field and missing the other.
        """
        return self.plate_crop_image or self.plate_image


class DetectionReviewNote(models.Model):
    detection = models.ForeignKey(Detection, on_delete=models.CASCADE, related_name='review_notes_list')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sc_detection_review_notes'
        ordering = ['created_at']

    def __str__(self):
        return f"Note by {self.author} on Detection {self.detection_id}"


class Annotation(models.Model):
    TYPE_BOX = 'box'
    TYPE_POLYGON = 'polygon'
    TYPE_LINE = 'line'
    TYPE_MARKER = 'marker'
    TYPE_VIOLATION = 'violation'
    TYPE_CHOICES = [
        (TYPE_BOX, 'Bounding Box'),
        (TYPE_POLYGON, 'Polygon'),
        (TYPE_LINE, 'Line'),
        (TYPE_MARKER, 'Marker'),
        (TYPE_VIOLATION, 'Violation Marker'),
    ]

    OBJECT_VEHICLE = 'vehicle'
    OBJECT_PLATE = 'plate'
    OBJECT_PERSON = 'person'
    OBJECT_OTHER = 'other'
    OBJECT_CHOICES = [
        (OBJECT_VEHICLE, 'Vehicle'),
        (OBJECT_PLATE, 'License Plate'),
        (OBJECT_PERSON, 'Person'),
        (OBJECT_OTHER, 'Other'),
    ]

    VIOLATION_WRONG_WAY = 'wrong_way'
    VIOLATION_SIGNAL_BREAK = 'signal_break'
    VIOLATION_OVER_SPEED = 'over_speed'
    VIOLATION_NO_HELMET = 'no_helmet'
    VIOLATION_OTHER = 'other'
    VIOLATION_CHOICES = [
        (VIOLATION_WRONG_WAY, 'Wrong Way'),
        (VIOLATION_SIGNAL_BREAK, 'Signal Break'),
        (VIOLATION_OVER_SPEED, 'Over Speed'),
        (VIOLATION_NO_HELMET, 'No Helmet'),
        (VIOLATION_OTHER, 'Other'),
    ]

    detection = models.ForeignKey(
        Detection, on_delete=models.CASCADE, related_name='annotations',
        help_text="The detection/frame this annotation belongs to. Ties the annotation to the tracked vehicle."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='annotations_created'
    )

    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_BOX)
    object_type = models.CharField(max_length=20, choices=OBJECT_CHOICES, default=OBJECT_VEHICLE)
    violation_type = models.CharField(
        max_length=20, choices=VIOLATION_CHOICES, null=True, blank=True,
        help_text="Set when type=violation. Records which violation the marker represents."
    )
    label = models.CharField(max_length=100, blank=True, default='', help_text="Human-readable label for the annotation.")
    coordinates = models.JSONField(
        default=dict, blank=True,
        help_text="Box: {x, y, width, height}. Polygon/Line: [[x,y],...]. Marker: {x, y}."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_annotations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['detection', 'created_at']),
            models.Index(fields=['type']),
            models.Index(fields=['object_type']),
        ]

    def __str__(self):
        return f"Annotation {self.id} on Detection {self.detection_id} ({self.get_type_display()})"

    @property
    def track_id(self):
        return f"T-{self.detection_id}"

    @property
    def frame_timestamp(self):
        return self.detection.created_at

    def to_dict(self):
        return {
            'id': self.id,
            'detection_id': self.detection_id,
            'track_id': self.track_id,
            'type': self.type,
            'object_type': self.object_type,
            'violation_type': self.violation_type,
            'label': self.label,
            'coordinates': self.coordinates,
            'created_by': self.created_by.username if self.created_by else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'frame_timestamp': self.frame_timestamp.isoformat() if self.frame_timestamp else None,
        }

