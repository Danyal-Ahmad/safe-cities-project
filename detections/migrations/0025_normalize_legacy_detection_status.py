from django.db import migrations

LEGACY_MAP = {
    'pending_review': 'pending',
    'flagged_for_dig': 'flagged_officer',
}


def normalize_statuses(apps, schema_editor):
    Detection = apps.get_model('detections', 'Detection')
    for old, new in LEGACY_MAP.items():
        Detection.objects.filter(status=old).update(status=new)


class Migration(migrations.Migration):
    dependencies = [
        ('detections', '0014_alter_detection_status'),
    ]

    operations = [
        migrations.RunPython(normalize_statuses, migrations.RunPython.noop),
    ]
