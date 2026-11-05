from django.db import models
from django.conf import settings
from cameras.models import Camera


class Detection(models.Model):
    PENDING = 'pending_review'
    CONFIRMED = 'confirmed'
    REJECTED = 'rejected'
    FLAGGED = 'flagged_officer'
    STATUS_CHOICES = [
        (PENDING, 'Pending Review'),
        (CONFIRMED, 'Confirmed'),
        (REJECTED, 'Rejected (False Positive)'),
        (FLAGGED, 'Flagged for Officer Review'),
    ]
    SIDE_FRONT = 'front'
    SIDE_BACK = 'back'
    SIDE_CHOICES = [(SIDE_FRONT, 'Front'), (SIDE_BACK, 'Back')]

    camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, related_name='detections',
                               null=True, blank=True,
                               help_text="Null for detections from video uploads, or after the source camera "
                                         "record has been deleted. Detections/evidence are preserved even if "
                                         "the camera is removed (SET_NULL, not CASCADE) - deleting a camera "
                                         "must never destroy violation evidence or challan history.")
    raw_image = models.ImageField(upload_to='detections/raw/%Y/%m/%d/')
    plate_crop_image = models.ImageField(upload_to='detections/plate/%Y/%m/%d/', null=True, blank=True)

    # Three-frame sequential evidence (90FPS style): the primary frame is
    # raw_image; these hold the two immediately consecutive frames captured
    # around the violation instant so reviewers can step through the sequence.
    evidence_frame_2 = models.ImageField(upload_to='detections/seq/%Y/%m/%d/', null=True, blank=True)
    evidence_frame_3 = models.ImageField(upload_to='detections/seq/%Y/%m/%d/', null=True, blank=True)
    evidence_frames_meta = models.JSONField(default=list, blank=True,
                                            help_text="Per-frame capture metadata for the 3-frame evidence sequence.")
    annotated_image = models.ImageField(upload_to='detections/annotated/%Y/%m/%d/', null=True, blank=True,
                                        help_text="Court-ready annotated evidence frame (violation box, plate box, direction arrow).")

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

    track_id = models.CharField(max_length=40, null=True, blank=True, db_index=True,
                                help_text="Cross-frame vehicle track identifier (same vehicle across frames).")
    track_frames = models.PositiveIntegerField(default=0,
                                               help_text="Number of frames matched in the vehicle track.")
    track_consistency = models.FloatField(default=0.0,
                                         help_text="0-1 plate/side agreement across the matched track frames.")

    evidence_checks = models.JSONField(default=list, blank=True,
                                       help_text="Five-step hard security check results for the evidence package.")
    evidence_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True,
                                     help_text="SHA-256 tamper-evident digest of the evidence chain.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_detections'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['camera', 'created_at']),
            models.Index(fields=['reviewed_by', 'reviewed_at']),
            models.Index(fields=['track_id']),
        ]

    def __str__(self):
        plate = self.ai_plate_text or '-'
        return f"Detection {self.id} | {plate} ({self.get_status_display()})"

    @property
    def effective_plate(self):
        return self.ai_plate_text or ''

    @property
    def effective_violation_type(self):
        return 'wrong_way' if self.ai_detected_violation else None

    @property
    def effective_plate_image(self):
        return self.plate_crop_image

    def evidence_frames(self):
        """Return the sequential evidence frames (max 3) for officer review.

        Frame 1 is always the primary raw capture. Frames 2 and 3 come from
        the consecutive-frame capture for video uploads, or from the same
        cross-frame vehicle track for live camera ingests.
        """
        frames = [{
            'slot': 1,
            'label': 'FRAME 01',
            'image': self.raw_image,
            'timestamp': self.created_at,
            'plate': self.ai_plate_text,
            'source': 'primary',
        }]
        for slot, field in ((2, 'evidence_frame_2'), (3, 'evidence_frame_3')):
            img = getattr(self, field)
            if img:
                meta = {}
                for row in (self.evidence_frames_meta or []):
                    if int(row.get('slot') or 0) == slot:
                        meta = row
                        break
                frames.append({
                    'slot': slot,
                    'label': f'FRAME {slot:02d}',
                    'image': img,
                    'timestamp': meta.get('timestamp'),
                    'plate': meta.get('plate'),
                    'source': 'sequential',
                })
        if len(frames) < 3 and self.track_id:
            track_peers = Detection.objects.filter(
                track_id=self.track_id,
            ).exclude(pk=self.pk).order_by('created_at')[:3]
            for peer in track_peers:
                if len(frames) >= 3:
                    break
                if peer.raw_image:
                    frames.append({
                        'slot': len(frames) + 1,
                        'label': f'FRAME {len(frames) + 1:02d}',
                        'image': peer.raw_image,
                        'timestamp': peer.created_at,
                        'plate': peer.ai_plate_text,
                        'source': 'track',
                    })
        return frames[:3]

    @property
    def evidence_summary(self):
        checks = self.evidence_checks or []
        passed = sum(1 for c in checks if c.get('passed'))
        return {
            'checks': checks,
            'passed': passed,
            'total': len(checks),
            'all_passed': bool(checks) and passed == len(checks),
            'hash': self.evidence_hash,
        }

    @property
    def failed_evidence_checks(self):
        return [c for c in (self.evidence_checks or []) if not c.get('passed')]


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
