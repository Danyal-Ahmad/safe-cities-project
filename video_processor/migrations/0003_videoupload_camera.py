
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cameras', '0004_rename_cameras_cam_is_act_is_str_idx_cameras_cam_is_acti_6478d1_idx_and_more'),
        ('video_processor', '0002_rename_video_pro_vid_upl_fra_idx_video_proce_video_u_702982_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='videoupload',
            name='camera',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='video_uploads', to='cameras.camera'),
        ),
    ]
