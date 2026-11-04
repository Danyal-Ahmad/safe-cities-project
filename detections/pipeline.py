"""Safe City core enforcement pipeline.

Flow (fully automated, no manual/officer annotation anywhere):

    DETECTION  ->  FRAME TRACKING  ->  EVIDENCE (5 hard security checks)  ->  CHALLAN

Every challan is issued exclusively through this pipeline. A challan can only
be generated when all five evidence security checks pass. Any failure blocks
issuance: hard failures are rejected outright, ambiguous cases are parked in
the review queue for DIG oversight.
"""
from __future__ import annotations

import datetime
import hashlib
import logging
import re

from django.db import transaction
from django.utils import timezone

from detections.models import Detection

logger = logging.getLogger('wrongway.pipeline')

PLATE_PATTERN = re.compile(r'^[A-Z]{2,3}-\d{1,4}$')
TRACK_WINDOW_SECONDS = 45
EVIDENCE_FRAMES_REQUIRED = 3
TRACK_MIN_FRAMES = 3
TRACK_MIN_CONSISTENCY = 0.80
SINGLE_FRAME_HIGH_CONF = 0.90
OCR_MIN_CONFIDENCE = 0.60
PLATE_CROP_MIN_HEIGHT = 18


def _normalize_plate(raw: str | None) -> str:
    if not raw:
        return ''
    return re.sub(r'[^A-Z0-9-]', '', str(raw).upper())


def opposite_direction(direction: str | None) -> str | None:
    if not direction:
        return None
    opposites = {
        'north': 'south', 'south': 'north',
        'east': 'west', 'west': 'east',
        'inbound': 'outbound', 'outbound': 'inbound',
        'forward': 'reverse', 'reverse': 'forward',
    }
    return opposites.get(direction.lower(), direction)


def _auto_confirm_threshold(camera) -> float:
    thr = 0.70
    if camera is not None:
        try:
            thr = float(getattr(camera, 'auto_confirm_threshold', None) or thr)
        except (TypeError, ValueError):
            pass
    try:
        from admin.dig_portal.models import SystemSettings
        sys_thr = float(SystemSettings.get().ai_confidence_threshold or thr)
        thr = max(thr, min(sys_thr, 0.95))
    except Exception:
        pass
    return max(0.55, min(0.95, thr))


def _doubt_floor(auto_thr: float) -> float:
    return max(0.35, auto_thr - 0.25)



def frame_tracking(detection, camera) -> dict:
    """Build the cross-frame vehicle track for a detection.

    Strict evidence policy: a challan-grade track requires the same plate
    confirmed across at least EVIDENCE_FRAMES_REQUIRED frames (3-frame
    evidence, checked one-by-one). Single-frame observations are never
    corroborated, regardless of confidence — they park for DIG review.
    """
    plate = _normalize_plate(detection.ai_plate_text)
    raw = detection.ai_raw_response or {}
    side_conf = float(raw.get('side_confidence') or 0.0)
    plate_conf = float(raw.get('plate_confidence') or detection.ai_confidence or 0.0)

    track = {
        'track_id': None,
        'frames': 0,
        'consistency': 0.0,
        'matched_plate': plate,
        'window_seconds': TRACK_WINDOW_SECONDS,
        'mode': 'none',
    }
    if not plate or camera is None:
        return track

    window_start = detection.created_at or timezone.now()
    window_start = window_start - datetime.timedelta(seconds=TRACK_WINDOW_SECONDS)

    prior = (
        Detection.objects.filter(
            camera=camera,
            created_at__gte=window_start,
            created_at__lte=detection.created_at or timezone.now(),
        ).exclude(pk=detection.pk)
        .order_by('created_at')
    )
    matched = []
    for d in prior:
        if _normalize_plate(d.ai_plate_text) == plate and plate:
            matched.append(d)

    frame_evidence = raw.get('frame_evidence') or []
    burst_frames = len(frame_evidence)

    total_frames = len(matched) + 1 + max(0, burst_frames - 1 if burst_frames else 0)

    if total_frames >= TRACK_MIN_FRAMES:
        agree = 0
        total = 0
        for m in matched:
            total += 2
            agree += 1 if _normalize_plate(m.ai_plate_text) == plate else 0
            agree += 1 if (m.ai_side_classification == detection.ai_side_classification) else 0
        for rec in frame_evidence:
            total += 2
            agree += 1 if _normalize_plate(rec.get('plate')) == plate else 0
            agree += 1 if rec.get('plate_complete') else 0
        consistency = (agree / total) if total else 1.0
        track.update({
            'track_id': f"TRK-{camera.pk}-{plate[:3]}-{(detection.pk or 0):04d}",
            'frames': total_frames,
            'consistency': round(consistency, 3),
            'mode': 'corroborated_track',
        })
    elif plate_conf >= SINGLE_FRAME_HIGH_CONF:
        track.update({
            'track_id': f"TRK-{camera.pk}-{plate[:3]}-{(detection.pk or 0):04d}",
            'frames': max(1, total_frames),
            'consistency': round(side_conf, 3),
            'mode': 'single_frame_high_confidence',
        })
    else:
        track.update({
            'frames': max(1, total_frames),
            'consistency': round(side_conf, 3),
            'mode': 'unconfirmed',
        })
    return track



