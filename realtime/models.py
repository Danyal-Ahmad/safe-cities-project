from django.db import models
from django.conf import settings
from cameras.models import Camera


class LiveFeed(models.Model):
    title = models.CharField(max_length=255, help_text="Name for this live feed")
    video_file = models.FileField(upload_to='live_feeds/%Y/%m/%d/',
                                  help_text="MP4/AVI/MOV video that will loop on the monitor")
    camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='live_feeds',
                               help_text="Optional: link to a registered camera for location context")
    location_label = models.CharField(max_length=255, null=True, blank=True,
                                      help_text="Display label for this feed (e.g. 'Main Boulevard')")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=True, help_text="When True, feed shows on monitoring dashboard")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sc_live_feeds'
        ordering = ['-created_at']

    def __str__(self):
        return f"LiveFeed: {self.title}"


class CameraAssignment(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='assignments')
    officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='assigned_cameras', limit_choices_to={'role': 'OFFICER'})
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, related_name='camera_assignments_made')
    is_active = models.BooleanField(default=True, help_text="When False, officer can't see this camera")
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True, help_text="Optional assignment notes")

    class Meta:
        db_table = 'sc_camera_assignments'
        ordering = ['-assigned_at']
        unique_together = ('camera', 'officer')

    def __str__(self):
        return f"{self.officer.display_name} → {self.camera.camera_id}"

