
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cameras', '0002_camera_degraded_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='camera',
            name='auto_confirm_threshold',
            field=models.FloatField(default=0.85, help_text='Minimum combined AI confidence (plate detection + side classification) for the system to AUTO-CONFIRM a violation and create a Challan without officer review. Detections below this threshold go to the officer review queue. Default = 0.85 (85%).'),
        ),
        migrations.AddField(
            model_name='camera',
            name='violation_side',
            field=models.CharField(choices=[('back', 'Back side = violation (default)'), ('front', 'Front side = violation (inverted)')], default='back', help_text="Which side of the car (as classified by the ONNX model) counts as a wrong-way violation at THIS camera. Default = back. Flip to 'front' if this camera is mounted to capture oncoming traffic (e.g. on the opposite side of the road).", max_length=5),
        ),
        migrations.AlterField(
            model_name='camera',
            name='legal_direction',
            field=models.CharField(choices=[('N', 'North'), ('S', 'South'), ('E', 'East'), ('W', 'West')], default='N', help_text='Pool / mounting direction of this camera (N/S/E/W). Used for physical placement labelling only - does NOT decide what counts as a violation.', max_length=10),
        ),
    ]
