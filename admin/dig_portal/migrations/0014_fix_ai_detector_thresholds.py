from django.db import migrations


def repair_ai_config(apps, schema_editor):
    SystemSettings = apps.get_model('dig_portal', 'SystemSettings')
    for settings_row in SystemSettings.objects.all():
        cfg = settings_row.ai_config
        if not isinstance(cfg, dict):
            continue
        pd = cfg.get('plate_detector')
        changed = False
        if isinstance(pd, dict):
            thr = pd.get('confidence_threshold')
            if thr is None or float(thr) > 0.50:
                pd['confidence_threshold'] = 0.15
                changed = True
            min_area = pd.get('min_box_area_ratio')
            if min_area is None or float(min_area) > 0.002:
                pd['min_box_area_ratio'] = 0.0008
                changed = True
            if pd.get('input_normalize') == '0_1':
                pd['input_normalize'] = 'imagenet'
                changed = True


            if pd.get('person_class_id') == 1:
                pd['person_class_id'] = -1
                changed = True
            if not pd.get('plate_class_ids') or list(pd.get('plate_class_ids')) == [0]:
                pd['plate_class_ids'] = [1]
                changed = True
        if cfg.get('reject_person'):
            cfg['reject_person'] = False
            changed = True
        if changed:
            settings_row.ai_config = cfg
            settings_row.save(update_fields=['ai_config'])


def unapply(apps, schema_editor):

    pass


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0013_blacklist_and_table_names'),
    ]

    operations = [
        migrations.RunPython(repair_ai_config, unapply),
    ]
