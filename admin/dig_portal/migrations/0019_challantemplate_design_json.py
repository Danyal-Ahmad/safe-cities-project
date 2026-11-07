

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0018_challantemplate_description_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='challantemplate',
            name='design_json',
            field=models.TextField(blank=True, default='', help_text='Challan Studio structured document (blocks + theme).'),
        ),
    ]