def _check_plate_readability(detection, raw) -> dict:
    """Check 1 — Pakistan plate format + HD OCR quality (per-frame, 1-by-1)."""
    plate = (detection.ai_plate_text or '').strip().upper()
    ocr_conf = float(raw.get('ocr_confidence') or 0.0)
    norm = _normalize_plate(plate)
    ok_format = bool(PLATE_PATTERN.match(norm)) if norm else False
    known_series = bool(raw.get('known_pk_series'))
    passed = ok_format and ocr_conf >= OCR_MIN_CONFIDENCE and bool(plate)
    detail = (
        f"plate={plate or '—'} pk_format={'ok' if ok_format else 'invalid'} "
        f"known_series={'yes' if known_series else 'no'} "
        f"ocr_conf={ocr_conf:.2f} (min {OCR_MIN_CONFIDENCE:.2f})"
    )
    return {'check': 'plate_readability', 'passed': bool(passed), 'detail': detail}


def _check_frame_consistency(detection, track) -> dict:
    """Check 2 — strict 3-frame evidence: same full plate verified across at
    least EVIDENCE_FRAMES_REQUIRED frames, each checked one-by-one."""
    mode = track.get('mode')
    frames = int(track.get('frames') or 0)
    consistency = float(track.get('consistency') or 0.0)
    raw = detection.ai_raw_response or {}
    frame_evidence = raw.get('frame_evidence') or []
    per_frame_ok = all(
        _normalize_plate(rec.get('plate')) == _normalize_plate(detection.ai_plate_text)
        and rec.get('plate_complete')
        for rec in frame_evidence
    ) if frame_evidence else False
    if mode == 'corroborated_track':
        passed = (
            frames >= EVIDENCE_FRAMES_REQUIRED
            and consistency >= TRACK_MIN_CONSISTENCY
            and (not frame_evidence or per_frame_ok)
        )
    else:
        passed = False
    detail = (
        f"mode={mode} frames={frames}/{EVIDENCE_FRAMES_REQUIRED} required "
        f"burst_frames={len(frame_evidence)} per_frame_1by1={'ok' if per_frame_ok or not frame_evidence else 'mismatch'} "
        f"consistency={consistency:.2f} (min {TRACK_MIN_CONSISTENCY:.2f})"
    )
    return {'check': 'frame_consistency', 'passed': bool(passed), 'detail': detail}


