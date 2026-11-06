import datetime
import logging
import re

from django.shortcuts import render, redirect, get_object_or_404, Http404
from django.http import JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count

from accounts.decorators import officer_or_dig_required, role_required
from detections.models import Detection, DetectionReviewNote
from challans.models import Challan
from appeals.models import ChallanAppeal
from admin.dig_portal.models import AuditLog, SystemSettings

log = logging.getLogger('wrongway.officer')


def officer_camera_ids(user):
    """Camera IDs the user may see. Officers are limited to their active
    CameraAssignment rows; senior staff (DIG/SSP/SUPV) see everything."""
    if user.role == 'OFFICER':
        from realtime.models import CameraAssignment
        ids = list(
            CameraAssignment.objects.filter(officer=user, is_active=True)
            .values_list('camera_id', flat=True)
        )
        return ids if ids else [-1]
    return None


def scope_detections(user, qs):
    ids = officer_camera_ids(user)
    if ids is not None:
        qs = qs.filter(camera_id__in=ids)
    return qs


@officer_or_dig_required
def home(request):
    now = timezone.now()
    today = now.date()
    last_7d = now - datetime.timedelta(days=7)

    queue_qs = scope_detections(request.user, Detection.objects.filter(status=Detection.PENDING))
    queue_count = queue_qs.count()
    flagged_count = scope_detections(
        request.user, Detection.objects.filter(status=Detection.FLAGGED)).count()
    confirmed_total = Detection.objects.filter(
        status=Detection.CONFIRMED, reviewed_by=request.user).count()
    rejected_total = Detection.objects.filter(
        status=Detection.REJECTED, reviewed_by=request.user).count()

    my_challans_total = Challan.objects.filter(created_by=request.user).count()
    my_challans_unpaid = Challan.objects.filter(
        created_by=request.user, payment_status='UNPAID').count()
    my_challans_paid = Challan.objects.filter(
        created_by=request.user, payment_status='PAID').count()
    my_appeals = ChallanAppeal.objects.filter(
        Q(challan__created_by=request.user) | Q(reviewed_by=request.user)).count()

    days_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_start = datetime.datetime.combine(day, datetime.time.min).replace(tzinfo=timezone.get_current_timezone())
        day_end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time.min).replace(tzinfo=timezone.get_current_timezone())
        reviewed = Detection.objects.filter(
            reviewed_by=request.user,
            reviewed_at__gte=day_start,
            reviewed_at__lt=day_end,
        ).count()
        days_data.append({'label': day.strftime('%a'), 'count': reviewed})

    violation_dist = (
        scope_detections(request.user, Detection.objects.filter(reviewed_by=request.user))
        .values('ai_detected_violation')
        .annotate(c=Count('id'))
        .order_by('-c')[:8]
    )
    violation_labels = ['Wrong Way' if v['ai_detected_violation'] else 'No Violation' for v in violation_dist]
    violation_counts = [v['c'] for v in violation_dist]

    recent = list(
        scope_detections(request.user, Detection.objects.filter(status=Detection.PENDING))
        .select_related('camera')
        .order_by('-created_at')[:12]
    )

    top_cameras = (
        Detection.objects.filter(reviewed_by=request.user)
        .values('camera__camera_id', 'camera__location')
        .annotate(c=Count('id'))
        .order_by('-c')[:5]
    )

    week_confirmed = Detection.objects.filter(
        status=Detection.CONFIRMED, reviewed_by=request.user, reviewed_at__gte=last_7d).count()
    week_rejected = Detection.objects.filter(
        status=Detection.REJECTED, reviewed_by=request.user, reviewed_at__gte=last_7d).count()
    week_flagged = Detection.objects.filter(
        status=Detection.FLAGGED, reviewed_by=request.user, reviewed_at__gte=last_7d).count()

    return render(request, 'dashboard/officer/dashboard.html', {
        'queue_count': queue_count,
        'flagged_count': flagged_count,
        'confirmed_total': confirmed_total,
        'rejected_total': rejected_total,
        'my_challans_total': my_challans_total,
        'my_challans_unpaid': my_challans_unpaid,
        'my_challans_paid': my_challans_paid,
        'my_appeals': my_appeals,
        'week_confirmed': week_confirmed,
        'week_rejected': week_rejected,
        'week_flagged': week_flagged,
        'recent_detections': recent,
        'detections': recent,
        'days_data': days_data,
        'violation_labels': violation_labels,
        'violation_counts': violation_counts,
        'top_cameras': top_cameras,
    })


