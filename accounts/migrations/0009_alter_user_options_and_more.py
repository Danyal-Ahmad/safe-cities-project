

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_officerprofile_extra_flags'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='user',
            options={},
        ),
        migrations.RenameIndex(
            model_name='passwordresettoken',
            new_name='sc_password_token_e8165d_idx',
            old_name='accounts_pa_token_e975e5_idx',
        ),
        migrations.AlterField(
            model_name='auditorprofile',
            name='audit_scope',
            field=models.CharField(blank=True, default='Full system', help_text='e.g. Financial, Operational, Full system', max_length=100),
        ),
        migrations.AlterField(
            model_name='itprofile',
            name='specialization',
            field=models.CharField(blank=True, default='Infrastructure', help_text='e.g. Infrastructure, CCTV, Database, Network', max_length=100),
        ),
        migrations.AlterField(
            model_name='sspprofile',
            name='high_value_threshold',
            field=models.PositiveIntegerField(default=5000, help_text='Fine amount (PKR) above which SSP attention is required'),
        ),
    ]

