
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0004_rename_dig_portal_ale_is_act_aud_idx_dig_portal__is_acti_a586ab_idx_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='banner',
            options={'ordering': ['-priority', '-created_at']},
        ),
        migrations.AddField(
            model_name='banner',
            name='auto_hide_after_search',
            field=models.BooleanField(default=True, help_text='V7.1: Auto-hide the banner once the visitor submits a challan search.'),
        ),
        migrations.AddField(
            model_name='banner',
            name='priority',
            field=models.IntegerField(default=0, help_text='Higher priority banners appear first. Default 0. Use 100 for critical announcements.'),
        ),
        migrations.AddField(
            model_name='banner',
            name='show_on_home_only',
            field=models.BooleanField(default=True, help_text='V7.1: Restrict banner to the public home page only (challans:home).'),
        ),
        migrations.AddField(
            model_name='banner',
            name='start_at',
            field=models.DateTimeField(blank=True, help_text="Optional scheduled start time. Banner won't display before this timestamp.", null=True),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='payment_config',
            field=models.JSONField(blank=True, default=dict, help_text='V7.1: Stores JazzCash, EasyPaisa, Stripe, Bank Transfer config.'),
        ),
    ]
