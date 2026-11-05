
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cameras', '0008_rename_cameras_cam_is_acti_6478d1_idx_sc_cameras_is_acti_026e9c_idx_and_more'),
        ('challans', '0004_rename_challans_ch_cnic_3428d9_idx_sc_challans_cnic_61b8a1_idx_and_more'),
        ('detections', '0010_detection_updated_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='challan',
            name='payment_method',
            field=models.CharField(blank=True, help_text='Payment method used (e.g. JazzCash, EasyPaisa, Card)', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='challan',
            name='txn_ref',
            field=models.CharField(blank=True, help_text='Transaction reference from payment gateway', max_length=100, null=True),
        ),
        migrations.AddIndex(
            model_name='challan',
            index=models.Index(fields=['txn_ref'], name='sc_challans_txn_ref_085794_idx'),
        ),
    ]