@officer_or_dig_required
def dashboard(request):
    return home(request)


@officer_or_dig_required
def review_queue(request):
    qs = scope_detections(request.user, Detection.objects.filter(status=Detection.PENDING)).order_by('created_at')
    selected_id = request.GET.get('detection_id') or request.GET.get('id')
    try:
        selected_id = int(selected_id) if selected_id else None
    except (TypeError, ValueError):
        selected_id = None
    selected = qs.filter(pk=selected_id).first() if selected_id else None
    if not selected and qs.exists():
        selected = qs.first()
    try:
        from detections.ai import get_model_info
        model_info = get_model_info()
    except Exception:
        model_info = {}
    return render(request, 'dashboard/officer/review_queue.html', {
        'detections': qs[:50], 'selected': selected, 'queue_count': qs.count(),
        'model_info': model_info,
        'ai_threshold': SystemSettings.get().ai_confidence_threshold,
    })


@officer_or_dig_required
def detection_detail(request, detection_id):
    detection = get_object_or_404(Detection, pk=detection_id)
    # Officer IDOR guard: officers may only open detections from their
    # assigned cameras (senior staff see everything).
    if request.user.role == 'OFFICER':
        allowed = officer_camera_ids(request.user)
        if detection.camera_id is not None and detection.camera_id not in allowed:
            raise Http404('Detection not found for your assigned cameras.')
    notes = detection.review_notes_list.all() if hasattr(detection, 'review_notes_list') else []
    ctx = {'detection': detection, 'notes': notes}
    if request.headers.get('HX-Request') or request.GET.get('partial'):
        return render(request, 'dashboard/officer/_detection_detail.html', ctx)
    return render(request, 'dashboard/officer/detection_detail.html', ctx)


def _do_review_action(request, detection_id, action):
    if action not in ('reject', 'flag'):
        raise Http404
    detection = get_object_or_404(Detection, pk=detection_id)
    notes = (request.POST.get('notes') or '').strip()
    if len(notes) < 20:
        messages.error(request, f"Notes are required (min 20 chars) for {action} action.")
        return redirect('officer_portal:review_queue')

    before = {'status': detection.status, 'plate': detection.effective_plate}
    from django.db import transaction
    with transaction.atomic():
        detection.reviewed_by = request.user
        detection.reviewed_at = timezone.now()
        detection.review_notes = notes
        if action == 'reject':
            detection.status = Detection.REJECTED
        elif action == 'flag':
            detection.status = Detection.FLAGGED
        detection.save()
        AuditLog.write(request, f'detection.{action}', 'Detection', detection.id,
                       before=before, after={'status': detection.status}, notes=notes)
        if action == 'reject':
            messages.success(request, "Detection rejected as false positive. Audit log updated.")
        else:
            messages.success(request, "Detection flagged for DIG escalation.")
    return redirect('officer_portal:review_queue')


@officer_or_dig_required
def reject_detection(request, detection_id):
    if request.method != 'POST':
        raise Http404
    return _do_review_action(request, detection_id, 'reject')


@officer_or_dig_required
def flag_detection(request, detection_id):
    if request.method != 'POST':
        raise Http404
    return _do_review_action(request, detection_id, 'flag')


