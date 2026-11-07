import datetime
import logging
import uuid
from django.shortcuts import render, redirect, get_object_or_404, Http404
from django.contrib import messages
from django.utils import timezone
from django.conf import settings as dj_settings

from cameras.models import Camera
from realtime.models import LiveFeed
from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from detections.models import Detection
from django.http import JsonResponse
from django.db.models import Q
from accounts.models import User
from accounts.decorators import any_permission_required
from accounts.decorators import dig_or_it_required
from accounts.decorators import it_required
from accounts.decorators import role_required
from accounts.decorators import staff_required


def _camera_list_redirect(request):
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'it_support_portal'
    return redirect(f'{ns}:camera_list')


@role_required('DIG', 'IT', 'SSP', 'SUPV', 'AUDIT')
def camera_list(request):
    q = (request.GET.get('q') or '').strip()
    health = (request.GET.get('health') or '').strip()
    active = (request.GET.get('active') or '').strip()
    health = health if health in ('online', 'degraded', 'offline', 'unknown') else ''
    active = active if active in ('active', 'inactive') else ''

    base_qs = Camera.objects.all().order_by('-installed_date')
    camera_qs = base_qs
    if q:
        camera_qs = camera_qs.filter(Q(camera_id__icontains=q) | Q(location__icontains=q))
    if health:
        camera_qs = camera_qs.filter(health_status=health)
    if active:
        camera_qs = camera_qs.filter(is_active=(active == 'active'))

    cameras = list(camera_qs)


    if q or health or active:
        all_cameras = list(base_qs)
    else:
        all_cameras = cameras
    online_count = sum(1 for c in all_cameras if c.is_active and (c.health_status in ('online', 'unknown') or c.rtsp_url))
    offline_count = sum(1 for c in all_cameras if not c.is_active or c.health_status == 'offline')
    with_media = sum(1 for c in all_cameras if c.rtsp_url)
    is_it = request.user.role == 'IT'
    return render(request, 'dashboard/dig/camera_list.html', {
        'cameras': cameras,
        'can_manage': is_it,
        'online_count': online_count,
        'offline_count': offline_count,
        'with_video': with_media,
        'total_registry': len(all_cameras),
        'q': q,
        'health_filter': health,
        'active_filter': active,
    })


