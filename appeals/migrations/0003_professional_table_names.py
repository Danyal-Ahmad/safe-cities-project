from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('appeals', '0002_appeal_routing_chain')]
    operations = [
        migrations.AlterModelTable(name='challanappeal', table='sc_challan_appeals'),
    ]

