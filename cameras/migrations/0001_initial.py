"""cameras migration 0001 — Camera model."""
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Camera',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('camera_id', models.CharField(help_text='Unique camera identifier (auto-assigned on enrollment).', max_length=50, unique=True)),
                ('api_key', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Per-camera API key transmitted as Bearer token by the camera worker.')),
                ('enrollment_token', models.UUIDField(blank=True, editable=False, help_text='One-time token used during camera self-enrollment.', null=True)),
                ('is_enrolled', models.BooleanField(default=False, help_text='True after the camera has completed self-enrollment.')),
                ('location', models.CharField(help_text="Physical location of the camera (e.g. 'Main Boulevard, Gulberg III, Lahore').", max_length=255)),
                ('legal_direction', models.CharField(choices=[('N', 'North'), ('S', 'South'), ('E', 'East'), ('W', 'West')], default='N', help_text='Legal travel direction at this camera location.', max_length=10)),
                ('rtsp_url', models.CharField(blank=True, help_text='RTSP stream URL: rtsp://user:pass@192.168.1.100:554/stream', max_length=500, null=True)),
                ('http_snapshot_url', models.CharField(blank=True, help_text='HTTP snapshot URL (alternative to RTSP): http://user:pass@192.168.1.100/snapshot.jpg', max_length=500, null=True)),
                ('is_streaming', models.BooleanField(default=True, help_text='When True, the camera worker polls this camera for frames.')),
                ('capture_interval', models.IntegerField(default=5, help_text='Seconds between frame captures by the camera worker.')),
                ('is_active', models.BooleanField(default=True)),
                ('installed_date', models.DateField(auto_now_add=True)),
                ('last_frame_at', models.DateTimeField(blank=True, help_text='Timestamp of last frame received from this camera.', null=True)),
                ('last_health_check', models.DateTimeField(blank=True, null=True)),
                ('health_status', models.CharField(choices=[('online', 'Online'), ('offline', 'Offline'), ('unknown', 'Unknown')], default='unknown', max_length=20)),
                ('notes', models.TextField(blank=True, help_text='Internal notes about this camera (maintenance, issues, etc.)', null=True)),
            ],
            options={
                'ordering': ['-installed_date'],
            },
        ),
        migrations.AddIndex(
            model_name='camera',
            index=models.Index(fields=['is_active', 'is_streaming'], name='cameras_cam_is_act_is_str_idx'),
        ),
        migrations.AddIndex(
            model_name='camera',
            index=models.Index(fields=['enrollment_token'], name='cameras_cam_enrollmen_idx'),
        ),
    ]
