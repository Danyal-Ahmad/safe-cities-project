import io
import logging
import os
import tempfile
import threading

from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger('wrongway.video_upload')

MAX_FRAMES_PER_UPLOAD = 500
SEQUENTIAL_EVIDENCE_FRAMES = 2  


def _extract_frame_timestamps(duration_seconds, interval_seconds):
    if duration_seconds <= 0 or interval_seconds <= 0:
        return [0.0]
    n = int(duration_seconds // interval_seconds) + 1
    n = max(1, min(n, MAX_FRAMES_PER_UPLOAD))
    return [i * interval_seconds for i in range(n) if i * interval_seconds < duration_seconds] or [0.0]


def _frame_to_jpeg_bytes(frame_bgr, quality=85):
    import cv2
    from PIL import Image
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    out = io.BytesIO()
    image.save(out, format='JPEG', quality=quality)
    return out.getvalue(), image


def _normalize_plate(raw):
    import re
    if not raw:
        return ''
    return re.sub(r'[^A-Z0-9]', '', str(raw).upper())


def _capture_sequential_frames(cap, count):
    frames = []
    for _ in range(count):
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        frames.append(frame)
    return frames


def process_video_upload(upload_id):
    import cv2
    from video_processor.models import VideoUpload, VideoFrame
    from detections.models import Detection
    from detections.ai import is_valid_pk_plate, run_pipeline

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
            raise RuntimeError("Could not open video file: unsupported or corrupt format.")

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
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                frames_ignored += 1
                VideoFrame.objects.create(
                    video_upload=upload, frame_number=idx, timestamp_secs=ts,
                    plate_detected=False, auto_processed=False,
                )
                continue

            primary_bytes, image = _frame_to_jpeg_bytes(frame)
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(primary_bytes)
                tmp_path = tmp.name

            video_frame = VideoFrame(video_upload=upload, frame_number=idx, timestamp_secs=ts)

            try:
                result = {}
                if camera is not None:
                    try:
                        result = run_pipeline(tmp_path, camera)
                    except Exception as ai_err:
                        logger.warning("AI pipeline failed for upload %s frame @%ss: %s",
                                       upload.id, ts, ai_err)
                        result = {}

                plate_text = result.get('plate_text')
                confidence = result.get('confidence')
                side = result.get('side')
                is_violation = bool(result.get('detected_violation'))
                plate_format_ok = bool(plate_text and is_valid_pk_plate(plate_text))

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


                    evidence_meta = [{
                        'slot': 1,
                        'timestamp': round(ts, 3),
                        'plate': plate_text,
                        'side': side,
                        'confidence': round(float(confidence or 0.0), 3),
                        'source': 'primary',
                    }]
                    if video_frame.plate_detected:
                        seq_frames = _capture_sequential_frames(cap, SEQUENTIAL_EVIDENCE_FRAMES)
                        burst_evidence_collected += len(seq_frames)
                        for seq_idx, seq_bgr in enumerate(seq_frames, start=2):
                            seq_bytes, _seq_img = _frame_to_jpeg_bytes(seq_bgr, quality=85)
                            seq_plate, seq_side, seq_conf = None, None, None
                            try:
                                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as seq_tmp:
                                    seq_tmp.write(seq_bytes)
                                    seq_tmp_path = seq_tmp.name
                                try:
                                    seq_result = run_pipeline(seq_tmp_path, camera)
                                    seq_plate = seq_result.get('plate_text')
                                    seq_side = seq_result.get('side')
                                    seq_conf = seq_result.get('confidence')
                                finally:
                                    try:
                                        os.unlink(seq_tmp_path)
                                    except Exception:
                                        pass
                            except Exception as seq_err:
                                logger.debug("sequential frame check failed: %s", seq_err)
                            field = 'evidence_frame_2' if seq_idx == 2 else 'evidence_frame_3'
                            getattr(detection, field).save(
                                f"seq{seq_idx}_{camera.camera_id}_upload{upload.id}_f{idx}.jpg",
                                ContentFile(seq_bytes), save=False,
                            )
                            evidence_meta.append({
                                'slot': seq_idx,
                                'timestamp': round(ts + (seq_idx - 1) / max(fps, 1.0), 3),
                                'plate': seq_plate,
                                'side': seq_side,
                                'confidence': round(float(seq_conf or 0.0), 3),
                                'source': 'sequential',
                            })
                    detection.evidence_frames_meta = evidence_meta


                    raw_resp = detection.ai_raw_response or {}
                    raw_resp['frame_evidence'] = [
                        {'plate': m.get('plate'), 'confidence': m.get('confidence'),
                         'ocr_confidence': m.get('confidence'),
                         'timestamp': str(m.get('timestamp')), 'plate_complete': True,
                         'plate_format_ok': is_valid_pk_plate(m.get('plate') or '')}
                        for m in evidence_meta
                    ]
                    raw_resp['vehicle_class'] = 'car' if (side and (result.get('raw_ai_response', {}) or {}).get('side_confidence', 0) >= 0.60) else 'unknown'
                    raw_resp['plate_complete'] = bool(plate_text)
                    raw_resp['plate_format_ok'] = plate_format_ok
                    detection.ai_raw_response = raw_resp

                    detection.save()
                    try:
                        from detections.pipeline import finalize_detection_from_ai
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
        logger.info("Video upload %s done: %d frames, %d with plates, %d sent to review, %d challans",
                     upload.id, len(timestamps), frames_with_plates, manual_review_created,
                     auto_challans_created)

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
