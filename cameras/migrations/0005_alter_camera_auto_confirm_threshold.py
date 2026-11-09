

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cameras', '0004_rename_cameras_cam_is_act_is_str_idx_cameras_cam_is_acti_6478d1_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='camera',
            name='auto_confirm_threshold',
            field=models.FloatField(default=0.7, help_text='Minimum combined AI confidence (plate detection + side classification) for the system to AUTO-CONFIRM a violation and create a Challan without officer review. Detections below this threshold go to the officer review queue. Default = 0.70 (70%).'),
        ),
    ]
