

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0011_systemsettings_integration_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='pdf_template',
            field=models.CharField(blank=True, default='safecityfyp_classic', help_text="Active PDF template key. File template = filename under templates/challan/challan_templates/ without .html. DB template = 'db:<ChallanTemplate id>'.", max_length=100),
        ),
        migrations.AlterField(
            model_name='banner',
            name='placement',
            field=models.CharField(choices=[('top', 'Top of page'), ('bottom', 'Bottom of page'), ('ad', 'Banner - Public Service Announcement Space'), ('popup', 'POPUP banner')], default='top', max_length=10),
        ),
        migrations.AlterField(
            model_name='challantemplate',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='challan_templates/%Y/%m/'),
        ),
        migrations.AlterField(
            model_name='systemsettings',
            name='ai_confidence_threshold',
            field=models.FloatField(default=0.75, help_text='Minimum confidence to accept a car detection (model default target 0.90)'),
        ),
    ]

