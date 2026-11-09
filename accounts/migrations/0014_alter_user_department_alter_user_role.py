

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_remove_officerprofile_can_add_manual_challan'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='department',
            field=models.CharField(blank=True, help_text="Department name (e.g. 'Traffic Enforcement')", max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('DIG', 'DIG (Super Admin)'), ('SSP', 'SSP | Senior Superintendent'), ('SUPV', 'Supervisor'), ('OFFICER', 'Officer'), ('AUDIT', 'Audit Officer'), ('IT', 'IT Support'), ('USER', 'Registered Citizen')], default='USER', max_length=10),
        ),
    ]

