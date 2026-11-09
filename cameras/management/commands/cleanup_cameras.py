from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = "Audit the camera table for stale/duplicate/orphaned records. Read-only unless --fix-* is passed."

    def add_arguments(self, parser):
        parser.add_argument('--fix-duplicates', action='store_true',
                             help="Deactivate (not delete) all but the newest camera in each duplicate camera_id group.")
        parser.add_argument('--fix-stale-health', action='store_true',
                             help="Mark cameras as 'offline' if last_health_check is older than --stale-hours (default 24) and currently shows 'online'.")
        parser.add_argument('--stale-hours', type=int, default=24)

    def handle(self, *args, **opts):
        from cameras.models import Camera
        from realtime.models import CameraAssignment, LiveFeed
        from detections.models import Detection

        self.stdout.write(self.style.MIGRATE_HEADING("Camera database audit"))

        total = Camera.objects.count()
        self.stdout.write(f"Total cameras: {total}")

        dupes = (Camera.objects.values('camera_id')
                 .annotate(n=Count('id')).filter(n__gt=1))
        if dupes:
            self.stdout.write(self.style.WARNING(f"\nDuplicate camera_id values: {len(dupes)}"))
            for d in dupes:
                rows = list(Camera.objects.filter(camera_id=d['camera_id']).order_by('-installed_date'))
                self.stdout.write(f"  {d['camera_id']}: pks {[r.pk for r in rows]}")
                if opts['fix_duplicates']:
                    for extra in rows[1:]:
                        extra.is_active = False
                        extra.save(update_fields=['is_active'])
                        self.stdout.write(self.style.SUCCESS(f"    deactivated pk={extra.pk} (kept pk={rows[0].pk} active)"))
        else:
            self.stdout.write(self.style.SUCCESS("No duplicate camera_id values."))

        misconfigured = Camera.objects.filter(is_streaming=True, rtsp_url__isnull=True, http_snapshot_url__isnull=True)
        if misconfigured.exists():
            self.stdout.write(self.style.WARNING(f"\nCameras marked is_streaming=True with no rtsp_url/http_snapshot_url: {misconfigured.count()}"))
            for c in misconfigured:
                self.stdout.write(f"  pk={c.pk} {c.camera_id} | {c.location}")
        else:
            self.stdout.write(self.style.SUCCESS("No streaming-enabled cameras missing a stream URL."))

        cutoff = timezone.now() - timedelta(hours=opts['stale_hours'])
        stale = Camera.objects.filter(health_status='online').filter(
            last_health_check__lt=cutoff
        ) | Camera.objects.filter(health_status='online', last_health_check__isnull=True)
        stale = stale.distinct()
        if stale.exists():
            self.stdout.write(self.style.WARNING(
                f"\nCameras reporting 'online' with no health check in the last {opts['stale_hours']}h: {stale.count()}"))
            for c in stale:
                self.stdout.write(f"  pk={c.pk} {c.camera_id} - last_health_check={c.last_health_check}")
                if opts['fix_stale_health']:
                    c.health_status = 'offline'
                    c.save(update_fields=['health_status'])
                    self.stdout.write(self.style.SUCCESS(f"    marked pk={c.pk} offline"))
        else:
            self.stdout.write(self.style.SUCCESS("No stale 'online' cameras."))

        orphan_detections = Detection.objects.filter(camera__isnull=False).exclude(
            camera_id__in=Camera.objects.values_list('id', flat=True))
        orphan_assignments = CameraAssignment.objects.exclude(
            camera_id__in=Camera.objects.values_list('id', flat=True))
        orphan_feeds = LiveFeed.objects.filter(camera__isnull=False).exclude(
            camera_id__in=Camera.objects.values_list('id', flat=True))
        n_od, n_oa, n_of = orphan_detections.count(), orphan_assignments.count(), orphan_feeds.count()
        if n_od or n_oa or n_of:
            self.stdout.write(self.style.ERROR(
                f"\nOrphaned rows found (should not be possible with FK constraints - "
                f"investigate immediately): detections={n_od} assignments={n_oa} live_feeds={n_of}"))
        else:
            self.stdout.write(self.style.SUCCESS("No orphaned detection/assignment/live-feed rows."))

        unused = Camera.objects.annotate(n=Count('detections')).filter(n=0)
        if unused.exists():
            self.stdout.write(self.style.WARNING(f"\nCameras with zero detections ever recorded: {unused.count()}"))
            for c in unused:
                self.stdout.write(f"  pk={c.pk} {c.camera_id} | {c.location} (active={c.is_active})")

        self.stdout.write(self.style.MIGRATE_HEADING("\nDone. Nothing was deleted. Use --fix-duplicates / --fix-stale-health to apply the safe fixes above."))

