
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detections', '0004_annotation'),
        ('video_processor', '0002_rename_video_pro_vid_upl_fra_idx_video_proce_video_u_702982_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='detection',
            name='source_video_upload',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pipeline_detections', to='video_processor.videoupload'),
        ),
    ]
