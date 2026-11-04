from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone

from accounts.decorators import role_required
from realtime.models import LiveFeed, CameraAssignment

from .models import VideoUpload


@role_required('OFFICER', 'IT')
def upload_video(request):
    """Upload a demo/recorded video, link it to a camera, and run the AI
    detection pipeline on it. Detections flow through the secure evidence
    pipeline and become visible on the Live Tracking page for the camera."""
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
        if user.role == 'OFFICER' and not CameraAssignment.objects.filter(
                camera=camera, officer=user, is_active=True).exists():
            messages.error(request, "That camera is not assigned to you.")
            return redirect('video_processor:upload_video')

        from django.db import transaction
        import hashlib
        try:
            digest = hashlib.sha256()
            for chunk in video_file.chunks():
                digest.update(chunk)
            file_sha256 = digest.hexdigest()
            video_file.seek(0)
            with transaction.atomic():
                upload = VideoUpload.objects.create(
                    camera=camera,
                    video_file=video_file,
                    original_filename=getattr(video_file, 'name', 'upload.mp4'),
                    uploaded_by=user,
                    camera_location=camera.location or '',
                    file_sha256=file_sha256,
                )
                LiveFeed.objects.create(
                    title=f"{camera.camera_id} — upload {upload.id}",
                    video_file=upload.video_file,
                    camera=camera,
                    location_label=camera.location,
                    uploaded_by=user,
                    is_active=True,
                )
                camera.health_status = 'online'
                camera.last_frame_at = timezone.now()
                camera.last_health_check = timezone.now()
                camera.save(update_fields=['health_status', 'last_frame_at', 'last_health_check'])
        except Exception as e:
            messages.error(request, f"Failed to save video: {e}")
            return redirect('video_processor:upload_video')

        try:
            from admin.dig_portal.models import AuditLog
            AuditLog.write(
                request, 'upload.video', 'VideoUpload', upload.id,
                filename=upload.original_filename, size_mb=round(video_file.size / 1048576, 2),
                sha256=file_sha256, camera=camera.camera_id,
                location=camera.location or '',
            )
        except Exception:
            pass

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
