from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0010_systemsettings_nadra'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='integration_mode',
            field=models.CharField(
                choices=[('demo', 'Demo'), ('real', 'Real')],
                default='demo',
                help_text='demo: sandbox Excise/NADRA/payments; real: use configured live endpoints',
                max_length=10,
            ),
        ),
    ]

