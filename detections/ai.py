from __future__ import annotations

import logging

import numpy as np
import os
from pathlib import Path
from typing import List, Tuple

from PIL import Image
from django.conf import settings

logger = logging.getLogger('wrongway.ai')

def get_ai_runtime_config():
    defaults = {
        'plate_detector': {
            'file': 'NumberPlate_detection_model_int8.onnx',
            'input_name': 'input',
            'input_shape': [1, 3, 560, 560],
            'input_layout': 'NCHW',
            'input_normalize': 'imagenet',
            'output_dets': 'dets',
            'output_labels': 'labels',
            'max_detections': 300,
            'num_classes': 91,
            'plate_class_ids': [1],
            'person_class_id': -1,
            'confidence_threshold': 0.15,
            'max_box_area_ratio': 0.18,
            'min_box_area_ratio': 0.0003,
            'box_tighten': 0.95,
            'nms_iou': 0.45,
        },
        'side_classifier': {
            'file': 'car_side_Classifier_model_int8.onnx',
            'input_name': 'input',
            'input_shape': [1, 224, 224, 3],
            'input_layout': 'NHWC',
            'input_normalize': '-1_1',
            'back_threshold': 0.50,
            'min_side_confidence': 0.60,
            'class_names': ['back', 'front'],
            'crop_expand_w': 3.5,
            'crop_expand_h': 4.5,
        },
        'car_only': True,
        'reject_person': False,
        'ai_confidence_threshold': 0.55,
    }
    try:
        from admin.dig_portal.models import SystemSettings
        s = SystemSettings.get()
        cfg = dict(defaults)
        stored = s.ai_config or {}
        if stored:
            for k, v in stored.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    merged = dict(cfg[k])
                    merged.update(v)
                    cfg[k] = merged
                else:
                    cfg[k] = v
        sys_thr = float(getattr(s, 'ai_confidence_threshold', None) or 0.55)
        cfg['ai_confidence_threshold'] = max(0.40, min(0.99, sys_thr))
        if 'plate_detector' in cfg:
            det_thr = float(cfg['plate_detector'].get('confidence_threshold') or 0.15)
            cfg['plate_detector']['confidence_threshold'] = max(0.10, min(0.95, det_thr))
        cfg['confidence_threshold'] = float(cfg.get('plate_detector', {}).get('confidence_threshold') or cfg.get('ai_confidence_threshold') or 0.55)
        cfg['auto_confirm_threshold'] = float(getattr(s, 'auto_confirm_threshold', 0.85) if 's' in locals() else 0.85)
        return cfg
    except Exception:
        defaults['confidence_threshold'] = defaults['ai_confidence_threshold']
        defaults['auto_confirm_threshold'] = 0.85
        return defaults


PLATE_CONFIDENCE_THRESHOLD = 0.15

_plate_detector_session = None
_side_classifier_session = None
_side_input_meta = None


def _get_plate_detector():
    global _plate_detector_session
    if _plate_detector_session is not None:
        return _plate_detector_session
    try:
        import onnxruntime as ort
        model_path = str(settings.PLATE_DETECTOR_MODEL)
        if not os.path.exists(model_path):
            logger.error("Plate detector model not found at %s", model_path)
            return None
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _plate_detector_session = ort.InferenceSession(
            model_path, sess_options=opts, providers=['CPUExecutionProvider']
        )
        inp = _plate_detector_session.get_inputs()[0]
        logger.info("ONNX plate detector loaded: %s  input=%s shape=%s",
                    model_path, inp.name, inp.shape)
        return _plate_detector_session
    except Exception as e:
        logger.exception("Failed to load ONNX plate detector: %s", e)
        return None