@it_required
def camera_add(request):
    if request.method == 'POST':
        source_type = request.POST.get('source_type', 'rtsp')
        video_file = request.FILES.get('video_file')

        new_camera_id = (request.POST.get('camera_id') or '').strip()
        new_location = (request.POST.get('location') or '').strip()
        if not new_camera_id:
            messages.error(request, "Camera ID is required.")
            return redirect('it_support_portal:camera_add')
        if not new_location:
            messages.error(request, "Location is required.")
            return redirect('it_support_portal:camera_add')
        if Camera.objects.filter(camera_id=new_camera_id).exists():
            messages.error(request, f"A camera with ID '{new_camera_id}' already exists.")
            return redirect('it_support_portal:camera_add')

        rtsp_url = None
        http_snapshot_url = None
        notes = request.POST.get('notes') or None

        if source_type == 'video' and video_file:
            from django.core.files.storage import default_storage
            safe_name = video_file.name.replace(' ', '_')
            rel_path = f'camera_videos/{safe_name}'
            saved = default_storage.save(rel_path, video_file)
            media_url = dj_settings.MEDIA_URL.rstrip('/') + '/' + saved
            rtsp_url = media_url
            http_snapshot_url = None
            notes = ((notes or '') + f' [Demo video: {safe_name}]').strip()
        else:
            rtsp_url = request.POST.get('rtsp_url') or None
            http_snapshot_url = request.POST.get('http_snapshot_url') or None

        try:
            threshold = float(request.POST.get('auto_confirm_threshold', 0.85))
            threshold = max(0.50, min(0.99, threshold))
        except (TypeError, ValueError):
            threshold = 0.85

        from django.db import transaction
        try:
            with transaction.atomic():
                try:
                    lat = float(request.POST.get('latitude')) if request.POST.get('latitude') not in (None, '') else None
                except (TypeError, ValueError):
                    lat = None
                try:
                    lng = float(request.POST.get('longitude')) if request.POST.get('longitude') not in (None, '') else None
                except (TypeError, ValueError):
                    lng = None
                camera = Camera.objects.create(
                    camera_id=new_camera_id,
                    location=new_location,
                    latitude=lat,
                    longitude=lng,
                    legal_direction=request.POST.get('legal_direction', 'N'),
                    violation_side=request.POST.get('violation_side', 'back'),
                    auto_confirm_threshold=threshold,
                    rtsp_url=rtsp_url,
                    http_snapshot_url=http_snapshot_url,
                    is_active=True,
                    is_streaming=True,
                    capture_interval=int(request.POST.get('capture_interval', 5)),
                    notes=notes,
                    health_status='online',
                )
                if source_type == 'video' and video_file:
                    camera.last_frame_at = timezone.now()
                    camera.last_health_check = timezone.now()
                    camera.save(update_fields=['last_frame_at', 'last_health_check'])
                    lf = LiveFeed.objects.create(
                        title=f"Camera {camera.camera_id} | {camera.location}",
                        video_file=video_file,
                        camera=camera,
                        location_label=camera.location,
                        uploaded_by=request.user,
                        is_active=True,
                    )
                    try:
                        if lf.video_file:
                            camera.rtsp_url = lf.video_file.url
                            camera.health_status = 'online'
                            camera.is_active = True
                            camera.is_streaming = True
                            camera.save(update_fields=['rtsp_url', 'health_status', 'is_active', 'is_streaming'])
                    except Exception:
                        pass
                    try:
                        from video_processor.models import VideoUpload
                        from cameras.video_processing import start_processing_async
                        upload = VideoUpload.objects.create(
                            camera=camera,
                            video_file=video_file,
                            original_filename=getattr(video_file, 'name', 'upload.mp4'),
                            uploaded_by=request.user,
                            camera_location=camera.location or '',
                        )
                        start_processing_async(upload.id)
                        msg_extra = " AI processing started on uploaded video."
                    except Exception as _vu_err:
                        import logging
                        logging.getLogger(__name__).warning("VideoUpload pipeline failed: %s", _vu_err)
                        msg_extra = ""
                if not camera.rtsp_url and not camera.http_snapshot_url:
                    camera.enrollment_token = uuid.uuid4()
                    camera.is_enrolled = False
                    camera.save()
                    AuditLog.write(request, 'camera.add', 'Camera', camera.id, camera_id=camera.camera_id,
                                   enrollment='pending')
                    msg = f"Camera {camera.camera_id} added. Enrollment token: {camera.enrollment_token}"
                else:
                    camera.is_enrolled = True
                    camera.save()
                    AuditLog.write(request, 'camera.add', 'Camera', camera.id, camera_id=camera.camera_id,
                                   rtsp=camera.rtsp_url or camera.http_snapshot_url)
                    msg = f"Camera {camera.camera_id} added. API key: {camera.api_key}" + (msg_extra if "msg_extra" in dir() else "")
        except Exception as e:
            messages.error(request, f"Failed to create camera: {e}")
            return redirect('it_support_portal:camera_add')
        messages.success(request, msg)
        return _camera_list_redirect(request)
    return render(request, 'dashboard/dig/camera_add.html', {})