@officer_or_dig_required
def add_review_note(request, detection_id):
    detection = get_object_or_404(Detection, pk=detection_id)
    if request.method == 'POST':
        note_text = (request.POST.get('note') or '').strip()
        if len(note_text) < 5:
            messages.error(request, "Note must be at least 5 characters.")
        else:
            DetectionReviewNote.objects.create(detection=detection, author=request.user, note=note_text)
            AuditLog.write(request, 'detection.note_add', 'Detection', detection.id, note=note_text[:80])
            messages.success(request, "Internal note added.")
    return redirect(reverse('officer_portal:review_queue') + f'?detection_id={detection_id}')


@officer_or_dig_required
def camera_feed(request):
    recent = scope_detections(
        request.user, Detection.objects.filter(status=Detection.PENDING)
    ).order_by('-created_at')[:24]
    return render(request, 'dashboard/officer/camera_feed.html', {'recent': recent})


@officer_or_dig_required
def detections_list(request):
    qs = scope_detections(request.user, Detection.objects.select_related('camera')).order_by('-created_at')
    plate_q = (request.GET.get('plate') or '').strip().upper()
    status_q = (request.GET.get('status') or '').strip()
    if plate_q:
        qs = qs.filter(ai_plate_text__icontains=plate_q)
    if status_q:
        qs = qs.filter(status=status_q)
    return render(request, 'dashboard/officer/detections_list.html', {
        'detections': qs[:100],
        'plate_q': plate_q,
        'status_q': status_q,
        'status_choices': getattr(Detection, 'STATUS_CHOICES', ()),
    })


@officer_or_dig_required
def flagged_list(request):
    qs = scope_detections(
        request.user, Detection.objects.filter(status=Detection.FLAGGED)
    ).select_related('camera').order_by('-created_at')[:100]
    return render(request, 'dashboard/officer/flagged_list.html', {'detections': qs})


@officer_or_dig_required
def challans_list(request):
    challans = Challan.objects.select_related('camera').order_by('-created_at')[:100]
    return render(request, 'dashboard/officer/challans_list.html', {'challans': challans})


@officer_or_dig_required
def review_history(request):
    qs = Detection.objects.filter(reviewed_by=request.user).order_by('-reviewed_at')
    plate_q = request.GET.get('plate')
    if plate_q:
        qs = qs.filter(ai_plate_text__icontains=plate_q)
    date_from = request.GET.get('date_from')
    if date_from:
        qs = qs.filter(reviewed_at__date__gte=date_from)
    date_to = request.GET.get('date_to')
    if date_to:
        qs = qs.filter(reviewed_at__date__lte=date_to)
    return render(request, 'dashboard/officer/review_history.html', {
        'actions': qs[:100], 'plate_q': plate_q, 'date_from': date_from, 'date_to': date_to,
    })


