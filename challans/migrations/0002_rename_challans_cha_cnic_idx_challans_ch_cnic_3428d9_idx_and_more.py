
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('challans', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='challan',
            new_name='challans_ch_cnic_3428d9_idx',
            old_name='challans_cha_cnic_idx',
        ),
        migrations.RenameIndex(
            model_name='challan',
            new_name='challans_ch_plate_n_06d274_idx',
            old_name='challans_cha_plate_idx',
        ),
        migrations.RenameIndex(
            model_name='challan',
            new_name='challans_ch_payment_613e1e_idx',
            old_name='challans_cha_payme_idx',
        ),
        migrations.RenameIndex(
            model_name='challan',
            new_name='challans_ch_issue_d_2c457d_idx',
            old_name='challans_cha_issue_idx',
        ),
        migrations.AlterField(
            model_name='challan',
            name='created_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='challans_created', to=settings.AUTH_USER_MODEL),
        ),
    ]