def _get_side_classifier():
    global _side_classifier_session, _side_input_meta
    if _side_classifier_session is not None:
        return _side_classifier_session
    try:
        import onnxruntime as ort
        model_path = str(settings.SIDE_CLASSIFIER_MODEL)
        if not os.path.exists(model_path):
            logger.error("Side classifier model not found at %s", model_path)
            return None
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _side_classifier_session = ort.InferenceSession(
            model_path, sess_options=opts, providers=['CPUExecutionProvider']
        )
        inp = _side_classifier_session.get_inputs()[0]
        shape = list(inp.shape)
        layout = 'NHWC'
        if len(shape) == 4:
            if shape[1] == 3:
                layout = 'NCHW'
            elif shape[-1] == 3:
                layout = 'NHWC'
        _side_input_meta = (inp.name, shape, layout)
        logger.info("ONNX side classifier loaded: %s  input=%s shape=%s layout=%s",
                    model_path, inp.name, shape, layout)
        return _side_classifier_session
    except Exception as e:
        logger.exception("Failed to load ONNX side classifier: %s", e)
        return None


def _plate_input_size(sess) -> Tuple[int, int]:
    try:
        shape = sess.get_inputs()[0].shape
        nums = [int(x) for x in shape if isinstance(x, (int, np.integer)) and int(x) > 3]
        if len(nums) >= 2:
            return int(nums[-2]), int(nums[-1])
        if len(nums) == 1:
            return int(nums[0]), int(nums[0])
    except Exception:
        pass
    return 560, 560


