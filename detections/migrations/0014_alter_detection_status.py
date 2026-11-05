
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detections', '0013_alter_detection_camera'),
    ]

    operations = [
        migrations.AlterField(
            model_name='detection',
            name='status',
            field=models.CharField(choices=[('pending_review', 'Pending Review'), ('confirmed', 'Confirmed'), ('rejected', 'Rejected (False Positive)'), ('flagged_officer', 'Flagged for Officer Review')], default='pending_review', max_length=20),
        ),
    ]
