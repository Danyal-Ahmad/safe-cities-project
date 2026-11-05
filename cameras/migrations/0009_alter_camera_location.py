
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cameras', '0008_rename_cameras_cam_is_acti_6478d1_idx_sc_cameras_is_acti_026e9c_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='camera',
            name='location',
            field=models.CharField(help_text="Physical location of the camera (e.g. 'Main Boulevard, Sector III').", max_length=255),
        ),
    ]