def _preprocess_for_plate_detector(image: Image.Image, sess=None) -> np.ndarray:
    h, w = _plate_input_size(sess) if sess is not None else (560, 560)
    img = image.convert('RGB').resize((w, h), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    arr = arr.transpose(2, 0, 1)
    return np.expand_dims(arr, axis=0).astype(np.float32)


def _preprocess_for_side_classifier(image: Image.Image) -> np.ndarray:
    img = image.convert('RGB').resize((224, 224), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32)
    arr = arr / 127.5 - 1.0
    layout = 'NHWC'
    if _side_input_meta:
        layout = _side_input_meta[2]
    if layout == 'NCHW':
        arr = arr.transpose(2, 0, 1)
    return np.expand_dims(arr, axis=0).astype(np.float32)


def _softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    e = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e / np.sum(e, axis=axis, keepdims=True)


def _iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _nms(boxes_scores: List[Tuple[tuple, float]], iou_thr: float = 0.45) -> List[Tuple[tuple, float]]:
    if not boxes_scores:
        return []
    order = sorted(boxes_scores, key=lambda x: x[1], reverse=True)
    keep = []
    while order:
        best = order.pop(0)
        keep.append(best)
        order = [r for r in order if _iou(best[0], r[0]) < iou_thr]
    return keep


def _expand_box_to_vehicle(bbox, img_w: float, img_h: float,
                           expand_w: float = 3.5, expand_h: float = 4.5):
    x1, y1, x2, y2 = [float(v) for v in bbox]
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    bw = max(x2 - x1, 1.0)
    bh = max(y2 - y1, 1.0)
    new_w = bw * expand_w
    new_h = bh * expand_h
    nx1 = max(0.0, cx - new_w / 2.0)
    nx2 = min(img_w, cx + new_w / 2.0)
    ny2 = min(img_h, cy + bh * 1.2)
    ny1 = max(0.0, ny2 - new_h)
    if ny2 - ny1 < bh * 2:
        ny1 = max(0.0, cy - new_h * 0.65)
        ny2 = min(img_h, cy + new_h * 0.35)
    return (nx1, ny1, nx2, ny2)


def _detect_plates(image: Image.Image, threshold: float = None):
    cfg = get_ai_runtime_config()
    pd = cfg.get('plate_detector', {})
    if threshold is None:
        threshold = float(pd.get('confidence_threshold') or PLATE_CONFIDENCE_THRESHOLD)
    threshold = max(0.10, min(0.99, float(threshold)))
    max_area = min(float(pd.get('max_box_area_ratio') or 0.18), 0.22)
    min_area = float(pd.get('min_box_area_ratio') or 0.0003)
    tighten = float(pd.get('box_tighten') or 0.95)
    person_id = int(pd.get('person_class_id', 1))
    reject_person = bool(cfg.get('reject_person', True))
    nms_iou = float(pd.get('nms_iou') or 0.45)
    plate_class_ids = set(int(x) for x in (pd.get('plate_class_ids') or [0]))

    sess = _get_plate_detector()
    if sess is None:
        return []
    try:
        input_arr = _preprocess_for_plate_detector(image, sess)
        input_name = sess.get_inputs()[0].name
        outputs = sess.run(None, {input_name: input_arr})
        dets = np.asarray(outputs[0][0])
        labels = np.asarray(outputs[1][0])

        scores = 1.0 / (1.0 + np.exp(-np.clip(labels.astype(np.float64), -40, 40)))
        num_classes = scores.shape[-1]

        if reject_person and num_classes > person_id:
            scores = scores.copy()
            scores[:, person_id] = 0.0

        if num_classes <= 2 or (plate_class_ids and max(plate_class_ids) < num_classes):
            use_ids = [i for i in plate_class_ids if i < num_classes]
            if not use_ids:
                use_ids = list(range(num_classes))
            max_probs = np.max(scores[:, use_ids], axis=-1)
            class_ids = np.array(use_ids)[np.argmax(scores[:, use_ids], axis=-1)]
        else:
            max_probs = np.max(scores, axis=-1)
            class_ids = np.argmax(scores, axis=-1)

        orig_w, orig_h = float(image.size[0]), float(image.size[1])
        img_area = max(orig_w * orig_h, 1.0)
        results = []
        for i in range(dets.shape[0]):
            conf = float(max_probs[i])
            if conf < threshold:
                continue
            cls = int(class_ids[i])
            if reject_person and cls == person_id:
                continue

            cx, cy, w, h = [float(v) for v in dets[i]]
            if max(abs(cx), abs(cy), abs(w), abs(h)) > 1.5:
                cx, cy, w, h = cx / orig_w, cy / orig_h, w / orig_w, h / orig_h

            w = min(max(abs(w), 0.005), 0.50)
            h = min(max(abs(h), 0.005), 0.50)
            w *= tighten
            h *= tighten
            x1 = max(0.0, (cx - w / 2.0) * orig_w)
            y1 = max(0.0, (cy - h / 2.0) * orig_h)
            x2 = min(orig_w, (cx + w / 2.0) * orig_w)
            y2 = min(orig_h, (cy + h / 2.0) * orig_h)
            bw, bh = (x2 - x1), (y2 - y1)
            if bw < 8 or bh < 6:
                continue
            area_ratio = (bw * bh) / img_area
            if area_ratio > max_area or area_ratio < min_area:
                continue
            aspect = bw / max(bh, 1.0)
            if aspect < 0.4 or aspect > 8.0:
                continue
            results.append(((x1, y1, x2, y2), conf))

        results = _nms(results, iou_thr=nms_iou)
        results.sort(key=lambda r: r[1], reverse=True)
        logger.info(
            "Plate detector: %d plate-sized boxes thr=%.2f max_area=%.2f",
            len(results), threshold, max_area,
        )
        return results
    except Exception as e:
        logger.exception("Plate detector inference failed: %s", e)
        return []


def _classify_side(image: Image.Image) -> Tuple[str, float]:
    sess = _get_side_classifier()
    if sess is None:
        return 'front', 0.0
    try:
        input_arr = _preprocess_for_side_classifier(image)
        input_name = (_side_input_meta[0] if _side_input_meta else sess.get_inputs()[0].name)
        outputs = sess.run(None, {input_name: input_arr})
        out = np.asarray(outputs[0]).reshape(-1)

        if out.size >= 2:
            probs = _softmax(out.astype(np.float64))
            names = list(get_ai_runtime_config().get('side_classifier', {}).get('class_names') or ['back', 'front'])
            if len(names) < 2:
                names = ['back', 'front']

            if float(np.max(probs) - np.min(probs)) < 0.01:
                logger.warning(
                    "C3: Side classifier output is near-uniform (%.4f~%.4f) — model may be "
                    "defective (constant INT8 export). Returning unknown side.",
                    float(np.min(probs)), float(np.max(probs))
                )
                return '', 0.0

            pairs = [(names[i] if i < len(names) else f'cls{i}', float(probs[i])) for i in range(min(len(probs), len(names)))]
            by_name = {n.lower(): p for n, p in pairs}
            if 'front' in by_name and 'back' in by_name:
                if by_name['front'] >= by_name['back']:
                    return 'front', by_name['front']
                return 'back', by_name['back']
            best_name, best_p = max(pairs, key=lambda t: t[1])
            label = best_name.lower() if best_name.lower() in ('front', 'back') else ('back' if best_name == names[0] else 'front')
            return label, best_p

        val = float(out[0])
        if val == 0.0:
            logger.warning("C3: Side classifier returned 0.0 — dead model output. Returning unknown side.")
            return '', 0.0
        if val < 0.0 or val > 1.0:
            val = 1.0 / (1.0 + np.exp(-val))
        back_p = val
        front_p = 1.0 - back_p
        if back_p >= 0.5:
            return 'back', back_p
        return 'front', front_p
    except Exception as e:
        logger.exception("Side classifier inference failed: %s", e)
        return 'front', 0.0


def _crop_and_save(image: Image.Image, bbox, save_path: Path):
    try:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(image.size[0], x2), min(image.size[1], y2)
        if x2 <= x1 or y2 <= y1:
            return None
        crop = image.crop((x1, y1, x2, y2))
        crop.save(str(save_path), format='JPEG', quality=90)
        return save_path
    except Exception as e:
        logger.warning("Failed to save plate crop: %s", e)
        return None



import re as _re

_PK_PLATE_RE = _re.compile(
    r'([A-Z]{1,3})[\s\-]*([0-9]{1,4})|'
    r'([A-Z]{3})[\s\-]*([0-9]{1,4})|'
    r'([A-Z]{2,3}[0-9]{2,4})',
    _re.I,
)


def _normalize_plate_text(raw: str) -> str:
    if not raw:
        return ''
    s = _re.sub(r'[^A-Za-z0-9]', '', raw).upper()
    if len(s) < 3:
        return ''
    m = _re.match(r'^([A-Z]{1,3})([0-9]{2,4})$', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = _re.match(r'^([A-Z]{3})([0-9]{1,4})$', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return s


_paddle_ocr = None
_easyocr_reader = None


def _get_paddle_ocr():
    """Lazy-load PaddleOCR (preferred plate reader)."""
    global _paddle_ocr
    if _paddle_ocr is not None:
        return _paddle_ocr
    try:
        from paddleocr import PaddleOCR
        _paddle_ocr = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            show_log=False,
            use_gpu=False,
        )
        logger.info('PaddleOCR loaded for plate text recognition')
        return _paddle_ocr
    except Exception as e:
        logger.warning('PaddleOCR unavailable: %s', e)
        _paddle_ocr = False
        return None


def _get_easyocr():
    """Lazy-load EasyOCR reader (secondary plate reader)."""
    global _easyocr_reader
    if _easyocr_reader is not None:
        return _easyocr_reader if _easyocr_reader is not False else None
    try:
        import easyocr
        _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        logger.info('EasyOCR loaded for plate text recognition')
        return _easyocr_reader
    except Exception as e:
        logger.warning('EasyOCR unavailable: %s', e)
        _easyocr_reader = False
        return None


def _preprocess_plate_for_ocr(pil_image):
    """Return list of numpy images (RGB / enhanced) for multi-pass OCR."""
    import numpy as np
    variants = []
    try:
        import cv2
        arr = np.array(pil_image.convert('RGB'))
        variants.append(arr)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        gray = cv2.bilateralFilter(gray, 7, 50, 50)
        h, w = gray.shape[:2]
        scale = 2.5 if max(h, w) < 160 else 1.8
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        thr = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 8
        )
        variants.append(cv2.cvtColor(thr, cv2.COLOR_GRAY2RGB))
        variants.append(cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB))
    except Exception:
        variants.append(np.array(pil_image.convert('RGB')))
    return variants


