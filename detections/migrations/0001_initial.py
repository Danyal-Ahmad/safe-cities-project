"""detections migration 0001 — Detection + DetectionReviewNote."""
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
            name='Detection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('raw_image', models.ImageField(upload_to='detections/raw/%Y/%m/%d/')),
                ('plate_crop_image', models.ImageField(blank=True, null=True, upload_to='detections/plate/%Y/%m/%d/')),
                ('ai_plate_text', models.CharField(blank=True, max_length=20, null=True)),
                ('ai_province', models.CharField(blank=True, max_length=10, null=True)),
                ('ai_series', models.CharField(blank=True, max_length=10, null=True)),
                ('ai_registration_year', models.CharField(blank=True, max_length=4, null=True)),
                ('ai_side_classification', models.CharField(blank=True, choices=[('front', 'Front'), ('back', 'Back')], max_length=5, null=True)),
                ('ai_confidence', models.FloatField(blank=True, null=True)),
                ('ai_detected_violation', models.BooleanField(default=False)),
                ('ai_workflow_version', models.CharField(blank=True, max_length=50, null=True)),
                ('ai_raw_response', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('pending_review', 'Pending Review'), ('confirmed', 'Confirmed'), ('rejected', 'Rejected (False Positive)'), ('flagged_for_dig', 'Flagged for DIG'), ('manually_added', 'Manually Added')], default='pending_review', max_length=20)),
                ('review_notes', models.TextField(blank=True, null=True)),
                ('manual_plate_text', models.CharField(blank=True, max_length=20, null=True)),
                ('manual_violation_type', models.CharField(blank=True, max_length=20, null=True)),
                ('is_manually_annotated', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('camera', models.ForeignKey(blank=True, help_text='Null for detections from video uploads (not tied to a physical camera).', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='detections', to='cameras.camera')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_detections', to='accounts.user')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='detection',
            index=models.Index(fields=['status', 'created_at'], name='detections_det_stat_cre_idx'),
        ),
        migrations.AddIndex(
            model_name='detection',
            index=models.Index(fields=['camera', 'created_at'], name='detections_det_came_cre_idx'),
        ),
        migrations.AddIndex(
            model_name='detection',
            index=models.Index(fields=['reviewed_by', 'reviewed_at'], name='detections_det_revi_rev_idx'),
        ),
        migrations.CreateModel(
            name='DetectionReviewNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.user')),
                ('detection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='review_notes_list', to='detections.detection')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