def _check_violation_logic(detection, camera, raw) -> dict:
    """Check 3 — violation logic + strict car-only gate (model is car-trained)."""
    side = detection.ai_side_classification
    side_conf = float(raw.get('side_confidence') or 0.0)
    violation_side = (getattr(camera, 'violation_side', None) or 'back') if camera else 'back'
    legal = (getattr(camera, 'legal_direction', None) or '').lower() if camera else ''
    moving = opposite_direction(legal) if legal else None
    violation_flag = bool(detection.ai_detected_violation)
    vehicle_class = raw.get('vehicle_class') or 'car'
    car_ok = vehicle_class == 'car'
    passed = violation_flag and side == violation_side and side_conf >= 0.60 and car_ok
    detail = (
        f"violation={violation_flag} side={side or '—'}/{side_conf:.2f} "
        f"required_side={violation_side} legal_dir={legal or '—'} moving_dir={moving or '—'} "
        f"vehicle_class={vehicle_class} car_gate={'passed' if car_ok else 'REJECTED (car-only model)'}"
    )
    return {'check': 'violation_logic', 'passed': bool(passed), 'detail': detail}


def _check_image_evidence(detection) -> dict:
    """Check 4 — full-plate image evidence: raw frame + complete plate crop
    (no half / edge-clipped plates) at usable resolution."""
    has_raw = bool(detection.raw_image and hasattr(detection.raw_image, 'name'))
    crop = detection.effective_plate_image
    has_crop = bool(crop and hasattr(crop, 'name'))
    crop_ok_size = False
    if has_crop:
        try:
            with crop.open('rb') as fh:
                from PIL import Image
                with Image.open(fh) as im:
                    crop_ok_size = im.height >= PLATE_CROP_MIN_HEIGHT
        except Exception:
            crop_ok_size = False
    raw = detection.ai_raw_response or {}
    plate_complete = bool(raw.get('plate_complete', True))
    passed = has_raw and has_crop and crop_ok_size and plate_complete
    detail = (
        f"raw_image={has_raw} plate_crop={has_crop} "
        f"crop_height_ok={crop_ok_size} (min {PLATE_CROP_MIN_HEIGHT}px) "
        f"plate_complete={plate_complete} (no half/cut plates)"
    )
    return {'check': 'image_evidence', 'passed': bool(passed), 'detail': detail}


def _check_chain_integrity(detection, checks, camera) -> dict:
    plate = _normalize_plate(detection.ai_plate_text)
    digest = build_evidence_hash(detection, checks, camera)
    duplicate = False
    if plate:
        from challans.models import Challan
        window = timezone.now() - datetime.timedelta(hours=24)
        recent = (
            Challan.objects
            .filter(detection__camera=camera, created_at__gte=window)
            .exclude(detection=detection)
            .values_list('plate_number', flat=True)
        )
        duplicate = any(
            _normalize_plate(p) == plate for p in recent if p
        )
    passed = bool(digest) and not duplicate
    detail = (
        f"chain_hash={digest[:16] if digest else '—'}… "
        f"duplicate_24h={'yes' if duplicate else 'no'}"
    )
    return {'check': 'chain_integrity', 'passed': bool(passed), 'detail': detail}


def build_evidence_hash(detection, checks, camera) -> str:
    """SHA-256 over the full evidence chain: camera, plate, timestamps, both
    evidence images and the first four check results. Tampering with any part
    of the chain invalidates the digest stored on the detection record.
    """
    try:
        def _img_digest(field):
            if not field or not hasattr(field, 'name'):
                return 'none'
            try:
                with field.open('rb') as fh:
                    return hashlib.sha256(fh.read()).hexdigest()
            except Exception:
                return 'unreadable'

        payload = {
            'camera': camera.pk if camera else None,
            'camera_id': getattr(camera, 'camera_id', None) if camera else None,
            'detection': detection.pk,
            'plate': _normalize_plate(detection.ai_plate_text),
            'created_at': (detection.created_at or timezone.now()).isoformat(),
            'raw_image_sha256': _img_digest(detection.raw_image),
            'plate_crop_sha256': _img_digest(detection.effective_plate_image),
            'checks': [{'check': c['check'], 'passed': c['passed']} for c in checks],
        }
        blob = repr(sorted(payload.items())).encode('utf-8')
        return hashlib.sha256(blob).hexdigest()
    except Exception as e:
        logger.warning('evidence hash failed: %s', e)
        return ''