def _ocr_plate_image(pil_image) -> tuple:
    """Return (plate_text, ocr_confidence 0..1, engine_name).

    Engine order (best for PK plates):
      1) PaddleOCR
      2) EasyOCR
      3) pytesseract (optional fallback)
    """
    candidates = []  # (text, conf, engine)
    variants = _preprocess_plate_for_ocr(pil_image)

    paddle = _get_paddle_ocr()
    if paddle:
        for img in variants:
            try:
                raw = paddle.ocr(img, cls=True)
                lines = raw[0] if raw and isinstance(raw, list) else raw
                if not lines:
                    continue
                for item in lines:
                    try:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            txt_conf = item[1]
                            if isinstance(txt_conf, (list, tuple)):
                                txt, conf = txt_conf[0], float(txt_conf[1])
                            else:
                                continue
                        else:
                            continue
                    except Exception:
                        continue
                    n = _normalize_plate_text(str(txt))
                    if n:
                        candidates.append((n, max(0.0, min(1.0, conf)), 'paddle'))
            except Exception as e:
                logger.debug('PaddleOCR pass failed: %s', e)

    if not candidates or max(c[1] for c in candidates) < 0.55:
        reader = _get_easyocr()
        if reader:
            import numpy as np
            for img in variants:
                try:
                    out = reader.readtext(
                        img, detail=1,
                        allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-',
                    )
                    for _box, txt, conf in out or []:
                        n = _normalize_plate_text(str(txt))
                        if n:
                            candidates.append((n, float(conf), 'easyocr'))
                except Exception as e:
                    logger.debug('EasyOCR pass failed: %s', e)

    if not candidates:
        try:
            import pytesseract
            from PIL import Image as _PILImage
            cfg = r'--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
            for img in variants[:2]:
                im = _PILImage.fromarray(img).convert('L')
                txt = pytesseract.image_to_string(im, config=cfg) or ''
                n = _normalize_plate_text(txt)
                if n:
                    candidates.append((n, 0.70, 'tesseract'))
        except Exception:
            pass

    if not candidates:
        return '', 0.0, ''

    def score(item):
        text, conf, eng = item
        bonus = 0.03 if eng == 'paddle' else (0.01 if eng == 'easyocr' else 0.0)
        return (len(text), conf + bonus)

    candidates.sort(key=score, reverse=True)
    best_text, best_conf, best_eng = candidates[0]
    logger.info('OCR plate=%s conf=%.2f engine=%s', best_text, best_conf, best_eng)
    return best_text, float(best_conf), best_eng


