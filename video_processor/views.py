from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.core.files.storage import default_storage

from accounts.decorators import officer_or_dig_required, role_required
from detections.models import Detection
from realtime.models import LiveFeed, CameraAssignment

from .models import VideoUpload


@role_required('OFFICER', 'IT')
def upload_video(request):
    """Upload a demo/recorded video, link it to a camera, and run the AI
    detection pipeline on it. Detections land in the officer review queue and
    become visible on the Live Tracking page for the linked camera.

    Scoped to OFFICER + IT — the roles permission.json grants live_tracking to.
    """
    from cameras.models import Camera

    user = request.user
    if user.role == 'OFFICER':
        cameras = list(Camera.objects.filter(
            assignments__officer=user, assignments__is_active=True, is_active=True
        ).order_by('camera_id'))
    else:
        cameras = list(Camera.objects.filter(is_active=True).order_by('camera_id'))

    if request.method == 'POST':
        video_file = request.FILES.get('video_file')
        if not video_file:
            messages.error(request, "Please choose a video file (MP4, AVI or MOV).")
            return redirect('video_processor:upload_video')
        if video_file.size > 200 * 1024 * 1024:
            messages.error(request, "Video exceeds the 200 MB limit.")
            return redirect('video_processor:upload_video')

        camera_id = (request.POST.get('camera_id') or '').strip()
        camera = None
        if camera_id:
            camera = Camera.objects.filter(pk=camera_id, is_active=True).first()
        if camera is None:
            messages.error(request, "Please select the camera this video belongs to — detections need a camera.")
            return redirect('video_processor:upload_video')
        # Officers may only upload for cameras assigned to them
        if user.role == 'OFFICER' and not CameraAssignment.objects.filter(
                camera=camera, officer=user, is_active=True).exists():
            messages.error(request, "That camera is not assigned to you.")
            return redirect('video_processor:upload_video')

        from django.db import transaction
        try:
            with transaction.atomic():
                upload = VideoUpload.objects.create(
                    camera=camera,
                    video_file=video_file,
                    original_filename=getattr(video_file, 'name', 'upload.mp4'),
                    uploaded_by=user,
                    camera_location=camera.location or '',
                )
                # Keep the camera's playable stream in sync so the video also
                # shows up on Live Tracking / Live Monitor.
                LiveFeed.objects.create(
                    title=f"{camera.camera_id} — upload {upload.id}",
                    video_file=upload.video_file,
                    camera=camera,
                    location_label=camera.location,
                    uploaded_by=user,
                    is_active=True,
                )
                # H10 FIX: Do NOT overwrite camera.rtsp_url with the uploaded video path.
                # The RTSP URL is the camera's live stream address and must not be
                # replaced by a one-off upload. Update only health indicators.
                camera.health_status = 'online'
                camera.last_frame_at = timezone.now()
                camera.last_health_check = timezone.now()
                camera.save(update_fields=['health_status',
                                           'last_frame_at', 'last_health_check'])
        except Exception as e:
            messages.error(request, f"Failed to save video: {e}")
            return redirect('video_processor:upload_video')

        from cameras.video_processing import start_processing_async
        start_processing_async(upload.id)
        messages.success(
            request,
            f"Video uploaded and AI processing started for camera {camera.camera_id}. "
            f"Detections will appear in the review queue and on Live Tracking."
        )
        if user.role == 'OFFICER':
            return redirect('officer_portal:live_tracking')
        return redirect('video_processor:upload_list')

    return render(request, 'dashboard/video/upload.html', {
        'cameras': cameras,
        'recent_uploads': VideoUpload.objects.filter(
            uploaded_by=user
        ).select_related('camera')[:10] if user.role != 'OFFICER' else [],
    })


@role_required('IT')
def upload_list(request):
    uploads = VideoUpload.objects.select_related('camera', 'uploaded_by')[:100]
    return render(request, 'dashboard/video/upload_list.html', {'uploads': uploads})


@officer_or_dig_required
def manual_annotation(request, detection_id):
    from challans.models import Challan
    from admin.dig_portal.models import AuditLog, SystemSettings
    import datetime

    detection = get_object_or_404(Detection, pk=detection_id)

    if detection.status != Detection.PENDING:
        messages.info(request, f"This detection has already been {detection.get_status_display()}.")
        return redirect('officer_portal:review_queue')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'confirm':
            plate_text = (request.POST.get('plate_text') or '').strip().upper()
            violation_type = request.POST.get('violation_type', Challan.WRONG_WAY)
            notes = (request.POST.get('notes') or '').strip()

            if not plate_text:
                messages.error(request, "Plate text is required to confirm.")
                return redirect('video_processor:manual_annotation', detection_id=detection.id)

            detection.manual_plate_text = plate_text
            detection.manual_violation_type = violation_type
            detection.is_manually_annotated = True
            detection.review_notes = notes
            detection.reviewed_by = request.user
            detection.reviewed_at = timezone.now()
            detection.status = Detection.CONFIRMED
            detection.save()

            sys_settings = SystemSettings.get()
            plate_series = plate_text[:3].upper()
            ticket_no = Challan.objects.generate_ticket_no(plate_series)

            challan = Challan.objects.create(
                detection=detection,
                ticket_no=ticket_no,
                plate_number=plate_text,
                violation_type=violation_type,
                fine_amount=sys_settings.get_fine(violation_type),
                location='Manual Annotation' if not detection.camera else detection.camera.location,
                ai_confidence=detection.ai_confidence,
                issue_date=datetime.date.today(),
                due_date=datetime.date.today() + datetime.timedelta(days=sys_settings.due_date_days),
                payment_status=Challan.UNPAID,
                created_by=request.user,
            )

            try:
                from challans.pdf_service import generate_challan_pdf
                generate_challan_pdf(challan)
            except Exception:
                pass

            AuditLog.write(request, 'detection.manual_annotate_confirm',
                           'Detection', detection.id,
                           plate=plate_text, violation=violation_type,
                           challan_id=challan.id)

            messages.success(request, f"Detection confirmed — Challan {challan.ticket_no} issued.")
            return redirect('officer_portal:review_queue')

        elif action == 'reject':
            detection.status = Detection.REJECTED
            detection.reviewed_by = request.user
            detection.reviewed_at = timezone.now()
            detection.review_notes = (request.POST.get('notes') or '').strip()
            detection.save()
            AuditLog.write(request, 'detection.manual_annotate_reject',
                           'Detection', detection.id)
            messages.info(request, "Detection rejected.")
            return redirect('officer_portal:review_queue')

    return render(request, 'dashboard/officer/manual_annotation.html', {
        'detection': detection,
    })

