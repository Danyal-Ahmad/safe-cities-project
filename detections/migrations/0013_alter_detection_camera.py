
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cameras', '0010_alter_camera_legal_direction'),
        ('detections', '0012_remove_detection_plate_image_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='detection',
            name='camera',
            field=models.ForeignKey(blank=True, help_text='Null for detections from video uploads, or after the source camera record has been deleted. Detections/evidence are preserved even if the camera is removed (SET_NULL, not CASCADE) - deleting a camera must never destroy violation evidence or challan history.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='detections', to='cameras.camera'),
        ),
    ]
