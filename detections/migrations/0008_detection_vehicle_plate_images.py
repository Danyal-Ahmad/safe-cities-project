from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detections', '0007_professional_table_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='detection',
            name='vehicle_image',
            field=models.ImageField(blank=True, null=True, upload_to='detections/vehicle/%Y/%m/%d/'),
        ),
        migrations.AddField(
            model_name='detection',
            name='plate_image',
            field=models.ImageField(blank=True, null=True, upload_to='detections/plate/%Y/%m/%d/'),
        ),
    ]

