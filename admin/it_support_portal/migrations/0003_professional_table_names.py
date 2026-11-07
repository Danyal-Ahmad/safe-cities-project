from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('it_support_portal', '0002_rename_it_support_status_idx_it_support__status_c535d4_idx_and_more')]
    operations = [
        migrations.AlterModelTable(name='paymentmethod', table='sc_payment_methods'),
    ]

