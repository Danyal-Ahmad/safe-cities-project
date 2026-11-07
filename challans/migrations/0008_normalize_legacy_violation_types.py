from django.db import migrations


VALID_KEYS = ('wrong_way', 'no_helmet', 'signal_break', 'over_speed', 'other')

ALIASES = {
    'WRONG_WAY': 'wrong_way',
    'WRONG-WAY': 'wrong_way',
    'WRONG WAY': 'wrong_way',
    'wrong-way': 'wrong_way',
    'NO_HELMET': 'no_helmet',
    'SIGNAL_BREAK': 'signal_break',
    'OVER_SPEED': 'over_speed',
    'OTHER': 'other',
}


def normalize_violation_types(apps, schema_editor):
    Challan = apps.get_model('challans', 'Challan')
    updated = 0
    for ch in Challan.objects.exclude(violation_type__in=VALID_KEYS):
        raw = (ch.violation_type or '').strip()
        fixed = ALIASES.get(raw)
        if fixed is None and raw:
            lowered = raw.lower().replace(' ', '_')
            if lowered in VALID_KEYS:
                fixed = lowered
        if not fixed:
            fixed = 'other'
        ch.violation_type = fixed
        ch.save(update_fields=['violation_type'])
        updated += 1
    if updated:
        print(f'challans 0008: normalized {updated} legacy violation_type rows')


def restore_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('challans', '0007_alter_challan_violation_type'),
    ]

    operations = [
        migrations.RunPython(normalize_violation_types, restore_noop),
    ]

