
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('it_support_portal', '0001_initial'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='paymentmethod',
            new_name='it_support__status_c535d4_idx',
            old_name='it_support_status_idx',
        ),
        migrations.RenameIndex(
            model_name='paymentmethod',
            new_name='it_support__type_4f548b_idx',
            old_name='it_support_type_idx',
        ),
        migrations.AlterField(
            model_name='paymentmethod',
            name='provider',
            field=models.CharField(help_text="Payment provider / bank name (e.g. 'JazzCash', 'NBP').", max_length=100),
        ),
    ]
