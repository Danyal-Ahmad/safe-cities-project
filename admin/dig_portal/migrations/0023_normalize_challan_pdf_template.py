from django.db import migrations

NEW_KEYS = ('standard_a4', 'government_grid_a4', 'notice_classic_a4')
LEGACY_KEYS = (
    'modern_a4', 'classic_a4', 'legal_notice_99a', 'digital_slip',
    'command_brief', 'secure_instrument', 'urdu_executive',
    'safecityfyp_classic', 'compact_a4', '',
)


def reset_pdf_template(apps, schema_editor):
    SystemSettings = apps.get_model('dig_portal', 'SystemSettings')
    for row in SystemSettings.objects.all():
        key = (row.pdf_template or '').strip()
        if key.startswith('db:'):
            continue
        if key in NEW_KEYS:
            continue
        row.pdf_template = 'standard_a4'
        row.save(update_fields=['pdf_template'])


def restore_legacy_state(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0022_alter_systemsettings_pdf_template'),
    ]

    operations = [
        migrations.RunPython(reset_pdf_template, restore_legacy_state),
    ]