def run_pipeline(image_path, camera=None, plate_threshold: float = PLATE_CONFIDENCE_THRESHOLD):

    result = {
        'plate_text': None, 'province': None, 'series': None, 'registration_year': None,
        'side': None, 'confidence': 0.0, 'detected_violation': False,
        'plate_crop_path': None, 'raw_ai_response': {}, 'error': None,
    }
    try:
        image = Image.open(image_path).convert('RGB')
    except Exception as e:
        result['error'] = f"Image load failed: {e}"
        logger.error(result['error'])
        return result

    cfg = get_ai_runtime_config()
    pd = cfg.get('plate_detector', {})
    sc = cfg.get('side_classifier', {})
    det_thr = float(plate_threshold if plate_threshold is not None else pd.get('confidence_threshold') or PLATE_CONFIDENCE_THRESHOLD)
    min_side = float(sc.get('min_side_confidence') or 0.60)
    expand_w = float(sc.get('crop_expand_w') or 3.5)
    expand_h = float(sc.get('crop_expand_h') or 4.5)

    detections = _detect_plates(image, threshold=det_thr)
    top_confidence = 0.0
    top_bbox = None
    vehicle_bbox = None
    side_image = image

    ocr_text, ocr_conf, ocr_engine = '', 0.0, ''
    if detections:
        top_bbox, top_confidence = detections[0]
        crop_path = Path(image_path).parent / f"plate_crop_{Path(image_path).stem}.jpg"
        if _crop_and_save(image, top_bbox, crop_path):
            result['plate_crop_path'] = str(crop_path)
            try:
                plate_crop_img = Image.open(crop_path).convert('RGB')
                ocr_text, ocr_conf, ocr_engine = _ocr_plate_image(plate_crop_img)
            except Exception as e:
                logger.debug('OCR failed: %s', e)
        if ocr_text:
            result['plate_text'] = ocr_text
            parts = ocr_text.replace('-', ' ').split()
            if len(parts) >= 1 and parts[0].isalpha():
                result['series'] = parts[0][:3]
            if len(parts) >= 2 and parts[1].isdigit():
                if len(parts[1]) == 4 and parts[1].startswith(('19', '20')):
                    result['registration_year'] = parts[1]
        ow, oh = image.size
        vehicle_bbox = _expand_box_to_vehicle(top_bbox, ow, oh, expand_w, expand_h)
        try:
            vx1, vy1, vx2, vy2 = [int(v) for v in vehicle_bbox]
            side_image = image.crop((vx1, vy1, vx2, vy2))
            if side_image.size[0] < 16 or side_image.size[1] < 16:
                side_image = image
        except Exception:
            side_image = image

    result['confidence'] = float(top_confidence)
    result['bbox'] = [float(v) for v in top_bbox] if top_bbox else None

    side, side_conf = _classify_side(side_image)
    result['side'] = side or None
    violation_side = getattr(camera, 'violation_side', None) or 'back'

    has_vehicle = bool(top_bbox is not None and top_confidence >= det_thr)
    side_ok = side_conf >= min_side
    result['detected_violation'] = bool(has_vehicle and side_ok and side == violation_side)

    if top_confidence > 0:
        result['confidence'] = float(top_confidence)
    elif side_conf >= min_side and has_vehicle:
        result['confidence'] = float(side_conf)
    else:
        result['confidence'] = float(top_confidence) if top_confidence > 0 else 0.0

    ow, oh = image.size
    result['raw_ai_response'] = {
        'plate_detections': [
            {
                'bbox': [float(v) for v in bbox],
                'confidence': float(conf),
                'bbox_norm': [
                    float(bbox[0]) / ow, float(bbox[1]) / oh,
                    float(bbox[2]) / ow, float(bbox[3]) / oh,
                ],
            }
            for bbox, conf in detections[:5]
        ],
        'bbox': result['bbox'],
        'bbox_norm': (
            [float(top_bbox[0]) / ow, float(top_bbox[1]) / oh,
             float(top_bbox[2]) / ow, float(top_bbox[3]) / oh]
            if top_bbox else None
        ),
        'vehicle_bbox': [float(v) for v in vehicle_bbox] if vehicle_bbox else None,
        'side': side,
        'side_confidence': float(side_conf),
        'plate_confidence': float(top_confidence),
        'plate_threshold': float(det_thr),
        'min_side_confidence': float(min_side),
        'image_size': list(image.size),
        'violation_side': violation_side,
        'has_vehicle': has_vehicle,
        'violation_type': 'wrong_way',
        'side_on_crop': bool(top_bbox is not None),
        'ocr_text': ocr_text or None,
        'ocr_confidence': float(ocr_conf),
        'ocr_engine': ocr_engine or None,
        'plate_text': result.get('plate_text'),
    }
    logger.info(
        "AI pipeline: plates=%d plate_conf=%.3f side=%s side_conf=%.3f violation=%s",
        len(detections), top_confidence, side, side_conf, result['detected_violation'],
    )

    if result.get('plate_text'):
        try:
            from admin.dig_portal.models import BlacklistEntry
            plate = str(result['plate_text']).strip().upper()
            plate_norm = plate.replace(' ', '').replace('-', '')
            bl_hit = (
                BlacklistEntry.objects
                .filter(is_active=True)
                .filter(plate_number__iexact=plate)
                .first()
            )
            if not bl_hit and plate_norm:
                bl_hit = (
                    BlacklistEntry.objects
                    .filter(is_active=True)
                    .filter(plate_number__icontains=plate_norm[:6])
                    .first()
                )
            if bl_hit:
                result['blacklisted'] = True
                result['blacklist_reason'] = bl_hit.reason
                result['detected_violation'] = False
                logger.info('AI pipeline: plate %s is blacklisted (%s)', plate, bl_hit.reason)
            else:
                result['blacklisted'] = False
        except Exception as e:
            logger.debug('blacklist lookup failed: %s', e)

    result.setdefault('blacklisted', False)
    result.setdefault('blacklist_reason', None)
    result['ai_confidence'] = result.get('confidence', 0.0)
    result['side_classification'] = result.get('side')
    return result


