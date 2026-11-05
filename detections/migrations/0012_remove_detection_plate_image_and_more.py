
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detections', '0011_remove_annotation_created_by_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='detection',
            name='plate_image',
        ),
        migrations.RemoveField(
            model_name='detection',
            name='vehicle_image',
        ),
        migrations.AddField(
            model_name='detection',
            name='annotated_image',
            field=models.ImageField(blank=True, help_text='Court-ready annotated evidence frame (violation box, plate box, direction arrow).', null=True, upload_to='detections/annotated/%Y/%m/%d/'),
        ),
        migrations.AddField(
            model_name='detection',
            name='evidence_frame_2',
            field=models.ImageField(blank=True, null=True, upload_to='detections/seq/%Y/%m/%d/'),
        ),
        migrations.AddField(
            model_name='detection',
            name='evidence_frame_3',
            field=models.ImageField(blank=True, null=True, upload_to='detections/seq/%Y/%m/%d/'),
        ),
        migrations.AddField(
            model_name='detection',
            name='evidence_frames_meta',
            field=models.JSONField(blank=True, default=list, help_text='Per-frame capture metadata for the 3-frame evidence sequence.'),
        ),
    ]