def lookup_owner_by_plate(plate_number):
    """Resolve plate to owner via local registration then the Excise registry."""
    logger = logging.getLogger('wrongway.excise')
    plate = (plate_number or '').strip().upper()
    if not plate or plate == 'UNKNOWN':
        return {
            'integration_status': 'no_plate',
            'integration_message': 'No plate number available for registry lookup.',
        }

    plate_compact = re.sub(r'[^A-Z0-9]', '', plate)

    try:
        from accounts.models import VehicleRegistration
        reg = (VehicleRegistration.objects
               .filter(Q(plate_number__iexact=plate) | Q(plate_number__iexact=plate_compact))
               .select_related('owner')
               .first())
        if reg:
            owner = getattr(reg, 'owner', None)
            data = {
                'owner_name': (getattr(owner, 'get_full_name', lambda: '')() or
                               getattr(owner, 'display_name', None) or
                               getattr(owner, 'first_name', None)),
                'cnic': getattr(owner, 'cnic', None),
                'address': None,
                'phone': getattr(owner, 'phone', None),
                'vehicle_type': getattr(reg, 'vehicle_type', None) or 'car',
                'make_year': getattr(reg, 'year', None),
                'color': getattr(reg, 'color', None),
                'chassis_no': None,
                'source': 'local_registration',
                'integration_status': 'ok_local',
            }
            if data.get('cnic'):
                try:
                    from integrations.nadra import verify_cnic
                    data['nadra'] = verify_cnic(data['cnic'], expected_name=data.get('owner_name'))
                except Exception:
                    pass
            return data
    except Exception as e:
        logger.debug('VehicleRegistration lookup skipped: %s', e)

    try:
        from integrations.excise import lookup_by_plate
        from integrations.mode import is_real
        from admin.dig_portal.models import SystemSettings
        sys_settings = SystemSettings.get()
        has_excise = bool((getattr(sys_settings, 'excise_api_url', None) or '').strip() and
                          (getattr(sys_settings, 'excise_api_key', None) or '').strip())

        data = lookup_by_plate(plate) or {}
        if data and data.get('owner_name'):
            data['integration_status'] = 'ok_excise'
            if data.get('cnic'):
                try:
                    from integrations.nadra import verify_cnic
                    data['nadra'] = verify_cnic(data['cnic'], expected_name=data.get('owner_name'))
                except Exception:
                    pass
            return data

        if is_real() and not has_excise:
            return {
                'integration_status': 'need_integration',
                'integration_message': 'Need NADRA / Excise system integration - configure API URL and key in IT → System Settings → Integrations, then set mode to Real.',
            }
        if is_real() and has_excise:
            return {
                'integration_status': 'not_found',
                'integration_message': 'Plate not found in Excise registry.',
            }
        return {
            'integration_status': 'need_integration',
            'integration_message': 'Need NADRA / Excise system integration - real person/plate identity requires live registry APIs (currently in Demo mode).',
        }
    except Exception as e:
        logger.warning('Excise integration failed: %s', e)
        return {
            'integration_status': 'need_integration',
            'integration_message': 'Need NADRA / Excise system integration - lookup failed.',
        }


@officer_or_dig_required
def appeal_list(request):
    appeals = ChallanAppeal.objects.filter(
        status=ChallanAppeal.PENDING,
    ).order_by('created_at')
    return render(request, 'dashboard/officer/appeal_list.html', {
        'appeals': appeals,
        'read_only': True,
        'info_message': 'Citizen appeals go directly to SSP. Officers do not approve or reject appeals.',
    })


@officer_or_dig_required
def appeal_detail(request, appeal_id):
    appeal = get_object_or_404(ChallanAppeal, pk=appeal_id)
    messages.info(request, "Officers cannot approve/reject appeals. Only SSP can make appeal decisions.")
    return render(request, 'dashboard/officer/appeal_detail.html', {'appeal': appeal, 'read_only': True})


@officer_or_dig_required
def performance(request):
    user = request.user
    today = timezone.localdate()
    week_ago = today - datetime.timedelta(days=7)
    my_actions = Detection.objects.filter(reviewed_by=user)
    my_appeals = ChallanAppeal.objects.filter(reviewed_by=user)
    reviewed = my_actions.exclude(reviewed_at__isnull=True)
    avg_review_hrs = 0
    if reviewed.exists():
        deltas = []
        for d in reviewed:
            if d.reviewed_at and d.created_at:
                deltas.append((d.reviewed_at - d.created_at).total_seconds() / 3600)
        if deltas:
            avg_review_hrs = round(sum(deltas) / len(deltas), 1)
    return render(request, 'dashboard/officer/performance.html', {
        'today_count': my_actions.filter(reviewed_at__date=today).count(),
        'week_count': my_actions.filter(reviewed_at__date__gte=week_ago).count(),
        'pending_count': Detection.objects.filter(status=Detection.PENDING).count(),
        'appeals_handled': my_appeals.count(),
        'avg_review_hrs': avg_review_hrs,
        'recent_actions': my_actions.order_by('-reviewed_at')[:10],
    })


