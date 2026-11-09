from django.db import migrations

OLD_SEED_TEMPLATE_NAMES = (
    'Safe City E-Challan (A4)',
    'Safe City Compact',
    'Legal Notice 99-A',
    'Digital Slip',
)

LEGACY_TEMPLATE_KEYS = (
    'modern_a4',
    'classic_a4',
    'legal_notice_99a',
    'digital_slip',
    'safecityfyp_classic',
)


def remove_legacy_templates_and_reset(apps, schema_editor):
    ChallanTemplate = apps.get_model('dig_portal', 'ChallanTemplate')
    SystemSettings = apps.get_model('dig_portal', 'SystemSettings')
    ChallanTemplate.objects.filter(name__in=OLD_SEED_TEMPLATE_NAMES).delete()
    for settings in SystemSettings.objects.all():
        key = (settings.pdf_template or 'standard_a4').strip()
        if key in LEGACY_TEMPLATE_KEYS:
            settings.pdf_template = 'standard_a4'
            settings.save(update_fields=['pdf_template'])


def restore_legacy_state(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0016_systemsettings_audit_pdf_template_auditpdftemplate'),
    ]

    operations = [
        migrations.RunPython(remove_legacy_templates_and_reset, restore_legacy_state),
    ]
