

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appeals', '0004_guest_appeal'),
    ]

    operations = [
        migrations.AlterField(
            model_name='challanappeal',
            name='current_stage',
            field=models.CharField(choices=[('officer', 'Officer Review'), ('ssp', 'SSP Review'), ('dig', 'DIG Review')], default='ssp', max_length=10),
        ),
    ]