@it_required
def camera_edit(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    if request.method == 'POST':
        before_rtsp = camera.rtsp_url
        camera.location = request.POST.get('location', camera.location)
        try:
            camera.latitude = float(request.POST.get('latitude')) if request.POST.get('latitude') not in (None, '') else None
        except (TypeError, ValueError):
            pass
        try:
            camera.longitude = float(request.POST.get('longitude')) if request.POST.get('longitude') not in (None, '') else None
        except (TypeError, ValueError):
            pass
        camera.legal_direction = request.POST.get('legal_direction', camera.legal_direction)
        camera.violation_side = request.POST.get('violation_side', camera.violation_side)
        try:
            threshold = float(request.POST.get('auto_confirm_threshold', camera.auto_confirm_threshold))
            camera.auto_confirm_threshold = max(0.50, min(0.99, threshold))
        except (TypeError, ValueError):
            pass
        camera.rtsp_url = request.POST.get('rtsp_url') or None
        camera.http_snapshot_url = request.POST.get('http_snapshot_url') or None
        camera.capture_interval = int(request.POST.get('capture_interval', 5) or 5)
        camera.is_streaming = request.POST.get('is_streaming') == 'on'
        camera.notes = request.POST.get('notes') or None
        video_file = request.FILES.get('video_file')
        if video_file:
            from django.core.files.storage import default_storage
            from realtime.models import LiveFeed
            rel_path = f"cameras/videos/{camera.camera_id}_{video_file.name.replace(' ', '_')}"
            saved = default_storage.save(rel_path, video_file)
            from django.conf import settings as dj_settings
            camera.rtsp_url = dj_settings.MEDIA_URL.rstrip('/') + '/' + saved
            camera.is_active = True
            camera.is_streaming = True
            camera.health_status = 'online'
            camera.last_frame_at = timezone.now()
            LiveFeed.objects.update_or_create(
                camera=camera,
                defaults={
                    'title': f"Camera {camera.camera_id} | {camera.location}",
                    'video_file': video_file,
                    'location_label': camera.location,
                    'uploaded_by': request.user,
                    'is_active': True,
                },
            )
            try:
                from video_processor.models import VideoUpload
                from cameras.video_processing import start_processing_async
                upload = VideoUpload.objects.create(
                    camera=camera,
                    video_file=video_file,
                    original_filename=getattr(video_file, 'name', 'upload.mp4'),
                    uploaded_by=request.user,
                    camera_location=camera.location or '',
                )
                start_processing_async(upload.id)
                messages.info(request, "AI processing started on the uploaded video - detections will appear in the review queue and on Live Tracking.")
            except Exception as _vu_err:
                logging.getLogger(__name__).warning("VideoUpload pipeline failed on camera_edit: %s", _vu_err)
        camera.save()
        AuditLog.write(request, 'camera.edit', 'Camera', camera.id, camera_id=camera.camera_id,
                       before_rtsp=before_rtsp, after_rtsp=camera.rtsp_url,
                       violation_side=camera.violation_side,
                       auto_confirm_threshold=camera.auto_confirm_threshold)
        messages.success(request, f"Camera {camera.camera_id} updated.")
        return _camera_list_redirect(request)
    return render(request, 'dashboard/dig/camera_edit.html', {'camera': camera})


@dig_or_it_required
def camera_toggle(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    camera.toggle()
    AuditLog.write(request, 'camera.toggle', 'Camera', camera.id, active=camera.is_active)
    messages.success(request, f"Camera {camera.camera_id} {'activated' if camera.is_active else 'deactivated'}.")
    return _camera_list_redirect(request)


@dig_or_it_required
def camera_set_online(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    camera.health_status = 'online'
    camera.last_frame_at = timezone.now()
    camera.last_health_check = timezone.now()
    camera.is_active = True
    camera.is_streaming = True
    camera.save()
    AuditLog.write(request, 'camera.set_online', 'Camera', camera.id, camera_id=camera.camera_id)
    messages.success(request, f"Camera {camera.camera_id} set to ONLINE / LIVE. Protected from auto-degradation for 24 hours.")
    return _camera_list_redirect(request)


def _camera_delete_impact(camera):
    from realtime.models import CameraAssignment
    return {
        'detections': camera.detections.count(),
        'assignments': CameraAssignment.objects.filter(camera=camera, is_active=True).count(),
        'challans': camera.challan_set.count() if hasattr(camera, 'challan_set') else 0,
    }


def _do_camera_delete(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    impact = _camera_delete_impact(camera)
    has_history = any(impact.values())
    if request.method == 'POST':
        force = request.POST.get('force') == 'on' or not has_history
        if has_history and not force:
            messages.error(
                request,
                f"Camera {camera.camera_id} has {impact['detections']} detection(s), "
                f"{impact['challans']} challan(s) and {impact['assignments']} active officer "
                f"assignment(s) linked to it. Deactivate it instead, or tick 'force delete' to "
                f"remove the camera record anyway (history is preserved but detached from it)."
            )
            return render(request, 'dashboard/dig/camera_confirm_delete.html',
                          {'camera': camera, 'impact': impact})
        AuditLog.write(request, 'camera.delete', 'Camera', camera.id,
                        camera_id=camera.camera_id, **impact)
        cid = camera.camera_id
        camera.delete()
        messages.success(request, f"Camera {cid} deleted.")
        return _camera_list_redirect(request)
    return render(request, 'dashboard/dig/camera_confirm_delete.html',
                  {'camera': camera, 'impact': impact})


@it_required
def camera_delete(request, camera_id):
    return _do_camera_delete(request, camera_id)


@it_required
def regenerate_enrollment_token(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    if request.method == 'POST':
        camera.enrollment_token = uuid.uuid4()
        camera.is_enrolled = False
        camera.save()
        AuditLog.write(request, 'camera.regenerate_token', 'Camera', camera.id, camera_id=camera.camera_id)
        messages.success(request, f"New enrollment token for {camera.camera_id}: {camera.enrollment_token}")
    return _camera_list_redirect(request)


@staff_required
def cameras_status(request):
    all_cameras = list(Camera.objects.all().order_by('-installed_date'))
    threshold = timezone.now() - datetime.timedelta(minutes=3)
    manual_online_threshold = timezone.now() - datetime.timedelta(hours=24)
    for c in all_cameras:
        is_demo = (c.rtsp_url and c.rtsp_url.startswith('file://'))
        if is_demo:
            if c.health_status != 'online' and c.is_active:
                c.health_status = 'online'
                c.save(update_fields=['health_status'])
            continue
        if not c.is_active:
            continue
        if c.last_health_check and c.last_health_check > manual_online_threshold and c.health_status == 'online':
            continue
        if not c.rtsp_url and not c.http_snapshot_url:
            continue
        if c.last_frame_at and c.last_frame_at > threshold:
            if c.health_status != 'online':
                c.health_status = 'online'
                c.save(update_fields=['health_status'])
        else:
            if c.last_frame_at and c.health_status == 'online':
                if not (c.last_health_check and c.last_health_check > manual_online_threshold):
                    c.health_status = 'degraded'
                    c.save(update_fields=['health_status'])


    online_count = sum(1 for c in all_cameras if c.health_status == 'online')
    offline_count = sum(1 for c in all_cameras if c.health_status == 'offline')
    degraded_count = sum(1 for c in all_cameras if c.health_status == 'degraded')
    unknown_count = max(0, len(all_cameras) - online_count - offline_count - degraded_count)

    q = (request.GET.get('q') or '').strip()
    cameras = all_cameras
    if q:
        needle = q.lower()
        cameras = [c for c in all_cameras
                   if needle in (c.camera_id or '').lower()
                   or needle in (c.location or '').lower()]

    return render(request, 'dashboard/dig/cameras_status.html', {
        'cameras': cameras,
        'now': timezone.now(),
        'q': q,
        'total_count': len(all_cameras),
        'online_count': online_count,
        'offline_count': offline_count,
        'degraded_count': degraded_count,
        'unknown_count': unknown_count,
    })


@it_required
def camera_assignments(request):
    from realtime.models import CameraAssignment
    officers = User.objects.filter(role=User.OFFICER, is_active=True)
    cameras = Camera.objects.filter(is_active=True)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign':
            camera_id = request.POST.get('camera_id')
            officer_id = request.POST.get('officer_id')
            notes = request.POST.get('notes', '').strip()
            try:
                camera = Camera.objects.get(pk=camera_id)
                officer = User.objects.get(pk=officer_id, role=User.OFFICER)
                existing = CameraAssignment.objects.filter(officer=officer, is_active=True).exclude(camera=camera)
                if existing.exists():
                    messages.error(
                        request,
                        f"{officer.display_name} already has a camera assigned. "
                        "Unassign it first (limit: 1 camera per officer)."
                    )
                    return redirect(request.resolver_match.namespace + ':camera_assignments'
                                    if getattr(request, 'resolver_match', None) else 'dig:camera_assignments')
                assignment, created = CameraAssignment.objects.get_or_create(
                    camera=camera, officer=officer,
                    defaults={
                        'assigned_by': request.user,
                        'is_active': True,
                        'notes': notes or None,
                    }
                )
                if not created:
                    assignment.is_active = True
                    assignment.notes = notes or assignment.notes
                    assignment.save()
                AuditLog.write(request, 'camera.assign', 'CameraAssignment', assignment.id,
                               camera=camera.camera_id, officer=officer.display_name)
                messages.success(request, f"Camera {camera.camera_id} assigned to {officer.display_name}.")
            except (Camera.DoesNotExist, User.DoesNotExist) as e:
                messages.error(request, f"Assignment failed: {e}")
            ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'dig'
            return redirect(f'{ns}:camera_assignments')

        elif action == 'unassign':
            assignment_id = request.POST.get('assignment_id')
            try:
                assignment = CameraAssignment.objects.get(pk=assignment_id)
                assignment.is_active = False
                assignment.save()
                AuditLog.write(request, 'camera.unassign', 'CameraAssignment', assignment.id,
                               camera=assignment.camera.camera_id, officer=assignment.officer.display_name)
                messages.success(request, f"Camera {assignment.camera.camera_id} unassigned from {assignment.officer.display_name}.")
            except CameraAssignment.DoesNotExist:
                messages.error(request, "Assignment not found.")
            return redirect('dig:camera_assignments')

        elif action == 'release':
            assignment_id = request.POST.get('assignment_id')
            try:
                assignment = CameraAssignment.objects.get(pk=assignment_id, is_active=True)
                assignment.is_active = False
                assignment.save()
                AuditLog.write(request, 'camera.release', 'CameraAssignment', assignment.id,
                               camera=assignment.camera.camera_id, officer=assignment.officer.display_name)
                messages.success(request, f"Camera {assignment.camera.camera_id} released from {assignment.officer.display_name}.")
            except CameraAssignment.DoesNotExist:
                messages.error(request, "Active assignment not found.")
            ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'dig'
            return redirect(f'{ns}:camera_assignments')

    assignments = CameraAssignment.objects.filter(is_active=True).select_related('camera', 'officer', 'assigned_by')
    return render(request, 'dashboard/dig/camera_assignments.html', {
        'officers': officers, 'cameras': cameras, 'assignments': assignments,
    })


@it_required
def camera_test(request, camera_id):
    import time
    import base64

    cam = get_object_or_404(Camera, pk=camera_id)
    url = (cam.http_snapshot_url or cam.rtsp_url or '').strip()
    if not url:
        return JsonResponse({'ok': False, 'error': 'No stream URL configured for this camera. Edit the camera and set an RTSP or HTTP snapshot URL (or upload a video).'})

    started = time.time()

    def _with_snapshot(payload, frame):
        try:
            import cv2
            h, w = frame.shape[:2]
            small = cv2.resize(frame, (320, max(1, int(320 * h / max(1, w)))))
            ok_enc, buf = cv2.imencode('.jpg', small)
            if ok_enc:
                payload['snapshot'] = 'data:image/jpeg;base64,' + base64.b64encode(buf).decode()
        except Exception:
            pass
        return payload

    if url.lower().startswith('http'):
        try:
            import requests as _rq
            resp = _rq.get(url, timeout=8)
            latency = int((time.time() - started) * 1000)
            if resp.status_code != 200:
                return JsonResponse({'ok': False, 'kind': 'http', 'latency_ms': latency,
                                     'error': f'HTTP {resp.status_code} from stream URL.'})
            try:
                import cv2
                import numpy as np
                arr = np.frombuffer(resp.content, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            except Exception:
                frame = None
            if frame is None:
                return JsonResponse({'ok': False, 'kind': 'http', 'latency_ms': latency,
                                     'error': 'Endpoint reachable but the response is not a decodable image. Use a snapshot JPEG URL.'})
            return JsonResponse(_with_snapshot({
                'ok': True, 'kind': 'http', 'latency_ms': latency,
                'message': f'Snapshot OK - {frame.shape[1]}x{frame.shape[0]}',
            }, frame))
        except Exception as e:
            return JsonResponse({'ok': False, 'kind': 'http', 'error': f'Request failed: {e}'})

    try:
        import cv2
        import os as _os
        _os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        opened = cap.isOpened()
        frame = None
        if opened:
            ok_f, frame = cap.read()
            if not ok_f:
                frame = None
        cap.release()
        latency = int((time.time() - started) * 1000)
        if frame is not None:
            return JsonResponse(_with_snapshot({
                'ok': True, 'kind': 'rtsp', 'latency_ms': latency,
                'message': f'RTSP stream OK - {frame.shape[1]}x{frame.shape[0]}',
            }, frame))
        return JsonResponse({
            'ok': False, 'kind': 'rtsp', 'latency_ms': latency,
            'error': 'Could not open RTSP stream. Check the URL, credentials and network reachability.',
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'kind': 'rtsp', 'error': f'RTSP test failed: {e}'})


@staff_required
def camera_health(request):
    q = (request.GET.get('q') or '').strip()
    base = Camera.objects.all().order_by('-installed_date')
    total = base.count()
    online = base.filter(health_status='online').count()
    offline = base.filter(health_status='offline').count()
    unknown = base.filter(health_status='unknown').count()
    degraded = base.filter(health_status='degraded').count()

    cameras = base
    if q:
        cameras = base.filter(Q(camera_id__icontains=q) | Q(location__icontains=q))

    return render(request, 'dashboard/dig/camera_health.html', {
        'cameras': list(cameras), 'total': total, 'online': online,
        'offline': offline, 'unknown': unknown, 'degraded': degraded,
        'q': q,
    })


@any_permission_required('camera_feed', 'view_cameras')
def camera_stream_url(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    if request.user.role == 'OFFICER':
        from realtime.models import CameraAssignment
        if not CameraAssignment.objects.filter(camera=camera, officer=request.user, is_active=True).exists():
            raise Http404

    if camera.http_snapshot_url:
        return JsonResponse({'stream_url': camera.http_snapshot_url, 'type': 'http_snapshot'})

    if camera.rtsp_url:
        return JsonResponse({'stream_url': camera.rtsp_url, 'type': 'rtsp'})

    latest = Detection.objects.filter(camera=camera).order_by('-created_at').first()
    if latest and latest.raw_image:
        return JsonResponse({'stream_url': latest.raw_image.url, 'type': 'detection_snapshot'})

    return JsonResponse({'stream_url': None, 'type': 'none'}, status=404)

