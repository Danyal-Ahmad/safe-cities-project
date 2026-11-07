from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.conf import settings as dj_settings

from cameras.models import Camera
from realtime.models import LiveFeed
from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from detections.models import Detection
from django.shortcuts import Http404
from django.db.models import Q
from accounts.decorators import any_permission_required
from django.shortcuts import get_object_or_404
from accounts.decorators import permission_required
from django.shortcuts import render
from accounts.decorators import staff_required


@staff_required
@permission_required('view_live_monitor')
def live_monitor(request):
    from django.urls import reverse as _reverse, NoReverseMatch as _NoReverseMatch

    q = (request.GET.get('q') or '').strip()
    current_ns = getattr(getattr(request, 'resolver_match', None), 'namespace', '') or 'dig'

    camera_qs = Camera.objects.all().order_by('-is_active', '-installed_date')
    if q:
        camera_qs = camera_qs.filter(
            Q(camera_id__icontains=q) | Q(location__icontains=q)
        )
    cameras = list(camera_qs[:200])

    feed_by_cam = {}
    for f in LiveFeed.objects.filter(is_active=True).select_related('camera').order_by('-created_at'):
        if f.camera_id and f.camera_id not in feed_by_cam:
            feed_by_cam[f.camera_id] = f

    cam_ids = [c.id for c in cameras]
    latest_detections = {}
    if cam_ids:
        for d in Detection.objects.filter(camera_id__in=cam_ids).order_by('-created_at'):
            if d.camera_id not in latest_detections:
                if d.status == Detection.CONFIRMED:
                    latest_detections[d.camera_id] = 'confirmed'
                elif d.status == Detection.PENDING:
                    latest_detections[d.camera_id] = 'doubt'
                elif d.status == Detection.REJECTED:
                    latest_detections[d.camera_id] = 'ignored'
                else:
                    latest_detections[d.camera_id] = ''


    snapshot_ns = None
    try:
        user = request.user
        if user.is_authenticated and user.has_any_permission('camera_feed', 'view_cameras'):
            for candidate in dict.fromkeys((current_ns, 'dig')):
                try:
                    _reverse(f'{candidate}:camera_snapshot', args=[0])
                    snapshot_ns = candidate
                    break
                except _NoReverseMatch:
                    continue
    except Exception:
        snapshot_ns = None

    direction_labels = dict(Camera._meta.get_field('legal_direction').choices)

    def _feed_kind(stream):
        low = (stream or '').lower()
        if not low:
            return 'none'
        if low.startswith(('rtsp://', 'rtsps://')):

            return 'snapshot'
        if '/media/' in low or any(ext in low for ext in ('.mp4', '.webm', '.mov', '.m4v', '.avi', '.mkv')):
            return 'video'
        return 'snapshot'

    for c in cameras:
        cid = (c.camera_id or '').strip()
        c.channel_label = ('CAM ' + cid) if cid.isdigit() else (cid or 'CAM')
        c.latest_detection_status = latest_detections.get(c.id, '')
        stream = (c.rtsp_url or '').strip() or (c.http_snapshot_url or '').strip()
        if not stream and c.id in feed_by_cam:
            f = feed_by_cam[c.id]
            try:
                if f.video_file:
                    stream = f.video_file.url
            except Exception:
                stream = ''
        c.playable_stream = stream
        c.feed_kind = _feed_kind(stream)
        c.snapshot_url = _reverse(f'{snapshot_ns}:camera_snapshot', args=[c.id]) if snapshot_ns else ''


        if c.feed_kind == 'video':
            c.camera_type_label = 'ANPR'
        elif c.feed_kind == 'snapshot':
            c.camera_type_label = 'SNAPSHOT'
        else:
            c.camera_type_label = 'NO SOURCE'
        legal = (direction_labels.get(c.legal_direction) or c.legal_direction or 'N')
        c.legal_direction_label = str(legal).upper()
        c.violation_side_label = (c.violation_side or 'back').upper()
        c.meta_line = '%s | LEGAL: %s | VIOLATION: %s' % (
            c.camera_type_label, c.legal_direction_label, c.violation_side_label)
        if stream and c.health_status in ('unknown', '', None):
            c.health_status = 'online'
        if c.health_status == 'online' and stream:
            c.status_key = 'live'
        elif c.health_status == 'online':
            c.status_key = 'nofeed'
        else:
            c.status_key = 'offline'

    live_feeds = list(LiveFeed.objects.filter(is_active=True).order_by('-created_at')[:50])
    all_cameras = cameras

    online_count = sum(1 for c in cameras if c.health_status == 'online' or getattr(c, 'playable_stream', None))
    offline_count = max(0, len(cameras) - online_count)
    no_feed_count = sum(1 for c in cameras if c.feed_kind == 'none')

    recent_detections = []
    if cam_ids:
        recent_detections = list(
            Detection.objects.filter(camera_id__in=cam_ids).order_by('-created_at')[:10]
        )

    feed_url = ''
    try:
        feed_url = _reverse(f'{current_ns}:live_monitor_feed')
    except _NoReverseMatch:
        feed_url = ''

    registry_url = ''
    for candidate in dict.fromkeys((current_ns, 'dig')):
        try:
            registry_url = _reverse(f'{candidate}:camera_list')
            break
        except _NoReverseMatch:
            continue

    return render(request, 'dashboard/dig/live_monitor.html', {
        'cameras': cameras,
        'live_feeds': live_feeds,
        'all_cameras': all_cameras,
        'online_count': online_count,
        'offline_count': offline_count,
        'no_feed_count': no_feed_count,
        'total_cameras': len(cameras),
        'recent_detections': recent_detections,
        'q': q,
        'feed_url': feed_url,
        'registry_url': registry_url,
    })


