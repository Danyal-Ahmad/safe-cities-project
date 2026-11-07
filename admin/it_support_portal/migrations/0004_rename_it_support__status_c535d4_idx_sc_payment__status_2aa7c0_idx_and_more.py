

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('it_support_portal', '0003_professional_table_names'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='paymentmethod',
            new_name='sc_payment__status_2aa7c0_idx',
            old_name='it_support__status_c535d4_idx',
        ),
        migrations.RenameIndex(
            model_name='paymentmethod',
            new_name='sc_payment__type_f2236e_idx',
            old_name='it_support__type_4f548b_idx',
        ),
        migrations.AlterField(
            model_name='paymentmethod',
            name='name',
            field=models.CharField(help_text="Display name (e.g. 'JazzCash', 'EasyPaisa', 'Card').", max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name='paymentmethod',
            name='provider',
            field=models.CharField(help_text="Payment provider (e.g. 'JazzCash', 'EasyPaisa').", max_length=100),
        ),
        migrations.AlterField(
            model_name='paymentmethod',
            name='type',
            field=models.CharField(choices=[('wallet', 'Mobile Wallet'), ('card', 'Card Payment'), ('gateway', 'Payment Gateway')], default='wallet', max_length=20),
        ),
    ]

