"""Court-ready evidence frame annotation.

Takes a detection's raw capture frame and renders the single large evidence
image displayed on challan PDFs: vehicle containment box, plate box, wrong-way
direction arrow, capture telemetry strip. The original raw frame is never
modified; the annotated copy is stored on ``Detection.annotated_image``.
"""
from __future__ import annotations

import datetime
import io
import logging

from django.core.files.base import ContentFile

logger = logging.getLogger('wrongway.evidence')

FONT_CANDIDATES = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
)


def _load_font(size: int):
    from PIL import ImageFont
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _clamp(value, low, high):
    return max(low, min(high, value))


def annotate_evidence_frame(detection, camera=None) -> bytes | None:
    """Render the annotated JPEG bytes for a detection, or None on failure."""
    try:
        from PIL import Image, ImageDraw

        if not detection.raw_image:
            return None
        with detection.raw_image.open('rb') as fh:
            image = Image.open(fh).convert('RGB')

        draw = ImageDraw.Draw(image)
        width, height = image.size
        scale = max(width, height) / 1920.0
        box_w = max(2, int(4 * scale))
        font_small = _load_font(max(14, int(18 * scale)))
        font_big = _load_font(max(20, int(30 * scale)))

        raw = detection.ai_raw_response or {}
        plate_bbox = raw.get('bbox')
        vehicle_bbox = raw.get('vehicle_bbox')

        # Vehicle containment box (red)
        if vehicle_bbox and len(vehicle_bbox) == 4:
            vx1, vy1, vx2, vy2 = [int(_clamp(v, 0, width if i % 2 == 0 else height))
                                  for i, v in enumerate(vehicle_bbox)]
            draw.rectangle([vx1, vy1, vx2, vy2], outline=(220, 38, 38), width=box_w)

        # Plate box (yellow)
        if plate_bbox and len(plate_bbox) == 4:
            px1, py1, px2, py2 = [int(_clamp(v, 0, width if i % 2 == 0 else height))
                                  for i, v in enumerate(plate_bbox)]
            draw.rectangle([px1, py1, px2, py2], outline=(250, 204, 21), width=max(2, int(3 * scale)))

        # Wrong-way direction arrow across the vehicle box
        if vehicle_bbox and len(vehicle_bbox) == 4:
            vx1, vy1, vx2, vy2 = [int(v) for v in vehicle_bbox]
            mid_y = (vy1 + vy2) // 2
            raw_side = (detection.ai_side_classification or '')
            # arrow flows against legal direction: back-facing plates => vehicle travelling away
            arrow_len = max(60, int((vx2 - vx1) * 0.9))
            if raw_side == 'back':
                ax1, ax2 = vx1 + arrow_len, vx1
            else:
                ax1, ax2 = vx2 - arrow_len, vx2
            ax1, ax2 = _clamp(ax1, 0, width), _clamp(ax2, 0, width)
            draw.line([ax1, mid_y, ax2, mid_y], fill=(220, 38, 38), width=box_w)
            head = max(12, int(18 * scale))
            if ax2 < ax1:
                pts = [(ax2, mid_y), (ax2 + head, mid_y - head), (ax2 + head, mid_y + head)]
            else:
                pts = [(ax2, mid_y), (ax2 - head, mid_y - head), (ax2 - head, mid_y + head)]
            draw.polygon(pts, fill=(220, 38, 38))

        # Header band
        band_h = max(34, int(44 * scale))
        draw.rectangle([0, 0, width, band_h], fill=(15, 37, 78))
        draw.text((int(14 * scale), int(6 * scale)),
                  'SAFE CITIES PROJECT  |  TRAFFIC VIOLATION EVIDENCE',
                  fill=(255, 255, 255), font=font_big)

        # Telemetry strip
        ts = (detection.created_at or datetime.datetime.now())
        ts_str = ts.strftime('%d-%m-%Y %H:%M:%S')
        cam_id = getattr(camera, 'camera_id', None) or (
            detection.camera.camera_id if detection.camera else 'N/A')
        area = getattr(camera, 'location', None) or (
            detection.camera.location if detection.camera else 'N/A')
        strip = (
            f'CAM {cam_id}  |  AREA {area}  |  {ts_str}  |  '
            f'PLATE {detection.effective_plate or "UNREAD"}  |  '
            f'VIOLATION: WRONG WAY'
        )
        draw.rectangle([0, height - band_h, width, height], fill=(15, 37, 78))
        draw.text((int(14 * scale), height - band_h + int(6 * scale)),
                  strip[:120], fill=(255, 255, 255), font=font_small)

        out = io.BytesIO()
        image.save(out, format='JPEG', quality=90)
        return out.getvalue()
    except Exception as exc:
        logger.warning('evidence annotation failed for detection %s: %s',
                       getattr(detection, 'pk', None), exc)
        return None


def store_annotated_evidence(detection, camera=None) -> bool:
    """Render and persist the annotated evidence frame on the detection."""
    data = annotate_evidence_frame(detection, camera)
    if not data:
        return False
    try:
        name = f"annotated_det{detection.pk or 0}_{int(datetime.datetime.now().timestamp())}.jpg"
        detection.annotated_image.save(name, ContentFile(data), save=True)
        return True
    except Exception as exc:
        logger.warning('annotated evidence store failed: %s', exc)
        return False
