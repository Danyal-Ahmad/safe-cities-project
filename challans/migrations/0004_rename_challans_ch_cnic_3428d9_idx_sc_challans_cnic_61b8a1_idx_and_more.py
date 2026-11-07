

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('challans', '0003_professional_table_names'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='challan',
            new_name='sc_challans_cnic_61b8a1_idx',
            old_name='challans_ch_cnic_3428d9_idx',
        ),
        migrations.RenameIndex(
            model_name='challan',
            new_name='sc_challans_plate_n_13052a_idx',
            old_name='challans_ch_plate_n_06d274_idx',
        ),
        migrations.RenameIndex(
            model_name='challan',
            new_name='sc_challans_payment_33f1b1_idx',
            old_name='challans_ch_payment_613e1e_idx',
        ),
        migrations.RenameIndex(
            model_name='challan',
            new_name='sc_challans_issue_d_2c6a9a_idx',
            old_name='challans_ch_issue_d_2c457d_idx',
        ),
    ]