def build_evidence(detection, track, camera) -> tuple[list, str]:
    raw = detection.ai_raw_response or {}
    checks = [
        _check_plate_readability(detection, raw),
        _check_frame_consistency(detection, track),
        _check_violation_logic(detection, camera, raw),
        _check_image_evidence(detection),
    ]
    chain = _check_chain_integrity(detection, checks, camera)
    checks.append(chain)
    evidence_hash = build_evidence_hash(detection, checks, camera)
    return checks, evidence_hash



def issue_challan(detection, camera, user=None):
    from challans.models import Challan
    from admin.dig_portal.models import SystemSettings

    existing = Challan.objects.filter(detection=detection).first()
    if existing:
        return existing

    sys_settings = SystemSettings.get()
    plate = detection.ai_plate_text or 'UNKNOWN'
    ticket_no = Challan.objects.generate_ticket_no(plate[:3].upper())
    violation_type = Challan.WRONG_WAY

    owner_data = {}
    try:
        from admin.officer_portal.views import lookup_owner_by_plate
        if plate and plate != 'UNKNOWN':
            owner_data = lookup_owner_by_plate(plate) or {}
    except Exception:
        owner_data = {}

    legal = (getattr(camera, 'legal_direction', None) or '') if camera else ''
    with transaction.atomic():
        challan = Challan.objects.create(
            detection=detection,
            ticket_no=ticket_no,
            plate_number=plate,
            province=detection.ai_province,
            owner_name=owner_data.get('owner_name'),
            cnic=owner_data.get('cnic'),
            address=owner_data.get('address'),
            phone=owner_data.get('phone'),
            vehicle_type=owner_data.get('vehicle_type') or 'car',
            make_year=owner_data.get('make_year'),
            color=owner_data.get('color'),
            chassis_no=owner_data.get('chassis_no'),
            violation_type=violation_type,
            fine_amount=sys_settings.get_fine(violation_type),
            location=camera.location if camera else 'AI Detection',
            camera=camera,
            ai_confidence=detection.ai_confidence,
            moving_direction=opposite_direction(legal) if legal else None,
            legal_direction=legal or None,
            issue_date=datetime.date.today(),
            due_date=datetime.date.today() + datetime.timedelta(days=sys_settings.due_date_days),
            payment_status=Challan.UNPAID,
            created_by=user,
        )

    try:
        from challans.pdf_service import save_challan_pdf
        save_challan_pdf(challan)
    except Exception as e:
        logger.warning('challan PDF deferred: %s', e)
    try:
        from challans.email_service import send_challan_notification
        send_challan_notification(challan)
    except Exception as e:
        logger.warning('challan email skipped: %s', e)

    try:
        from admin.dig_portal.models import AuditLog
        AuditLog.write(
            None, 'pipeline.challan_issued', 'Detection', detection.id,
            plate=plate, challan=ticket_no, confidence=detection.ai_confidence,
            evidence_hash=detection.evidence_hash,
        )
    except Exception:
        pass
    return challan



