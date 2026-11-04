"""video_processor migration 0001 — VideoUpload + VideoFrame."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        ('detections', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='VideoUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('video_file', models.FileField(help_text='MP4, AVI, MOV — max 200 MB', upload_to='videos/%Y/%m/%d/')),
                ('original_filename', models.CharField(blank=True, max_length=255, null=True)),
                ('status', models.CharField(choices=[('uploaded', 'Uploaded'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='uploaded', max_length=20)),
                ('total_frames_extracted', models.IntegerField(default=0)),
                ('frames_with_plates', models.IntegerField(default=0)),
                ('violations_detected', models.IntegerField(default=0)),
                ('auto_challans_created', models.IntegerField(default=0)),
                ('manual_review_created', models.IntegerField(default=0)),
                ('frames_ignored', models.IntegerField(default=0)),
                ('processing_started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('camera_location', models.CharField(blank=True, help_text='Location where this video was recorded', max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='video_uploads', to='accounts.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='VideoFrame',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('frame_number', models.IntegerField()),
                ('timestamp_secs', models.FloatField(help_text='Timestamp in the video (seconds)')),
                ('frame_image', models.ImageField(blank=True, null=True, upload_to='video_frames/%Y/%m/%d/')),
                ('plate_detected', models.BooleanField(default=False)),
                ('side_classification', models.CharField(blank=True, max_length=5, null=True)),
                ('ai_confidence', models.FloatField(blank=True, null=True)),
                ('ocr_text', models.CharField(blank=True, help_text='OCR-extracted plate text (if available)', max_length=20, null=True)),
                ('ocr_confidence', models.FloatField(blank=True, null=True)),
                ('auto_processed', models.BooleanField(default=False, help_text='True if auto-challan created, False if sent to manual review')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('detection', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='video_frames', to='detections.detection')),
                ('video_upload', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='frames', to='video_processor.videoupload')),
            ],
            options={
                'ordering': ['frame_number'],
            },
        ),
        migrations.AddIndex(
            model_name='videoframe',
            index=models.Index(fields=['video_upload', 'frame_number'], name='video_pro_vid_upl_fra_idx'),
        ),
        migrations.AddIndex(
            model_name='videoframe',
            index=models.Index(fields=['plate_detected', 'auto_processed'], name='video_pro_pla_det_aut_idx'),
        ),
    ]
