import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection


class Command(BaseCommand):
    help = "Delete ALL data from the database EXCEPT user accounts (admins + citizens)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm', action='store_true',
            help='Skip the interactive confirmation prompt (for use in scripts/bat files).'
        )
        parser.add_argument(
            '--include-systemsettings', action='store_true',
            help='Also delete the SystemSettings singleton (not recommended - will be re-created on next access).'
        )
        parser.add_argument(
            '--include-media', action='store_true',
            help='Also delete uploaded media files (detection images, video uploads, appeal evidence).'
        )
        parser.add_argument(
            '--include-accounts', action='store_true',
            help='DANGER: Also delete all User accounts. Use this ONLY to do a full reset.'
        )

    def handle(self, *args, **options):
        confirm = options['confirm']
        include_ss = options['include_systemsettings']
        include_media = options['include_media']
        include_accounts = options['include_accounts']

        if not confirm:
            self.stdout.write(self.style.WARNING(
                "\n========================================\n"
                "  PURGE DATA - DESTRUCTIVE OPERATION\n"
                "========================================\n"
                "\n"
                "This will DELETE all data from the database EXCEPT:\n"
                "  - User accounts (admins + citizens)\n"
                "  - OfficerProfile (officer permissions)\n"
                "  - VehicleRegistration (citizen vehicles)\n"
                "  - SystemSettings singleton\n"
            ))
            if include_accounts:
                self.stdout.write(self.style.ERROR(
                    "  --include-accounts is set → ALL USER ACCOUNTS WILL ALSO BE DELETED!\n"
                ))
            if include_media:
                self.stdout.write(self.style.WARNING(
                    "  --include-media is set → all uploaded files in media/ will be deleted!\n"
                ))
            response = input("\nType 'yes' to confirm, anything else to abort: ").strip().lower()
            if response != 'yes':
                self.stdout.write(self.style.ERROR("Aborted. No data was deleted."))
                return

        from accounts.models import User, OfficerProfile, VehicleRegistration
        from challans.models import Challan
        from detections.models import Detection, DetectionReviewNote
        from appeals.models import ChallanAppeal
        from cameras.models import Camera
        from realtime.models import LiveFeed, CameraAssignment
        from video_processor.models import VideoUpload, VideoFrame
        from admin.dig_portal.models import (
            SystemSettings, AuditLog, Alert, Banner, Notification,
        )

        before = {
            'Users (preserved)': User.objects.count(),
            'OfficerProfiles (preserved)': OfficerProfile.objects.count(),
            'VehicleRegistrations (preserved)': VehicleRegistration.objects.count(),
            'Challans': Challan.objects.count(),
            'Detections': Detection.objects.count(),
            'DetectionReviewNotes': DetectionReviewNote.objects.count(),
            'ChallanAppeals': ChallanAppeal.objects.count(),
            'Cameras': Camera.objects.count(),
            'LiveFeeds': LiveFeed.objects.count(),
            'CameraAssignments': CameraAssignment.objects.count(),
            'VideoUploads': VideoUpload.objects.count(),
            'VideoFrames': VideoFrame.objects.count(),
            'AuditLogs': AuditLog.objects.count(),
            'Alerts': Alert.objects.count(),
            'Banners': Banner.objects.count(),
            'Notifications': Notification.objects.count(),
        }

        self.stdout.write("\n[Purge] Deleting data in FK-safe order...")

        n = Notification.objects.all().delete()[0]
        if n: self.stdout.write(f"  - Notifications:        {n} deleted")

        n = Banner.objects.all().delete()[0]
        if n: self.stdout.write(f"  - Banners:              {n} deleted")

        n = Alert.objects.all().delete()[0]
        if n: self.stdout.write(f"  - Alerts:               {n} deleted")

        n = AuditLog.objects.all().delete()[0]
        if n: self.stdout.write(f"  - AuditLogs:            {n} deleted")

        n = VideoFrame.objects.all().delete()[0]
        if n: self.stdout.write(f"  - VideoFrames:          {n} deleted")

        n = VideoUpload.objects.all().delete()[0]
        if n: self.stdout.write(f"  - VideoUploads:         {n} deleted")

        n = CameraAssignment.objects.all().delete()[0]
        if n: self.stdout.write(f"  - CameraAssignments:    {n} deleted")

        n = LiveFeed.objects.all().delete()[0]
        if n: self.stdout.write(f"  - LiveFeeds:            {n} deleted")

        n = DetectionReviewNote.objects.all().delete()[0]
        if n: self.stdout.write(f"  - DetectionReviewNotes: {n} deleted")

        n = ChallanAppeal.objects.all().delete()[0]
        if n: self.stdout.write(f"  - ChallanAppeals:       {n} deleted")

        n = Challan.objects.all().delete()[0]
        if n: self.stdout.write(f"  - Challans:             {n} deleted")

        n = Detection.objects.all().delete()[0]
        if n: self.stdout.write(f"  - Detections:           {n} deleted")

        n = Camera.objects.all().delete()[0]
        if n: self.stdout.write(f"  - Cameras:              {n} deleted")

        if include_ss:
            n = SystemSettings.objects.all().delete()[0]
            if n: self.stdout.write(f"  - SystemSettings:       {n} deleted")
        else:
            self.stdout.write("  - SystemSettings:       preserved (singleton)")

        if include_accounts:
            VehicleRegistration.objects.all().delete()
            OfficerProfile.objects.all().delete()
            n = User.objects.all().delete()[0]
            self.stdout.write(self.style.ERROR(
                f"  - Users:                {n} deleted (INCLUDE ACCOUNTS - full reset)"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"  - Users:                PRESERVED ({User.objects.count()} accounts kept)"
            ))

        if include_media:
            media_root = settings.MEDIA_ROOT
            if os.path.isdir(media_root):
                preserved_subdirs = {'banners', 'settings'}
                for entry in os.listdir(media_root):
                    full_path = os.path.join(media_root, entry)
                    if entry in preserved_subdirs:
                        continue
                    if os.path.isdir(full_path):
                        shutil.rmtree(full_path, ignore_errors=True)
                        self.stdout.write(f"  - media/{entry}/ (dir)   deleted")
                    else:
                        os.remove(full_path)
                        self.stdout.write(f"  - media/{entry}          deleted")

        if connection.vendor == 'postgresql':
            self.stdout.write("\n[Purge] Resetting PostgreSQL sequences...")
            with connection.cursor() as cursor:
                tables_to_reset = [
                    'challans_challan',
                    'detections_detection',
                    'detections_detectionreviewnote',
                    'appeals_challanappeal',
                    'cameras_camera',
                    'realtime_livefeed',
                    'realtime_cameraassignment',
                    'video_processor_videoupload',
                    'video_processor_videoframe',
                    'dig_portal_auditlog',
                    'dig_portal_alert',
                    'dig_portal_banner',
                    'dig_portal_notification',
                ]
                if include_ss:
                    tables_to_reset.append('dig_portal_systemsettings')
                for table in tables_to_reset:
                    try:
                        cursor.execute(
                            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), 1, false);"
                        )
                    except Exception:
                        pass
            self.stdout.write("  PostgreSQL sequences reset to 1.")

        self.stdout.write(self.style.SUCCESS(
            "\n========================================\n"
            "  PURGE COMPLETE\n"
            "========================================\n"
        ))
        self.stdout.write("Summary of data BEFORE purge (for audit):")
        for name, count in before.items():
            marker = '✓' if 'preserved' in name else '✗'
            self.stdout.write(f"  {marker} {name:35s} {count}")

        self.stdout.write(self.style.SUCCESS(
            f"\nUser accounts preserved: {User.objects.count()}"
        ))
        if not include_ss:
            self.stdout.write(self.style.SUCCESS(
                f"SystemSettings preserved: {SystemSettings.objects.count()}"
            ))
        self.stdout.write(
            "\nNext steps:\n"
            "  - Run 'python manage.py create_dig_admin' to re-create the DIG admin if needed.\n"
            "  - Add new cameras manually from the DIG portal at /dig/cameras/add/.\n"
        )

