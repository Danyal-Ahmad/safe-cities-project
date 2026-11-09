

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('challans', '0005_challan_payment_method_challan_txn_ref_and_more'),
        ('detections', '0013_alter_detection_camera'),
    ]

    operations = [
        migrations.AlterField(
            model_name='challan',
            name='detection',
            field=models.OneToOneField(blank=True, help_text='One detection can produce at most one challan (DB-enforced).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='challans', to='detections.detection'),
        ),
    ]

