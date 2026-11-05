from django.db import models
from django.conf import settings


class VideoUpload(models.Model):
    STATUS_UPLOADED = 'uploaded'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_UPLOADED, 'Uploaded'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, related_name='video_uploads')
    video_file = models.FileField(upload_to='videos/%Y/%m/%d/',
                                  help_text="MP4, AVI, MOV - max 200 MB")
    original_filename = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UPLOADED)

    total_frames_extracted = models.IntegerField(default=0)
    frames_with_plates = models.IntegerField(default=0)
    violations_detected = models.IntegerField(default=0)
    auto_challans_created = models.IntegerField(default=0)
    manual_review_created = models.IntegerField(default=0)
    frames_ignored = models.IntegerField(default=0)

    processing_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    camera = models.ForeignKey('cameras.Camera', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='video_uploads')
    camera_location = models.CharField(max_length=255, null=True, blank=True,
                                       help_text="Location where this video was recorded")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sc_video_uploads'
        ordering = ['-created_at']

    def __str__(self):
        return f"VideoUpload {self.id} | {self.original_filename or 'unnamed'} ({self.status})"

    @property
    def duration_str(self):
        if self.processing_started_at and self.completed_at:
            delta = self.completed_at - self.processing_started_at
            return f"{delta.total_seconds():.1f}s"
        return '-'

    @property
    def progress_percent(self):
        if self.total_frames_extracted == 0:
            return 0
        processed = self.frames_with_plates + self.frames_ignored + self.manual_review_created
        processed = min(processed, self.total_frames_extracted)
        if self.status == self.STATUS_COMPLETED:
            return 100
        return min(100, int((processed / self.total_frames_extracted) * 100))


class VideoFrame(models.Model):
    video_upload = models.ForeignKey(VideoUpload, on_delete=models.CASCADE, related_name='frames')
    detection = models.ForeignKey('detections.Detection', on_delete=models.CASCADE,
                                  null=True, blank=True, related_name='video_frames')
    frame_number = models.IntegerField()
    timestamp_secs = models.FloatField(help_text="Timestamp in the video (seconds)")
    frame_image = models.ImageField(upload_to='video_frames/%Y/%m/%d/',
                                    null=True, blank=True)
    plate_detected = models.BooleanField(default=False)
    side_classification = models.CharField(max_length=5, null=True, blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)
    ocr_text = models.CharField(max_length=20, null=True, blank=True,
                                help_text="OCR-extracted plate text (if available)")
    ocr_confidence = models.FloatField(null=True, blank=True)
    auto_processed = models.BooleanField(default=False,
                                         help_text="True if auto-challan created, False if sent to manual review")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sc_video_frames'
        ordering = ['frame_number']
        indexes = [
            models.Index(fields=['video_upload', 'frame_number']),
            models.Index(fields=['plate_detected', 'auto_processed']),
        ]

    def __str__(self):
        return f"Frame {self.frame_number} ({self.timestamp_secs:.1f}s) - plate={self.plate_detected}"

