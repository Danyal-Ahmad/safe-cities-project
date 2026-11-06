from django.core.management.base import BaseCommand
from django.db import connection


ORPHAN_TABLES = [
    'dig_portal_blacklistentry',
    'dig_portal_challanapproval',
    'dig_portal_faq',
    'dig_portal_leaverequest',
    'dig_portal_officerfeedback',
    'dig_portal_shifthandover',
]

RENAMES = {
    'accounts_user': 'sc_users',
    'accounts_officerprofile': 'sc_officer_profiles',
    'accounts_vehicleregistration': 'sc_vehicle_registrations',
    'accounts_passwordresettoken': 'sc_password_reset_tokens',
    'accounts_user_groups': 'sc_users_groups',
    'accounts_user_user_permissions': 'sc_users_user_permissions',
    'cameras_camera': 'sc_cameras',
    'detections_detection': 'sc_detections',
    'detections_detectionreviewnote': 'sc_detection_review_notes',
    'detections_annotation': 'sc_annotations',
    'challans_challan': 'sc_challans',
    'appeals_challanappeal': 'sc_challan_appeals',
    'realtime_livefeed': 'sc_live_feeds',
    'realtime_cameraassignment': 'sc_camera_assignments',
    'video_processor_videoupload': 'sc_video_uploads',
    'video_processor_videoframe': 'sc_video_frames',
    'dig_portal_systemsettings': 'sc_system_settings',
    'dig_portal_auditlog': 'sc_audit_logs',
    'dig_portal_alert': 'sc_alerts',
    'dig_portal_banner': 'sc_banners',
    'dig_portal_notification': 'sc_notifications',
    'dig_portal_shift': 'sc_shifts',
    'dig_portal_challantemplate': 'sc_challan_templates',
    'it_support_portal_paymentmethod': 'sc_payment_methods',
}


class Command(BaseCommand):
    help = 'Drop unused tables and rename app tables to professional sc_* names.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print actions only')

    def handle(self, *args, **options):
        dry = options['dry_run']
        with connection.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            existing = {r[0] for r in cur.fetchall()}

            self.stdout.write(self.style.MIGRATE_HEADING('1) Drop orphan tables'))
            for t in ORPHAN_TABLES:
                if t in existing:
                    sql = f'DROP TABLE IF EXISTS "{t}" CASCADE'
                    self.stdout.write(f'  DROP {t}')
                    if not dry:
                        cur.execute(sql)
                else:
                    self.stdout.write(f'  skip (missing): {t}')

            self.stdout.write(self.style.MIGRATE_HEADING('2) Rename to sc_*'))
            for old, new in RENAMES.items():
                if old in existing and new not in existing:
                    sql = f'ALTER TABLE "{old}" RENAME TO "{new}"'
                    self.stdout.write(f'  RENAME {old} → {new}')
                    if not dry:
                        cur.execute(sql)
                elif new in existing:
                    self.stdout.write(f'  skip (already): {new}')
                else:
                    self.stdout.write(f'  skip (no source): {old}')

            self.stdout.write(self.style.MIGRATE_HEADING('3) Ensure sc_blacklist'))
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='sc_blacklist'"
            )
            if cur.fetchone():
                self.stdout.write('  sc_blacklist exists')
            else:
                self.stdout.write('  create sc_blacklist via migrate (run migrate after this)')

        if dry:
            self.stdout.write(self.style.WARNING('Dry-run only - no changes applied.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                'Done. Next: python manage.py migrate'
            ))
