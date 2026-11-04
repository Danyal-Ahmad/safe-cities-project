"""Add 4 quadrant image fields to Detection for manual officer annotation."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detections', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='detection',
            name='manual_q1_image',
            field=models.ImageField(blank=True, help_text='Top-left quadrant of the manually annotated frame.', null=True, upload_to='detections/manual/q1/%Y/%m/%d/'),
        ),
        migrations.AddField(
            model_name='detection',
            name='manual_q2_image',
            field=models.ImageField(blank=True, help_text='Top-right quadrant of the manually annotated frame.', null=True, upload_to='detections/manual/q2/%Y/%m/%d/'),
        ),
        migrations.AddField(
            model_name='detection',
            name='manual_q3_image',
            field=models.ImageField(blank=True, help_text='Bottom-left quadrant of the manually annotated frame.', null=True, upload_to='detections/manual/q3/%Y/%m/%d/'),
        ),
        migrations.AddField(
            model_name='detection',
            name='manual_q4_image',
            field=models.ImageField(blank=True, help_text='Bottom-right quadrant of the manually annotated frame.', null=True, upload_to='detections/manual/q4/%Y/%m/%d/'),
        ),
    ]