@staff_required
@permission_required('view_live_monitor')
def live_monitor_feed(request):
    from detections.models import Detection

    cameras = Camera.objects.all()
    online_count = cameras.filter(health_status='online').count()
    total_cameras = cameras.count()
    offline_count = max(0, total_cameras - online_count)

    recent = list(Detection.objects.select_related('camera').order_by('-created_at')[:10])
    items = []
    for d in recent:
        items.append({
            'id': d.id,
            'camera_id': d.camera.camera_id if d.camera else None,
            'plate': d.effective_plate or None,
            'violation_type': d.effective_violation_type or None,
            'status': d.status,
            'created_at': d.created_at.isoformat() if d.created_at else None,
            'created_at_display': d.created_at.strftime('%H:%M:%S') if d.created_at else '',
        })

    return JsonResponse({
        'online_count': online_count,
        'offline_count': offline_count,
        'total_cameras': total_cameras,
        'recent_detections': items,
        'server_time': timezone.now().isoformat(),
    })


@permission_required('live_tracking')
def live_tracking(request):
    from admin.shared import LiveTrackingService
    from detections.models import Detection

    cam_id = request.GET.get('camera_id') or request.GET.get('camera') or ''
    service = LiveTrackingService(
        user=request.user,
        selected_camera_id=cam_id or None,
        plate_query=request.GET.get('plate') or '',
        status_filter=request.GET.get('status') or '',
        limit=80,
    )
    cameras = service.get_available_cameras()
    if not service.selected_camera_id and cameras:
        service.selected_camera_id = str(cameras[0].id)
    recent = service.get_recent_detections()
    latest_detection = recent[0] if recent else None
    stats = service.get_stats(recent)
    return render(request, 'dashboard/shared/live_tracking.html', {
        'cameras': cameras,
        'has_assignment': bool(cameras),
        'selected_camera': service.camera,
        'stream_url': service.resolve_stream_url(),
        'selected_camera_id': service.selected_camera_id or '',
        'camera_not_found': service.camera_not_found,
        'plate_q': service.plate_query,
        'status_q': service.status_filter,
        'recent_detections': recent,
        'latest_detection': latest_detection,
        'live_feeds': [],
        'stat_total': stats['total'],
        'stat_violations': stats['violations'],
        'stat_pending': stats['pending'],
        'stat_unique_plates': stats['unique_plates'],
        'stat_avg_conf': stats['avg_confidence'],
        'status_choices': getattr(Detection, 'STATUS_CHOICES', ()),
    })


@any_permission_required('camera_feed', 'view_cameras')
def camera_snapshot(request, camera_id):
    from django.http import FileResponse as _FileResponse
    from django.conf import settings as dj_settings
    import os
    camera = get_object_or_404(Camera, pk=camera_id)
    if request.user.role == 'OFFICER':
        from realtime.models import CameraAssignment
        if not CameraAssignment.objects.filter(camera=camera, officer=request.user, is_active=True).exists():
            raise Http404

    latest = Detection.objects.filter(camera=camera).order_by('-created_at').first()
    if latest and latest.raw_image:
        try:
            return _FileResponse(open(latest.raw_image.path, 'rb'), content_type='image/jpeg')
        except Exception:
            pass

    if camera.http_snapshot_url and not camera.http_snapshot_url.startswith(('/media/', 'media/')):
        try:
            import urllib.request
            req = urllib.request.Request(camera.http_snapshot_url, headers={'User-Agent': 'SafeCity/1.0'})
            resp = urllib.request.urlopen(req, timeout=5)
            return HttpResponse(resp.read(), content_type='image/jpeg')
        except Exception:
            pass

    video_url = (camera.rtsp_url or camera.http_snapshot_url or '').strip()
    if video_url:
        media_url = (dj_settings.MEDIA_URL or '/media/').rstrip('/') + '/'
        rel = video_url
        if video_url.startswith(media_url):
            rel = video_url[len(media_url):]
        elif video_url.startswith('/media/'):
            rel = video_url[len('/media/'):]
        elif video_url.startswith('media/'):
            rel = video_url[len('media/'):]
        lower = rel.lower()
        if any(lower.endswith(ext) for ext in ('.mp4', '.avi', '.mkv', '.mov', '.webm', '.m4v')):
            abs_path = os.path.join(dj_settings.MEDIA_ROOT, rel.replace('/', os.sep))
            if os.path.isfile(abs_path):
                try:
                    import cv2
                    cap = cv2.VideoCapture(abs_path)
                    if cap.isOpened():
                        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                        target = max(0, total // 3) if total > 3 else 0
                        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                        ok, frame = cap.read()
                        if not ok:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ok, frame = cap.read()
                        cap.release()
                        if ok and frame is not None:
                            h, w = frame.shape[:2]
                            if w > 960:
                                scale = 960.0 / w
                                frame = cv2.resize(frame, (960, int(h * scale)))
                            ok2, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                            if ok2:
                                return HttpResponse(buf.tobytes(), content_type='image/jpeg')
                except Exception:
                    pass

    return HttpResponse(status=204)

