from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger('cameras.heartbeat')

class Command(BaseCommand):
    help = "Scan active cameras and mark those without recent heartbeats as offline."

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout-seconds',
            type=int,
            default=120,
            help="Threshold in seconds of inactivity before marking offline (default 120)."
        )

    def handle(self, *args, **options):
        from cameras.models import Camera
        timeout_sec = options['timeout_seconds']
        cutoff = timezone.now() - timedelta(seconds=timeout_sec)

        stale_cameras = Camera.objects.filter(
            is_active=True,
            health_status='online'
        ).filter(
            last_health_check__lt=cutoff
        )

        count = 0
        for cam in stale_cameras:
            cam.health_status = 'offline'
            cam.save(update_fields=['health_status'])
            count += 1
            self.stdout.write(self.style.WARNING(f"Camera {cam.camera_id} timed out -> marked offline"))

        self.stdout.write(self.style.SUCCESS(f"Heartbeat scan complete: {count} cameras marked offline."))
