"""
Unified Live Tracking Service — single source of truth for detection trail data.

IT Support (unrestricted) and Officer (assignment-scoped) portals use this service. DIG does not.
"""
from __future__ import annotations

from typing import Optional
from django.db.models import Q, QuerySet

from detections.models import Detection
from cameras.models import Camera
from accounts.models import User
from realtime.models import CameraAssignment


class LiveTrackingService:
    """Service for retrieving live tracking data with proper access control."""

    DEFAULT_STATUSES = [
        Detection.PENDING,
        Detection.CONFIRMED,
        Detection.FLAGGED,
    ]

    def __init__(self, user: User, selected_camera_id: Optional[str] = None,
                 plate_query: str = '', status_filter: str = '',
                 limit: int = 80):
        self.user = user
        self.selected_camera_id = selected_camera_id
        self.plate_query = plate_query.strip().upper()
        self.status_filter = status_filter.strip()
        self.limit = limit
        self._camera = None
        self._camera_not_found = False

    @property
    def camera(self) -> Optional[Camera]:
        if self._camera is None and self.selected_camera_id:
            try:
                self._camera = Camera.objects.filter(pk=self.selected_camera_id).first()
                if self._camera is None:
                    self._camera_not_found = True
            except (ValueError, TypeError):
                self._camera = None
                self._camera_not_found = True
        return self._camera

    @property
    def camera_not_found(self) -> bool:
        _ = self.camera  # triggers property logic
        return self._camera_not_found

    def get_available_cameras(self) -> list[Camera]:
        """Get cameras user can access."""
        if self.user.role in (User.DIG, User.SSP, User.AUDIT, User.IT_SUPPORT):
            return list(Camera.objects.all().order_by('-is_active', '-installed_date')[:100])
        assigned_ids = list(CameraAssignment.objects.filter(
            officer=self.user, is_active=True
        ).values_list('camera_id', flat=True)[:1])
        return list(Camera.objects.filter(id__in=assigned_ids).order_by('camera_id')[:1])

    def get_base_queryset(self) -> QuerySet:
        """Base queryset with camera access control."""
        qs = Detection.objects.select_related('camera').order_by('-created_at')

        if self.user.role in (User.DIG, User.SSP, User.AUDIT, User.IT_SUPPORT):
            pass
        else:
            assigned_ids = list(CameraAssignment.objects.filter(
                officer=self.user, is_active=True
            ).values_list('camera_id', flat=True)[:1])
            qs = qs.filter(Q(camera_id__in=assigned_ids) | Q(camera__isnull=True))

        if self.selected_camera_id and not self.camera_not_found:
            qs = qs.filter(camera_id=self.selected_camera_id)
        elif self.camera_not_found:
            return qs.none()

        if self.plate_query:
            qs = qs.filter(ai_plate_text__icontains=self.plate_query)

        if self.status_filter:
            qs = qs.filter(status=self.status_filter)
        else:
            qs = qs.filter(status__in=self.DEFAULT_STATUSES)

        return qs

    def get_recent_detections(self) -> list[Detection]:
        """Get recent detections for the trail."""
        return list(self.get_base_queryset()[:self.limit])

    def get_latest_detection(self) -> Optional[Detection]:
        """Get the most recent detection."""
        detections = self.get_recent_detections()
        return detections[0] if detections else None

    def get_stats(self, detections: list[Detection]) -> dict:
        """Calculate summary statistics."""
        total = len(detections)
        if total == 0:
            return {
                'total': 0, 'violations': 0, 'pending': 0,
                'unique_plates': 0, 'avg_confidence': None,
            }

        violations = sum(1 for d in detections
                         if d.ai_detected_violation or (d.ai_confidence or 0) >= 0.55)
        pending = sum(1 for d in detections if d.status == Detection.PENDING)
        plates = {d.effective_plate for d in detections if d.effective_plate}
        confs = [float(d.ai_confidence) for d in detections if d.ai_confidence is not None]
        avg_conf = round(sum(confs) / len(confs) * 100, 1) if confs else None

        return {
            'total': total,
            'violations': violations,
            'pending': pending,
            'unique_plates': len(plates),
            'avg_confidence': avg_conf,
        }

    def serialize_detections(self, detections: list[Detection]) -> list[dict]:
        """Serialize detections for JSON API."""
        items = []
        for d in detections:
            raw = d.ai_raw_response or {}
            if isinstance(raw, str):
                raw = {}

            bbox_norm = raw.get('bbox_norm')
            if not bbox_norm and raw.get('plate_detections'):
                try:
                    bbox_norm = raw['plate_detections'][0].get('bbox_norm')
                except Exception:
                    bbox_norm = None
            vehicle_bbox_norm = raw.get('vehicle_bbox_norm')
            if not vehicle_bbox_norm:
                vb = raw.get('vehicle_bbox')
                if vb and len(vb) == 4:
                    try:
                        w_img = float((raw.get('image_size') or [0, 0])[0]) or None
                        h_img = float((raw.get('image_size') or [0, 0])[1]) or None
                        if w_img and h_img:
                            vehicle_bbox_norm = [
                                float(vb[0]) / w_img, float(vb[1]) / h_img,
                                float(vb[2]) / w_img, float(vb[3]) / h_img,
                            ]
                    except Exception:
                        vehicle_bbox_norm = None

            conf = float(d.ai_confidence or 0)
            cam = d.camera

            items.append({
                'id': d.id,
                'plate': d.effective_plate or '—',
                'side': d.ai_side_classification or '',
                'confidence': conf,
                'confidence_pct': round(conf * 100, 1),
                'status': d.status,
                'status_label': d.get_status_display(),
                'camera': cam.camera_id if cam else None,
                'camera_id': cam.id if cam else None,
                'camera_location': cam.location if cam else None,
                'legal_direction': getattr(cam, 'legal_direction', None) if cam else None,
                'legal_direction_label': {'N':'North','S':'South','E':'East','W':'West'}.get(getattr(cam, 'legal_direction', None), getattr(cam, 'legal_direction', None) or '—') if cam else '—',
                'violation_side': getattr(cam, 'violation_side', None) if cam else None,
                'travel_hint': ('Towards camera' if (d.ai_side_classification or '').lower() in ('front','f') else ('Away from camera' if (d.ai_side_classification or '').lower() in ('back','rear','b') else 'Unknown')),
                'side_label': (d.get_ai_side_classification_display() if hasattr(d, 'get_ai_side_classification_display') else (d.ai_side_classification or '—')),

                'raw_image': d.raw_image.url if d.raw_image else None,
                'plate_crop': d.plate_crop_image.url if d.plate_crop_image else None,
                'timestamp': d.created_at.isoformat() if d.created_at else None,
                'violation': bool(d.ai_detected_violation) or conf >= 0.55,
                'violation_type': d.effective_violation_type,
                'bbox_norm': bbox_norm,
                'vehicle_bbox_norm': vehicle_bbox_norm,
                'image_w': (raw.get('image_size') or [None, None])[0],
                'image_h': (raw.get('image_size') or [None, None])[1],
                'province': d.ai_province or '',
                'series': d.ai_series or '',
                'registration_year': d.ai_registration_year or '',
            })
        return items

    def resolve_stream_url(self, camera: Optional[Camera] = None) -> Optional[str]:
        """Best playable URL: uploaded demo video > HTTP/MJPEG > RTSP string."""
        cam = camera or self.camera
        if not cam:
            return None
        try:
            from realtime.models import LiveFeed
            feed = (
                LiveFeed.objects
                .filter(camera=cam, is_active=True)
                .order_by('-created_at')
                .first()
            )
            if feed is not None:
                vf = getattr(feed, 'video_file', None)
                if vf and getattr(vf, 'url', None):
                    return vf.url
                su = (getattr(feed, 'stream_url', None) or '').strip()
                if su:
                    return su
        except Exception:
            pass
        for attr in ('http_snapshot_url', 'rtsp_url'):
            url = (getattr(cam, attr, None) or '').strip()
            if not url:
                continue
            low = url.lower()
            if any(x in low for x in ('.mp4', '.webm', '.ogg', '/media/', 'http://', 'https://', 'mjpeg', 'mjpg')):
                return url
        for attr in ('http_snapshot_url', 'rtsp_url'):
            url = (getattr(cam, attr, None) or '').strip()
            if url:
                return url
        return None

    def enforce_officer_one_camera(self) -> None:
        """If officer has >1 active assignment, keep newest only."""
        if self.user.role != User.OFFICER:
            return
        qs = CameraAssignment.objects.filter(officer=self.user, is_active=True).order_by('-assigned_at', '-id')
        keep = qs.first()
        if keep:
            qs.exclude(pk=keep.pk).update(is_active=False)
