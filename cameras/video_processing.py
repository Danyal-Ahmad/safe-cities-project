import io
import os
import logging
import tempfile
import threading

from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger('wrongway.video_upload')

MAX_FRAMES_PER_UPLOAD = 500
EVIDENCE_FRAMES_REQUIRED = 3
BURST_MAX_EXTRA = 8
BURST_FPS_CAP = 90.0


def _extract_frame_timestamps(duration_seconds, interval_seconds):
    if duration_seconds <= 0 or interval_seconds <= 0:
        return [0.0]
    n = int(duration_seconds // interval_seconds) + 1
    n = max(1, min(n, MAX_FRAMES_PER_UPLOAD))
    return [i * interval_seconds for i in range(n) if i * interval_seconds < duration_seconds] or [0.0]


def _burst_timestamps(base_ts, fps):
    """Dense burst timestamps after a candidate violation frame.

    90FPS-style sampling: consecutive frames spaced at the video's native
    cadence (never denser than 1/90s). Each burst frame is checked 1-by-1
    until EVIDENCE_FRAMES_REQUIRED matching plate reads are collected.
    """
    native = float(fps) if fps and fps > 0 else 30.0
    step = max(1.0 / BURST_FPS_CAP, 1.0 / native)
    return [base_ts + (i + 1) * step for i in range(BURST_MAX_EXTRA)]


def _frame_to_image(cap, ts):
    cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    import cv2 as _cv2
    from PIL import Image
    rgb = _cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _run_ai(tmp_path, camera):
    from detections.ai import run_pipeline
    try:
        return run_pipeline(tmp_path, camera)
    except Exception as ai_err:
        logger.warning("AI pipeline failed for frame @%ss: %s", tmp_path, ai_err)
        return {}


def _valid_evidence_plate(result):
    from detections.ai import is_valid_pk_plate
    plate = (result.get('plate_text') or '').strip().upper()
    raw = result.get('raw_ai_response') or {}
    return plate if (is_valid_pk_plate(plate) and raw.get('plate_complete')) else None


def process_video_upload(upload_id):
    global cv2
    import cv2
    from PIL import Image
    from video_processor.models import VideoUpload, VideoFrame
    from detections.models import Detection
    from detections.ai import is_valid_pk_plate

    try:
        upload = VideoUpload.objects.select_related('camera').get(pk=upload_id)
    except VideoUpload.DoesNotExist:
        logger.warning("process_video_upload: VideoUpload %s does not exist (rolled back or deleted).", upload_id)
        return
    camera = upload.camera
    upload.status = VideoUpload.STATUS_PROCESSING
    upload.processing_started_at = timezone.now()
    upload.save(update_fields=['status', 'processing_started_at'])

    interval = camera.capture_interval if camera else 5
    video_path = upload.video_file.path
    cap = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError("Could not open video file — unsupported or corrupt format.")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count_total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration = frame_count_total / fps if fps > 0 else 0

        timestamps = _extract_frame_timestamps(duration, interval)
        upload.total_frames_extracted = len(timestamps)
        upload.save(update_fields=['total_frames_extracted'])

        frames_with_plates = 0
        violations_detected = 0
        auto_challans_created = 0
        manual_review_created = 0
        frames_ignored = 0
        burst_evidence_collected = 0

        for idx, ts in enumerate(timestamps):
            image = _frame_to_image(cap, ts)
            if image is None:
                frames_ignored += 1
                VideoFrame.objects.create(
                    video_upload=upload, frame_number=idx, timestamp_secs=ts,
                    plate_detected=False, auto_processed=False,
                )
                continue

            video_frame = VideoFrame(video_upload=upload, frame_number=idx, timestamp_secs=ts)

            try:
                result = {}
                if camera is not None:
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                        image.save(tmp, format='JPEG', quality=92)
                        tmp_path = tmp.name
                    try:
                        result = _run_ai(tmp_path, camera)
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass

                plate_text = result.get('plate_text')
                confidence = result.get('confidence')
                side = result.get('side')
                is_violation = bool(result.get('detected_violation'))

                video_frame.plate_detected = bool(result.get('plate_crop_path'))
                video_frame.side_classification = side
                video_frame.ai_confidence = confidence
                video_frame.ocr_text = plate_text

                frame_io = io.BytesIO()
                image.save(frame_io, format='JPEG', quality=88)
                video_frame.frame_image.save(
                    f"{upload.id}_frame{idx}_{ts:.1f}s.jpg",
                    ContentFile(frame_io.getvalue()), save=False,
                )

                if video_frame.plate_detected:
                    frames_with_plates += 1

                if camera is None:
                    frames_ignored += 1
                else:
                    raw_io = io.BytesIO()
                    image.save(raw_io, format='JPEG', quality=92)

                    detection = Detection(
                        camera=camera,
                        ai_plate_text=plate_text,
                        ai_province=result.get('province'),
                        ai_series=result.get('series'),
                        ai_registration_year=result.get('registration_year'),
                        ai_side_classification=side,
                        ai_confidence=confidence,
                        ai_detected_violation=is_violation,
                        ai_workflow_version="onnx-plate+onnx-side (video-upload, 3-frame burst)",
                        ai_raw_response=result.get('raw_ai_response', {}) or {},
                        status=Detection.PENDING,
                        source_video_upload=upload,
                    )
                    detection.raw_image.save(
                        f"{camera.camera_id}_upload{upload.id}_f{idx}.jpg",
                        ContentFile(raw_io.getvalue()), save=False,
                    )
                    if result.get('plate_crop_path') and os.path.exists(result['plate_crop_path']):
                        with open(result['plate_crop_path'], 'rb') as f:
                            crop_bytes = f.read()
                        detection.plate_crop_image.save(
                            f"crop_{camera.camera_id}_upload{upload.id}_f{idx}.jpg",
                            ContentFile(crop_bytes), save=False,
                        )
                        try:
                            os.unlink(result['plate_crop_path'])
                        except Exception:
                            pass

                    base_plate = _valid_evidence_plate(result)
                    frame_evidence = []
                    if base_plate:
                        raw = result.get('raw_ai_response') or {}
                        frame_evidence.append({
                            'plate': base_plate,
                            'confidence': float(result.get('confidence') or 0.0),
                            'ocr_confidence': float(raw.get('ocr_confidence') or 0.0),
                            'timestamp': f"{ts:.3f}s",
                            'plate_complete': True,
                        })
                        for bts in _burst_timestamps(ts, fps):
                            if len(frame_evidence) >= EVIDENCE_FRAMES_REQUIRED:
                                break
                            bimg = _frame_to_image(cap, bts)
                            if bimg is None:
                                break
                            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as btmp:
                                bimg.save(btmp, format='JPEG', quality=92)
                                btmp_path = btmp.name
                            try:
                                bres = _run_ai(btmp_path, camera)
                            finally:
                                try:
                                    os.unlink(btmp_path)
                                except Exception:
                                    pass
                            bplate = _valid_evidence_plate(bres)
                            if bplate and bplate == base_plate:
                                braw = bres.get('raw_ai_response') or {}
                                frame_evidence.append({
                                    'plate': bplate,
                                    'confidence': float(bres.get('confidence') or 0.0),
                                    'ocr_confidence': float(braw.get('ocr_confidence') or 0.0),
                                    'timestamp': f"{bts:.3f}s",
                                    'plate_complete': True,
                                })
                        if len(frame_evidence) >= EVIDENCE_FRAMES_REQUIRED:
                            raw = result.get('raw_ai_response') or {}
                            raw['frame_evidence'] = frame_evidence
                            raw['burst_mode'] = '90fps_density'
                            result['raw_ai_response'] = raw
                            detection.ai_raw_response = raw
                            burst_evidence_collected += 1
                            logger.info(
                                "Upload %s frame %d: %d-frame evidence collected for %s (1-by-1 verified)",
                                upload.id, idx, len(frame_evidence), base_plate,
                            )

                    detection.save()
                    try:
                        from detections.finalize import finalize_detection_from_ai
                        detection, challan, action = finalize_detection_from_ai(
                            detection, result, camera=camera,
                        )
                        if action == 'challan_issued':
                            video_frame.auto_processed = True
                            auto_challans_created += 1
                        elif action == 'queued_review':
                            video_frame.auto_processed = False
                            manual_review_created += 1
                        else:
                            video_frame.auto_processed = False
                            frames_ignored += 1
                    except Exception as fin_err:
                        logger.warning("finalize failed on upload frame: %s", fin_err)
                        video_frame.auto_processed = False
                        manual_review_created += 1
                    video_frame.detection = detection
                    if is_violation:
                        violations_detected += 1
            finally:
                video_frame.save()

            upload.frames_with_plates = frames_with_plates
            upload.violations_detected = violations_detected
            upload.manual_review_created = manual_review_created
            upload.frames_ignored = frames_ignored
            upload.burst_evidence_collected = burst_evidence_collected
            upload.save(update_fields=['frames_with_plates', 'violations_detected',
                                        'manual_review_created', 'frames_ignored',
                                        'burst_evidence_collected'])

        upload.auto_challans_created = auto_challans_created
        upload.status = VideoUpload.STATUS_COMPLETED
        upload.completed_at = timezone.now()
        upload.save(update_fields=['auto_challans_created', 'status', 'completed_at'])
        if camera is not None:
            camera.mark_online()
        logger.info(
            "Video upload %s done: %d frames, %d with plates, %d bursts with 3-frame evidence, "
            "%d challans, %d sent to review",
            upload.id, len(timestamps), frames_with_plates, burst_evidence_collected,
            auto_challans_created, manual_review_created,
        )

    except Exception as e:
        logger.exception("Video upload %s failed", upload.id)
        upload.status = VideoUpload.STATUS_FAILED
        upload.error_message = str(e)[:2000]
        upload.completed_at = timezone.now()
        upload.save(update_fields=['status', 'error_message', 'completed_at'])
    finally:
        if cap is not None:
            cap.release()


def start_processing_async(upload_id):
    t = threading.Thread(target=process_video_upload, args=(upload_id,), daemon=True)
    t.start()
    return t
