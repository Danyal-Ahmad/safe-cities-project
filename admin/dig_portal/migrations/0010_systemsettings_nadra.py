from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0009_systemsettings_ai_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='nadra_api_url',
            field=models.CharField(blank=True, help_text='NADRA Verisys / CNIC verification endpoint', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='nadra_api_key',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

