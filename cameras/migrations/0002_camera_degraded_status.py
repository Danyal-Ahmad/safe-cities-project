


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cameras', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='camera',
            name='health_status',
            field=models.CharField(
                choices=[('online', 'Online'), ('offline', 'Offline'),
                         ('unknown', 'Unknown'), ('degraded', 'Degraded')],
                default='unknown', max_length=20),
        ),
    ]
