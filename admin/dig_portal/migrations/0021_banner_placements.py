

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0020_auditlog_device_auditlog_user_agent_loginevent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='banner',
            name='placement',
            field=models.CharField(choices=[('static_post', 'Static post ad (home, hidden staging)'), ('popup', 'Popup ad (home only)'), ('ticker', 'Ticker ad (portals + home)'), ('push', 'Push notification (portals)'), ('top', 'Top strip (legacy)'), ('bottom', 'Bottom strip (legacy)'), ('ad', 'Legacy ad space (retired)')], default='ticker', max_length=20),
        ),
    ]
