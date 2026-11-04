
from __future__ import annotations

import datetime
import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('wrongway.ai')


def _opposite_direction(direction: str | None) -> str | None:
    """Return the cardinal direction opposite to *direction* (for wrong-way logic).

    H2 FIX: A wrong-way vehicle is moving AGAINST the legal direction, so its
    ``moving_direction`` is the opposite of ``cam.legal_direction``.
    """
    if not direction:
        return None
    _opposites = {
        'north': 'south', 'south': 'north',
        'east':  'west',  'west':  'east',
        'inbound': 'outbound', 'outbound': 'inbound',
        'forward': 'reverse',  'reverse': 'forward',
    }
    return _opposites.get(direction.lower(), direction)


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


def finalize_detection_from_ai(detection, result: dict, camera=None, system_user=None):
    from detections.models import Detection

    conf = float(result.get('confidence') or detection.ai_confidence or 0.0)
    is_violation = bool(result.get('detected_violation') or detection.ai_detected_violation)
    has_plate_box = bool(
        result.get('plate_crop_path')
        or (result.get('raw_ai_response') or {}).get('plate_detections')
        or detection.plate_crop_image
    )
    side_conf = float((result.get('raw_ai_response') or {}).get('side_confidence') or 0.0)

    auto_thr = _auto_confirm_threshold(camera or detection.camera)
    floor = _doubt_floor(auto_thr)

    combined = conf
    if side_conf > 0:
        combined = 0.65 * conf + 0.35 * side_conf

    detection.ai_confidence = conf
    detection.ai_detected_violation = is_violation
    if result.get('side'):
        detection.ai_side_classification = result.get('side')
    if result.get('raw_ai_response'):
        detection.ai_raw_response = result.get('raw_ai_response')

    if is_violation and combined >= auto_thr and has_plate_box:
        detection.status = Detection.CONFIRMED
        detection.reviewed_at = timezone.now()
        detection.review_notes = (
            f"Auto-confirmed by AI (combined={combined:.2f} ≥ threshold={auto_thr:.2f}). "
            "No officer annotation required."
        )
        detection.save()
        challan = _issue_auto_challan(detection, system_user)
        logger.info(
            "Detection %s AUTO-CONFIRMED conf=%.2f combined=%.2f thr=%.2f challan=%s",
            detection.id, conf, combined, auto_thr, getattr(challan, 'ticket_no', None),
        )
        return detection, challan, 'auto_confirmed'

    if has_plate_box and combined >= floor:
        detection.status = Detection.PENDING
        detection.review_notes = (
            f"Queued for officer review (combined={combined:.2f}, auto_thr={auto_thr:.2f}, "
            f"violation={is_violation})."
        )
        detection.save()
        logger.info("Detection %s QUEUED for review conf=%.2f combined=%.2f", detection.id, conf, combined)
        return detection, None, 'queued_review'

    detection.status = Detection.REJECTED
    detection.reviewed_at = timezone.now()
    detection.review_notes = (
        f"Auto-ignored low confidence (combined={combined:.2f} < floor={floor:.2f})."
    )
    detection.save()
    logger.info("Detection %s IGNORED conf=%.2f combined=%.2f", detection.id, conf, combined)
    return detection, None, 'ignored'


def _issue_auto_challan(detection, user=None):
    from challans.models import Challan
    from admin.dig_portal.models import SystemSettings

    existing = Challan.objects.filter(detection=detection).first()
    if existing:
        return existing

    sys_settings = SystemSettings.get()
    plate = detection.effective_plate or 'UNKNOWN'
    plate_series = (plate or 'LRN')[:3].upper()
    ticket_no = Challan.objects.generate_ticket_no(plate_series)
    violation_type = detection.effective_violation_type or Challan.WRONG_WAY
    if violation_type != Challan.WRONG_WAY:
        violation_type = Challan.WRONG_WAY
    cam = detection.camera

    owner_data = {}
    try:
        from admin.officer_portal.views import lookup_owner_by_plate
        if plate and plate != 'UNKNOWN':
            owner_data = lookup_owner_by_plate(plate) or {}
    except Exception:
        pass

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
            location=cam.location if cam else 'AI Detection',
            camera=cam,
            ai_confidence=detection.ai_confidence,
            # H2 FIX: For a wrong-way violation, the vehicle is moving in the
            # direction OPPOSITE to the legal direction. Use the opposite value.
            moving_direction=(_opposite_direction(cam.legal_direction) if cam and cam.legal_direction else None),
            legal_direction=cam.legal_direction if cam else None,
            issue_date=datetime.date.today(),
            due_date=datetime.date.today() + datetime.timedelta(days=sys_settings.due_date_days),
            payment_status=Challan.UNPAID,
            created_by=user,
        )

    try:
        from challans.pdf_service import save_challan_pdf
        save_challan_pdf(challan)
    except Exception as e:
        logger.warning("Auto-challan PDF deferred: %s", e)
    try:
        from challans.email_service import send_challan_notification
        send_challan_notification(challan)
    except Exception as e:
        logger.warning("Auto-challan email skipped: %s", e)

    try:
        from admin.dig_portal.models import AuditLog
        AuditLog.write(
            None, 'detection.auto_confirm', 'Detection', detection.id,
            plate=plate, challan=ticket_no, confidence=detection.ai_confidence,
        )
    except Exception:
        pass

    return challan