def process_detection(detection, result: dict, camera=None, system_user=None):
    """Run the full enforcement pipeline for one detection record.

    Strict policy (5 hard security checks):
      1. plate_readability   — Pakistan plate format + HD OCR confidence
      2. frame_consistency   — 3-frame evidence verified one-by-one (90fps burst)
      3. violation_logic     — wrong-way logic + strict car-only gate
      4. image_evidence      — full (non-clipped) plate crop at usable size
      5. chain_integrity     — SHA-256 tamper-evident chain, no duplicates

    Returns (detection, challan_or_None, action) where action is one of:
      'challan_issued'   — all five evidence checks passed, challan created
      'queued_review'    — evidence incomplete; parked for DIG oversight
      'ignored'          — hard failure; rejected
    """
    raw = result.get('raw_ai_response') or detection.ai_raw_response or {}
    conf = float(result.get('confidence') or detection.ai_confidence or 0.0)
    has_plate_box = bool(
        result.get('plate_crop_path')
        or raw.get('plate_detections')
        or detection.plate_crop_image
    )
    is_violation = bool(result.get('detected_violation') or detection.ai_detected_violation)

    auto_thr = _auto_confirm_threshold(camera or detection.camera)
    floor = _doubt_floor(auto_thr)

    detection.ai_confidence = conf
    detection.ai_detected_violation = is_violation
    if result.get('side'):
        detection.ai_side_classification = result.get('side')
    if raw:
        detection.ai_raw_response = raw

    if not has_plate_box or (not is_violation and conf < floor):
        detection.status = Detection.REJECTED
        detection.reviewed_at = timezone.now()
        detection.review_notes = (
            f"Auto-ignored: no usable plate evidence (conf={conf:.2f}, floor={floor:.2f})."
        )
        detection.evidence_checks = []
        detection.evidence_hash = None
        detection.save()
        logger.info('Detection %s IGNORED conf=%.2f', detection.id, conf)
        return detection, None, 'ignored'

    raw_vehicle_class = (raw.get('vehicle_class') or 'car')
    if raw_vehicle_class != 'car':
        detection.status = Detection.REJECTED
        detection.reviewed_at = timezone.now()
        detection.review_notes = (
            f"Auto-ignored: vehicle class '{raw_vehicle_class}' — the detection model is "
            f"trained on cars only, non-car vehicles are strictly out of scope."
        )
        detection.evidence_checks = []
        detection.evidence_hash = None
        detection.save()
        logger.info('Detection %s IGNORED non-car vehicle class=%s', detection.id, raw_vehicle_class)
        return detection, None, 'ignored'

    track = frame_tracking(detection, camera or detection.camera)
    detection.track_id = track.get('track_id')
    detection.track_frames = track.get('frames') or 0
    detection.track_consistency = track.get('consistency') or 0.0

    checks, evidence_hash = build_evidence(detection, track, camera or detection.camera)
    detection.evidence_checks = checks
    detection.evidence_hash = evidence_hash

    passed_count = sum(1 for c in checks if c.get('passed'))
    all_passed = passed_count == len(checks) and len(checks) == 5

    if all_passed and is_violation:
        detection.status = Detection.CONFIRMED
        detection.reviewed_at = timezone.now()
        detection.review_notes = (
            f"Evidence verified — {passed_count}/5 security checks passed "
            f"(track={track.get('mode')}, frames={track.get('frames')}/{EVIDENCE_FRAMES_REQUIRED}, "
            f"consistency={track.get('consistency'):.2f}). "
            f"Chain {evidence_hash[:16]}…"
        )
        detection.save()
        challan = issue_challan(detection, camera or detection.camera, user=system_user)
        logger.info(
            'Detection %s CHALLAN ISSUED %s — 5/5 checks, track=%s frames=%s',
            detection.id, getattr(challan, 'ticket_no', None), track.get('mode'), track.get('frames'),
        )
        return detection, challan, 'challan_issued'

    detection.status = Detection.PENDING
    detection.review_notes = (
        f"Evidence incomplete — {passed_count}/5 checks passed. "
        f"Failed: {', '.join(c['check'] for c in checks if not c.get('passed')) or '—'}. "
        f"Track={track.get('mode')} frames={track.get('frames')}/{EVIDENCE_FRAMES_REQUIRED} required "
        f"consistency={track.get('consistency'):.2f}. Parked for DIG review."
    )
    detection.save()
    logger.info(
        'Detection %s QUEUED — %d/5 checks (track=%s frames=%s)',
        detection.id, passed_count, track.get('mode'), track.get('frames'),
    )
    return detection, None, 'queued_review'


def finalize_detection_from_ai(detection, result: dict, camera=None, system_user=None):
    """Backwards-compatible entry point used by the camera worker and the
    video upload processor. Delegates to process_detection.
    """
    return process_detection(detection, result, camera=camera, system_user=system_user)