def is_models_available():
    return (os.path.exists(str(settings.PLATE_DETECTOR_MODEL)) and
            os.path.exists(str(settings.SIDE_CLASSIFIER_MODEL)))


def get_model_info():
    cfg = get_ai_runtime_config()
    pd = cfg.get('plate_detector', {})
    sc = cfg.get('side_classifier', {})
    return {
        'ocr_backend': 'easyocr',
        'plate_detector': {
            'path': str(settings.PLATE_DETECTOR_MODEL),
            'exists': os.path.exists(str(settings.PLATE_DETECTOR_MODEL)),
            'size_mb': round(os.path.getsize(settings.PLATE_DETECTOR_MODEL) / 1024 / 1024, 1)
                       if os.path.exists(str(settings.PLATE_DETECTOR_MODEL)) else 0,
            'file': pd.get('file', 'NumberPlate_detection_model_int8.onnx'),
            'input_name': pd.get('input_name', 'input'),
            'input_shape': pd.get('input_shape', [1, 3, 560, 560]),
            'input_layout': pd.get('input_layout', 'NCHW'),
            'input_format': 'NCHW, ImageNet mean/std (RF-DETR notebook)',
            'input_normalize': pd.get('input_normalize', 'imagenet'),
            'outputs': ['dets [1, N, 4]', 'labels [1, N, C]'],
            'max_detections': pd.get('max_detections', 300),
            'num_classes': pd.get('num_classes', 91),
            'plate_class_ids': pd.get('plate_class_ids', [0]),
            'confidence_threshold': pd.get('confidence_threshold', 0.45),
            'max_box_area_ratio': pd.get('max_box_area_ratio', 0.18),
            'box_tighten': pd.get('box_tighten', 0.95),
        },
        'side_classifier': {
            'path': str(settings.SIDE_CLASSIFIER_MODEL),
            'exists': os.path.exists(str(settings.SIDE_CLASSIFIER_MODEL)),
            'size_mb': round(os.path.getsize(settings.SIDE_CLASSIFIER_MODEL) / 1024 / 1024, 1)
                       if os.path.exists(str(settings.SIDE_CLASSIFIER_MODEL)) else 0,
            'file': sc.get('file', 'car_side_Classifier_model_int8.onnx'),
            'input_name': sc.get('input_name', 'input'),
            'input_shape': sc.get('input_shape', [1, 224, 224, 3]),
            'input_layout': sc.get('input_layout', 'NHWC'),
            'input_format': 'HWC, MobileNetV2 preprocess [-1, 1]',
            'input_normalize': sc.get('input_normalize', '-1_1'),
            'output': '[N,1] dense score → P(back) after sigmoid if needed',
            'back_threshold': sc.get('back_threshold', 0.50),
            'min_side_confidence': sc.get('min_side_confidence', 0.60),
            'crop_expand_w': sc.get('crop_expand_w', 3.5),
            'crop_expand_h': sc.get('crop_expand_h', 4.5),
        },
        'runtime': {
            'car_only': cfg.get('car_only', True),
            'reject_person': cfg.get('reject_person', True),
            'ai_confidence_threshold': cfg.get('ai_confidence_threshold', 0.55),
            'side_on_vehicle_crop': True,
        },
    }

