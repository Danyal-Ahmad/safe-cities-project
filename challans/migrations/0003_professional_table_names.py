from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('challans', '0002_rename_challans_cha_cnic_idx_challans_ch_cnic_3428d9_idx_and_more')]
    operations = [
        migrations.AlterModelTable(name='challan', table='sc_challans'),
    ]

