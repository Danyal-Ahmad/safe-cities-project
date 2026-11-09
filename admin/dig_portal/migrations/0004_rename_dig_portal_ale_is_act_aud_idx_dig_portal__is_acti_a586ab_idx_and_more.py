

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0003_notification'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='alert',
            new_name='dig_portal__is_acti_a586ab_idx',
            old_name='dig_portal_ale_is_act_aud_idx',
        ),
        migrations.RenameIndex(
            model_name='auditlog',
            new_name='dig_portal__actor_i_04d050_idx',
            old_name='dig_portal_aud_actor_time_idx',
        ),
        migrations.RenameIndex(
            model_name='auditlog',
            new_name='dig_portal__action_d8c340_idx',
            old_name='dig_portal_aud_acti_time_idx',
        ),
        migrations.RenameIndex(
            model_name='auditlog',
            new_name='dig_portal__target__b30440_idx',
            old_name='dig_portal_aud_targ_mod_idx',
        ),
        migrations.RenameIndex(
            model_name='notification',
            new_name='dig_portal__recipie_fe0628_idx',
            old_name='dig_portal_notif_recip_idx',
        ),
        migrations.RenameIndex(
            model_name='notification',
            new_name='dig_portal__categor_620cb7_idx',
            old_name='dig_portal_notif_cat_idx',
        ),
        migrations.AlterField(
            model_name='notification',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='notification',
            name='target_url',
            field=models.CharField(blank=True, default='', help_text='URL to navigate to when clicked (e.g. /dig/appeal/5/override/)', max_length=500),
        ),
    ]