@role_required('OFFICER')
def live_tracking(request):
    """Officer Live Tracking - camera-scoped to this officer's active
    CameraAssignment rows only. Uses LiveTrackingService for consistent data."""
    from admin.shared import LiveTrackingService

    service = LiveTrackingService(
        user=request.user,
        selected_camera_id=request.GET.get('camera_id') or '',
        plate_query=request.GET.get('plate') or '',
        status_filter=request.GET.get('status') or '',
        limit=100,
    )

    cameras = service.get_available_cameras()
    if not service.selected_camera_id and cameras:
        service.selected_camera_id = str(cameras[0].id)
    recent = service.get_recent_detections()

    focus_id = request.GET.get('focus')
    latest_detection = None
    if focus_id:
        latest_detection = Detection.objects.filter(
            pk=focus_id
        ).select_related('camera').first()
    if latest_detection is None and recent:
        latest_detection = recent[0]

    stats = service.get_stats(recent)

    from realtime.models import LiveFeed
    live_feeds = list(
        LiveFeed.objects.filter(is_active=True, camera_id__in=[c.id for c in cameras])
        .select_related('camera').order_by('-created_at')[:12]
    ) if cameras else []
    service.enforce_officer_one_camera()
    return render(request, 'dashboard/shared/live_tracking.html', {
        'cameras': cameras,
        'has_assignment': bool(cameras),
        'selected_camera': service.camera,
        'stream_url': service.resolve_stream_url(),
        'selected_camera_id': service.selected_camera_id or '',
        'camera_not_found': service.camera_not_found,
        'plate_q': service.plate_query,
        'status_q': service.status_filter,
        'recent_detections': recent,
        'latest_detection': latest_detection,
        'live_feeds': live_feeds,
        'stat_total': stats['total'],
        'stat_violations': stats['violations'],
        'stat_pending': stats['pending'],
        'stat_unique_plates': stats['unique_plates'],
        'stat_avg_conf': stats['avg_confidence'],
        'status_choices': getattr(Detection, 'STATUS_CHOICES', ()),
    })


@role_required('OFFICER')
def vehicle_tracking(request):
    plate = (request.GET.get('plate') or '').strip().upper()
    detections = []
    challans = []
    if plate:
        detections = list(
            scope_detections(request.user, Detection.objects.all())
            .filter(ai_plate_text__icontains=plate)
            .order_by('-created_at')[:50]
        )
        challans = list(Challan.objects.filter(plate_number__icontains=plate).order_by('-issue_date')[:20])
    return render(request, 'dashboard/officer/vehicle_tracking.html', {
        'plate': plate,
        'detections': detections,
        'challans': challans,
    })


@role_required('OFFICER', 'IT')
def frame_timeline(request):
    """JSON feed for officer Live Tracking trail - camera-assignment scoped."""
    from admin.shared import LiveTrackingService

    service = LiveTrackingService(
        user=request.user,
        selected_camera_id=request.GET.get('camera_id') or '',
        plate_query=request.GET.get('plate') or '',
        limit=60,
    )
    detections = service.get_recent_detections()

    camera_id = request.GET.get('camera_id')
    if camera_id and service.camera_not_found:
        return JsonResponse({'items': [], 'camera_not_found': True})

    items = service.serialize_detections(detections)
    return JsonResponse({
        'items': items,
        'count': len(items),
        'camera_not_found': service.camera_not_found,
    })


@officer_or_dig_required
def officer_profile(request):
    user = request.user
    if request.method == 'POST':
        user.phone = request.POST.get('phone', user.phone) or user.phone
        if hasattr(user, 'department'):
            user.department = request.POST.get('department', user.department) or user.department
        user.save()
        messages.success(request, 'Profile updated.')
        return redirect('officer_portal:profile')
    return render(request, 'dashboard/officer/profile.html', {'profile_user': user})
