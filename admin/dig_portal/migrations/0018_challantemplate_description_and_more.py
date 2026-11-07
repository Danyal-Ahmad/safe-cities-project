

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0017_replace_legacy_challan_templates'),
    ]

    operations = [
        migrations.AddField(
            model_name='challantemplate',
            name='description',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='challantemplate',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]

