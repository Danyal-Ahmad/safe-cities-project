import os
import io
import logging
from uuid import UUID
from PIL import Image
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile
from django.utils import timezone

from wrongway_system.security.rate_limit import is_rate_limited, rate_limit_response

from .models import Camera
from detections.models import Detection
from detections.ai import run_pipeline

logger = logging.getLogger('wrongway.ingest')


# ---------------------------------------------------------------------------
# Per-endpoint API rate limits (per IP, sliding window).
# These are view-level limits - the global RateLimitMiddleware never covers
# /api/ paths, so the layers never double-limit. The limits are checked
# BEFORE authentication so flooding does not cost a DB lookup, and they are
# plain in-view checks (no decorator wrapping) so @csrf_exempt on the Bearer
# endpoints is untouched.
# ---------------------------------------------------------------------------
ENROLL_LIMIT = (5, 3600)      # 5 per hour per IP - enrollment tokens are rare
INGEST_LIMIT = (300, 60)      # 300 per minute per IP - a camera pushes every few
                               # seconds; must NOT break normal operation
HEARTBEAT_LIMIT = (120, 60)   # 120 per minute per IP


def _authenticate_camera(request):
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth.startswith('Bearer '):
        return None
    try:
        api_key = UUID(auth[7:].strip())
    except ValueError:
        return None
    try:
        return Camera.objects.get(api_key=api_key, is_active=True)
    except Camera.DoesNotExist:
        return None


@csrf_exempt
@require_POST
def enroll_camera(request):
    if is_rate_limited(request, 'api_enroll', limit=ENROLL_LIMIT[0], window=ENROLL_LIMIT[1]):
        return rate_limit_response(request)
    token = (request.POST.get('enrollment_token') or '').strip()
    if not token:
        return HttpResponseBadRequest("enrollment_token is required.")
    try:
        token_uuid = UUID(token)
    except ValueError:
        return HttpResponseBadRequest("Invalid enrollment_token format.")
    try:
        camera = Camera.objects.get(enrollment_token=token_uuid, is_enrolled=False)
    except Camera.DoesNotExist:
        return HttpResponseForbidden("Invalid or already-used enrollment token.")
    camera.is_enrolled = True
    camera.enrollment_token = None
    rtsp_url = (request.POST.get('rtsp_url') or '').strip()
    http_snapshot_url = (request.POST.get('http_snapshot_url') or '').strip()
    if rtsp_url:
        camera.rtsp_url = rtsp_url
    if http_snapshot_url:
        camera.http_snapshot_url = http_snapshot_url
    update_fields = ['is_enrolled', 'enrollment_token']
    if rtsp_url:
        update_fields.append('rtsp_url')
    if http_snapshot_url:
        update_fields.append('http_snapshot_url')
    camera.save(update_fields=update_fields)
    logger.info("Camera %s enrolled successfully (rtsp=%s, http=%s)",
                camera.camera_id, bool(rtsp_url), bool(http_snapshot_url))
    return JsonResponse({
        'camera_id': camera.camera_id,
        'api_key': str(camera.api_key),
        'message': 'Enrollment successful. Use this api_key as Bearer token for /api/v1/ingest/ and /api/v1/heartbeat/.',
    })


@csrf_exempt
@require_POST
def ingest(request):
    if is_rate_limited(request, 'api_ingest', limit=INGEST_LIMIT[0], window=INGEST_LIMIT[1]):
        return rate_limit_response(request)
    camera = _authenticate_camera(request)
    if not camera:
        return HttpResponseForbidden("Invalid or inactive camera API key.")
    image_file = request.FILES.get('image')
    if not image_file:
        return HttpResponseBadRequest("Image file is required.")
    if image_file.size > 10 * 1024 * 1024:
        return HttpResponseBadRequest("Image exceeds 10 MB limit.")
    if image_file.content_type and not image_file.content_type.startswith('image/'):
        return HttpResponseBadRequest("Only image MIME types are accepted.")
    try:
        img = Image.open(image_file).convert('RGB')
    except Exception as e:
        logger.warning("Invalid image from camera %s: %s", camera.camera_id, e)
        return HttpResponseBadRequest(f"Invalid image: {e}")

    raw_image_io = io.BytesIO()
    img.save(raw_image_io, format='JPEG', quality=85)
    raw_image_io.seek(0)

    import tempfile
    result = {}
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        img.save(tmp, format='JPEG', quality=85)
        tmp_path = tmp.name
    try:
        try:
            result = run_pipeline(tmp_path, camera)
        except Exception as ai_err:
            logger.warning("AI pipeline failed for camera %s: %s", camera.camera_id, ai_err)
            result = {'plate_text': None, 'province': None, 'series': None,
                      'registration_year': None, 'side': None, 'confidence': None,
                      'detected_violation': None, 'raw_ai_response': {'error': str(ai_err)}}
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass

    detection = Detection(
        camera=camera,
        ai_plate_text=result.get('plate_text'),
        ai_province=result.get('province'),
        ai_series=result.get('series'),
        ai_registration_year=result.get('registration_year'),
        ai_side_classification=result.get('side'),
        ai_confidence=result.get('confidence'),
        ai_detected_violation=result.get('detected_violation'),
        ai_workflow_version="onnx-plate+onnx-side",
        ai_raw_response=result.get('raw_ai_response', {}),
        status=Detection.PENDING,
    )
    detection.raw_image.save(f"{camera.camera_id}_{timezone.now():%Y%m%d_%H%M%S}.jpg",
                              ContentFile(raw_image_io.getvalue()), save=False)
    if result.get('plate_crop_path') and os.path.exists(result['plate_crop_path']):
        with open(result['plate_crop_path'], 'rb') as f:
            crop_io = io.BytesIO(f.read()); crop_io.seek(0)
            detection.plate_crop_image.save(f"crop_{camera.camera_id}.jpg",
                                            ContentFile(crop_io.getvalue()), save=False)
        try: os.unlink(result['plate_crop_path'])
        except Exception: pass
    detection.save()

    challan = None
    action = 'queued_review'
    try:
        from detections.finalize import finalize_detection_from_ai
        detection, challan, action = finalize_detection_from_ai(detection, result, camera=camera)
    except Exception as fin_err:
        logger.warning("finalize_detection_from_ai failed: %s", fin_err)

    camera.mark_online()

    logger.info("Detection %d from camera %s (side=%s, violation=%s, action=%s)",
                detection.id, camera.camera_id, detection.ai_side_classification,
                detection.ai_detected_violation, action)
    return JsonResponse({
        'detection_id': detection.id,
        'plate_detected': bool(detection.plate_crop_image),
        'side': detection.ai_side_classification,
        'confidence': detection.ai_confidence,
        'detected_violation': detection.ai_detected_violation,
        'status': detection.status,
        'action': action,
        'challan_ticket': getattr(challan, 'ticket_no', None),
    }, status=201)


@csrf_exempt
@require_POST
def heartbeat(request):
    if is_rate_limited(request, 'api_heartbeat', limit=HEARTBEAT_LIMIT[0], window=HEARTBEAT_LIMIT[1]):
        return rate_limit_response(request)
    camera = _authenticate_camera(request)
    if not camera:
        return HttpResponseForbidden("Invalid or inactive camera API key.")
    camera.mark_online()
    return JsonResponse({'status': 'ok', 'camera_id': camera.camera_id,
                         'timestamp': timezone.now().isoformat()})

