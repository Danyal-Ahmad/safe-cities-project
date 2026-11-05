"""realtime migration 0001 - LiveFeed + CameraAssignment."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        ('cameras', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiveFeed',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Name for this live feed', max_length=255)),
                ('video_file', models.FileField(help_text='MP4/AVI/MOV video that will loop on the monitor', upload_to='live_feeds/%Y/%m/%d/')),
                ('location_label', models.CharField(blank=True, help_text="Display label for this feed (e.g. 'Main Boulevard')", max_length=255, null=True)),
                ('is_active', models.BooleanField(default=True, help_text='When True, feed shows on monitoring dashboard')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('camera', models.ForeignKey(blank=True, help_text='Optional: link to a registered camera for location context', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='live_feeds', to='cameras.camera')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CameraAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, help_text="When False, officer can't see this camera")),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True, help_text='Optional assignment notes', null=True)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='camera_assignments_made', to='accounts.user')),
                ('camera', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='cameras.camera')),
                ('officer', models.ForeignKey(limit_choices_to={'role': 'OFFICER'}, on_delete=django.db.models.deletion.CASCADE, related_name='assigned_cameras', to='accounts.user')),
            ],
            options={
                'ordering': ['-assigned_at'],
                'unique_together': {('camera', 'officer')},
            },
        ),
    ]
