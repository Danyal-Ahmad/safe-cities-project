import datetime
import logging

from django.shortcuts import render, redirect, get_object_or_404, Http404
from django.http import JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from accounts.decorators import officer_or_dig_required, role_required
from detections.models import Detection, DetectionReviewNote, Annotation
from challans.models import Challan
from appeals.models import ChallanAppeal
from cameras.models import Camera
from admin.dig_portal.models import AuditLog, SystemSettings

log = logging.getLogger('wrongway.officer')


@officer_or_dig_required
def home(request):
    """Officer landing dashboard with rich KPIs and charts."""
    now = timezone.now()
    today = now.date()
    last_7d = now - datetime.timedelta(days=7)
    last_30d = now - datetime.timedelta(days=30)

    # Queue & status counts
    queue_count = Detection.objects.filter(status=Detection.PENDING).count()
    flagged_count = Detection.objects.filter(status=Detection.FLAGGED).count()
    confirmed_total = Detection.objects.filter(
        status=Detection.CONFIRMED, reviewed_by=request.user
    ).count()
    rejected_total = Detection.objects.filter(
        status=Detection.REJECTED, reviewed_by=request.user
    ).count()

    # My challans issued
    my_challans_total = Challan.objects.filter(created_by=request.user).count()
    my_challans_unpaid = Challan.objects.filter(
        created_by=request.user, payment_status='UNPAID'
    ).count()
    my_challans_paid = Challan.objects.filter(
        created_by=request.user, payment_status='PAID'
    ).count()

    # Appeals
    my_appeals = ChallanAppeal.objects.filter(
        Q(challan__created_by=request.user) | Q(reviewed_by=request.user)
    ).count()

    # 7-day review trend (day-by-day)
    days_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_start = datetime.datetime.combine(day, datetime.time.min).replace(tzinfo=datetime.timezone.utc)
        day_end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time.min).replace(tzinfo=datetime.timezone.utc)
        reviewed = Detection.objects.filter(
            reviewed_by=request.user,
            reviewed_at__gte=day_start,
            reviewed_at__lt=day_end,
        ).count()
        days_data.append({
            'label': day.strftime('%a'),
            'count': reviewed,
        })

    # Violation type breakdown for this officer
    from django.db.models import Count
    violation_dist = (
        Detection.objects.filter(reviewed_by=request.user)
        .values('manual_violation_type')
        .annotate(c=Count('id'))
        .order_by('-c')[:8]
    )
    violation_labels = [(v['manual_violation_type'] or 'wrong_way').replace('_', ' ').title() for v in violation_dist]
    violation_counts = [v['c'] for v in violation_dist]

    # Recent detections queue
    recent = list(
        Detection.objects.filter(status=Detection.PENDING)
        .select_related('camera')
        .order_by('-created_at')[:12]
    )

    # Top cameras for this officer
    top_cameras = (
        Detection.objects.filter(reviewed_by=request.user)
        .values('camera__camera_id', 'camera__location')
        .annotate(c=Count('id'))
        .order_by('-c')[:5]
    )

    # This week performance
    week_confirmed = Detection.objects.filter(
        status=Detection.CONFIRMED, reviewed_by=request.user, reviewed_at__gte=last_7d
    ).count()
    week_rejected = Detection.objects.filter(
        status=Detection.REJECTED, reviewed_by=request.user, reviewed_at__gte=last_7d
    ).count()
    week_flagged = Detection.objects.filter(
        status=Detection.FLAGGED, reviewed_by=request.user, reviewed_at__gte=last_7d
    ).count()

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
    qs = Detection.objects.filter(status=Detection.PENDING).order_by('created_at')
    selected_id = request.GET.get('detection_id') or request.GET.get('id')
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
    notes = detection.review_notes_list.all() if hasattr(detection, 'review_notes_list') else []
    ctx = {'detection': detection, 'notes': notes}
    if request.headers.get('HX-Request') or request.GET.get('partial'):
        return render(request, 'dashboard/officer/_detection_detail.html', ctx)
    return render(request, 'dashboard/officer/detection_detail.html', ctx)


def _do_review_action(request, detection_id, action):
    detection = get_object_or_404(Detection, pk=detection_id)
    notes = (request.POST.get('notes') or '').strip()
    manual_plate = (request.POST.get('manual_plate_text') or '').strip().upper()
    manual_violation = (request.POST.get('manual_violation_type') or request.POST.get('violation_type') or 'wrong_way').strip()
    manual_violation = 'wrong_way'
    if action in ('reject', 'flag') and len(notes) < 20:
        messages.error(request, f"Notes are required (min 20 chars) for {action} action.")
        return redirect('officer_portal:review_queue')

    if action == 'confirm' and not (manual_plate or detection.effective_plate):
        messages.error(
            request,
            "Cannot confirm: no plate number. Enter a plate (AI or manual) before confirming."
        )
        return redirect('officer_portal:review_queue')

    before = {'status': detection.status, 'plate': detection.effective_plate}
    from django.db import transaction
    with transaction.atomic():
        detection.reviewed_by = request.user
        detection.reviewed_at = timezone.now()
        detection.review_notes = notes
        if manual_plate:
            detection.manual_plate_text = manual_plate
            detection.is_manually_annotated = True
        if manual_violation:
            detection.manual_violation_type = manual_violation
        if action == 'confirm':
            detection.status = Detection.CONFIRMED
        elif action == 'reject':
            detection.status = Detection.REJECTED
        elif action == 'flag':
            detection.status = Detection.FLAGGED
        detection.save()

        if action == 'confirm':
            challan = _create_challan_from_detection(detection, request.user)
            AuditLog.write(request, 'detection.confirm', 'Detection', detection.id,
                           before=before, after={'status': detection.status},
                           challan=challan.ticket_no, notes=notes)
            messages.success(request, f"Detection confirmed. Challan {challan.ticket_no} created (PKR {challan.fine_amount}).")
        elif action == 'reject':
            AuditLog.write(request, 'detection.reject', 'Detection', detection.id,
                           before=before, after={'status': detection.status}, notes=notes)
            messages.success(request, "Detection rejected as false positive. Audit log updated.")
        elif action == 'flag':
            AuditLog.write(request, 'detection.flag', 'Detection', detection.id,
                           before=before, after={'status': detection.status}, notes=notes)
            messages.success(request, "Detection flagged for DIG escalation.")
    return redirect('officer_portal:review_queue')


@officer_or_dig_required
def confirm_detection(request, detection_id):
    if request.method != 'POST':
        raise Http404
    return _do_review_action(request, detection_id, 'confirm')


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
    recent = Detection.objects.filter(status=Detection.PENDING).order_by('-created_at')[:24]
    return render(request, 'dashboard/officer/camera_feed.html', {'recent': recent})


@officer_or_dig_required
def detections_list(request):
    """Officer's read-only detections browse page (permission: view_detections)."""
    qs = Detection.objects.select_related('camera').order_by('-created_at')
    plate_q = (request.GET.get('plate') or '').strip().upper()
    status_q = (request.GET.get('status') or '').strip()
    if plate_q:
        qs = qs.filter(Q(ai_plate_text__icontains=plate_q) | Q(manual_plate_text__icontains=plate_q))
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
    """Officer's flagged detections page (permission: view_flagged_detections)."""
    qs = Detection.objects.filter(status=Detection.FLAGGED).select_related('camera').order_by('-created_at')[:100]
    return render(request, 'dashboard/officer/flagged_list.html', {'detections': qs})


@officer_or_dig_required
def challans_list(request):
    """Officer's read-only challan register (permission: view_challans).

    Officers can see challans but get no management actions (edit fine,
    mark paid, delete) — those stay with DIG/IT per permission.json.
    """
    challans = Challan.objects.select_related('camera').order_by('-created_at')[:100]
    return render(request, 'dashboard/officer/challans_list.html', {'challans': challans})


@officer_or_dig_required
def review_history(request):
    qs = Detection.objects.filter(reviewed_by=request.user).order_by('-reviewed_at')
    plate_q = request.GET.get('plate')
    if plate_q:
        qs = qs.filter(Q(ai_plate_text__icontains=plate_q) | Q(manual_plate_text__icontains=plate_q))
    date_from = request.GET.get('date_from')
    if date_from:
        qs = qs.filter(reviewed_at__date__gte=date_from)
    date_to = request.GET.get('date_to')
    if date_to:
        qs = qs.filter(reviewed_at__date__lte=date_to)
    return render(request, 'dashboard/officer/review_history.html', {
        'actions': qs[:100], 'plate_q': plate_q, 'date_from': date_from, 'date_to': date_to,
    })


@officer_or_dig_required
def add_manual_challan(request):
    if request.method == 'POST':
        plate_number = (request.POST.get('plate_number') or '').strip().upper()
        if not plate_number:
            messages.error(request, "Plate number is required to issue a manual challan.")
            return redirect('officer_portal:live_tracking')
        sys_settings = SystemSettings.get()
        plate_series = (plate_number[:3] or 'LRN').upper()
        ticket_no = Challan.objects.generate_ticket_no(plate_series)
        violation = 'wrong_way'
        try:
            due_days = int(request.POST.get('due_days') or sys_settings.due_date_days)
        except ValueError:
            due_days = sys_settings.due_date_days
        from django.db import transaction
        try:
            with transaction.atomic():
                challan = Challan.objects.create(
                    ticket_no=ticket_no,
                    plate_number=plate_number,
                    province=request.POST.get('province') or None,
                    owner_name=request.POST.get('owner_name') or None,
                    cnic=request.POST.get('cnic') or None,
                    address=request.POST.get('address') or None,
                    phone=request.POST.get('phone') or None,
                    vehicle_type=request.POST.get('vehicle_type') or None,
                    make_year=request.POST.get('make_year') or None,
                    color=request.POST.get('color') or None,
                    violation_type=violation,
                    fine_amount=sys_settings.get_fine(violation),
                    location=request.POST.get('location') or None,
                    issue_date=datetime.date.today(),
                    due_date=datetime.date.today() + datetime.timedelta(days=due_days),
                    payment_status=Challan.UNPAID,
                    created_by=request.user,
                )
                AuditLog.write(request, 'challan.manual_create', 'Challan', challan.id, ticket_no=challan.ticket_no)
        except Exception as e:
            log.error("Manual challan creation failed: %s", e)
            messages.error(request, f"Failed to create challan: {e}")
            return redirect('officer_portal:review_queue')
        try:
            from challans.pdf_service import generate_challan_pdf
            generate_challan_pdf(challan)
        except Exception as e:
            log.warning("PDF gen deferred: %s", e)
        proof = request.FILES.get('proof_image') or request.FILES.get('evidence')
        camera_id = request.POST.get('camera_id')
        if proof:
            try:
                from detections.models import Detection
                from cameras.models import Camera
                cam = None
                if camera_id:
                    cam = Camera.objects.filter(pk=camera_id).first()
                det = Detection(
                    camera=cam,
                    ai_plate_text=plate_number,
                    status=Detection.CONFIRMED,
                    is_manually_annotated=True,
                    reviewed_by=request.user,
                    manual_plate_text=plate_number,
                    manual_violation_type=violation,
                    review_notes=(request.POST.get('notes') or 'Manual issue from live tracking').strip(),
                )
                det.raw_image.save(
                    f"manual_{challan.ticket_no}_{proof.name}",
                    proof,
                    save=False,
                )
                det.save()
                challan.detection = det
                challan.save(update_fields=['detection'])
            except Exception as e:
                log.warning("Proof attach failed for %s: %s", challan.ticket_no, e)

        messages.success(request, f"Manual challan {challan.ticket_no} created.")
        return redirect('officer_portal:live_tracking')
    return redirect('officer_portal:live_tracking')


def _create_challan_from_detection(detection, user):
    from django.db import transaction
    sys_settings = SystemSettings.get()
    plate_series = (detection.effective_plate or 'LRN')[:3].upper()
    ticket_no = Challan.objects.generate_ticket_no(plate_series)
    violation_type = detection.effective_violation_type or Challan.WRONG_WAY
    owner_data = lookup_owner_by_plate(detection.effective_plate) if detection.effective_plate else {}
    with transaction.atomic():
        challan = Challan.objects.create(
            detection=detection, ticket_no=ticket_no,
            plate_number=detection.effective_plate or 'UNKNOWN',
            province=detection.ai_province,
            owner_name=owner_data.get('owner_name'),
            cnic=owner_data.get('cnic'),
            address=owner_data.get('address'),
            phone=owner_data.get('phone'),
            vehicle_type=owner_data.get('vehicle_type'),
            make_year=owner_data.get('make_year'),
            color=owner_data.get('color'),
            chassis_no=owner_data.get('chassis_no'),
            violation_type=violation_type,
            fine_amount=sys_settings.get_fine(violation_type),
            location=detection.camera.location if detection.camera else 'Unknown',
            camera=detection.camera,
            ai_confidence=detection.ai_confidence,
            moving_direction=detection.camera.legal_direction if detection.camera else None,
            legal_direction=detection.camera.legal_direction if detection.camera else None,
            issue_date=datetime.date.today(),
            due_date=datetime.date.today() + datetime.timedelta(days=sys_settings.due_date_days),
            payment_status=Challan.UNPAID,
            created_by=user,
        )
    try:
        from challans.pdf_service import generate_challan_pdf
        generate_challan_pdf(challan)
    except Exception as e:
        log.warning("PDF gen deferred: %s", e)
    try:
        from challans.email_service import send_challan_notification
        send_challan_notification(challan)
    except Exception as e:
        log.warning("Email skipped: %s", e)
    try:
        from admin.dig_portal.views import run_auto_blacklist
        run_auto_blacklist(challan.plate_number, request=None)
    except Exception as e:
        log.warning("Auto-blacklist skipped: %s", e)
    return challan


def lookup_owner_by_plate(plate_number):
    """Resolve plate → owner. Returns dict; may include integration_status for UI."""
    import logging
    import re as _re
    logger = logging.getLogger('wrongway.excise')
    plate = (plate_number or '').strip().upper()
    if not plate or plate == 'UNKNOWN':
        return {
            'integration_status': 'no_plate',
            'integration_message': 'No plate number available for registry lookup.',
        }

    plate_compact = _re.sub(r'[^A-Z0-9]', '', plate)

    # Local DB first (seeded / enrolled citizens)
    try:
        from accounts.models import VehicleRegistration
        from django.db.models import Q
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
                    nv = verify_cnic(data['cnic'], expected_name=data.get('owner_name'))
                    data['nadra'] = nv
                except Exception:
                    pass
            return data
    except Exception as e:
        logger.debug('VehicleRegistration lookup skipped: %s', e)

    # External Excise (+ optional NADRA)
    try:
        from integrations.excise import lookup_by_plate
        from integrations.mode import is_real, is_demo
        from admin.dig_portal.models import SystemSettings
        sys = SystemSettings.get()
        has_excise = bool((getattr(sys, 'excise_api_url', None) or '').strip() and
                          (getattr(sys, 'excise_api_key', None) or '').strip())

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
                'integration_message': 'Need NADRA / Excise system integration — configure API URL and key in IT → System Settings → Integrations, then set mode to Real.',
            }
        if is_real() and has_excise:
            return {
                'integration_status': 'not_found',
                'integration_message': 'Plate not found in Excise registry.',
            }
        # demo mode, plate not in sandbox
        return {
            'integration_status': 'need_integration',
            'integration_message': 'Need NADRA / Excise system integration — real person/plate identity requires live registry APIs (currently in Demo mode).',
        }
    except Exception as e:
        logger.warning('Excise integration failed: %s', e)
        return {
            'integration_status': 'need_integration',
            'integration_message': 'Need NADRA / Excise system integration — lookup failed.',
        }


@officer_or_dig_required
def appeal_list(request):
    # Citizen appeals are routed directly to SSP — officers do not decide appeals.
    appeals = ChallanAppeal.objects.filter(
        status=ChallanAppeal.PENDING,
        current_stage=ChallanAppeal.STAGE_OFFICER,
    ).order_by('created_at')
    return render(request, 'dashboard/officer/appeal_list.html', {
        'appeals': appeals,
        'read_only': True,
        'info_message': 'Citizen appeals go directly to SSP. Officers do not approve or reject appeals.',
    })


@officer_or_dig_required
def appeal_detail(request, appeal_id):
    appeal = get_object_or_404(ChallanAppeal, pk=appeal_id)
    messages.info(request, "Officers cannot approve/reject appeals. Only SSP can make appeal decisions. Use /auth/admin/login/ if you are SSP.")
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
        'today_count':     my_actions.filter(reviewed_at__date=today).count(),
        'week_count':      my_actions.filter(reviewed_at__date__gte=week_ago).count(),
        'pending_count':   Detection.objects.filter(status=Detection.PENDING).count(),
        'appeals_handled': my_appeals.count(),
        'avg_review_hrs':  avg_review_hrs,
        'recent_actions':  my_actions.order_by('-reviewed_at')[:10],
    })


@role_required('OFFICER')
def live_tracking(request):
    """Officer's Live Tracking view — camera-scoped to this officer's active
    CameraAssignment rows only. Uses LiveTrackingService for consistent data.

    Security: officer with zero active assignments sees zero cameras/detections.
    """
    from admin.shared import LiveTrackingService
    from detections.models import Annotation

    service = LiveTrackingService(
        user=request.user,
        selected_camera_id=request.GET.get('camera_id') or '',
        plate_query=request.GET.get('plate') or '',
        status_filter=request.GET.get('status') or '',
        limit=100,
    )

    cameras = service.get_available_cameras()
    # Auto-select the officer's (single) assigned camera so the feed and
    # stream resolve without requiring a manual camera_id GET param.
    if not service.selected_camera_id and cameras:
        service.selected_camera_id = str(cameras[0].id)
    recent = service.get_recent_detections()

    # Handle focus parameter (direct link to specific detection)
    focus_id = request.GET.get('focus')
    latest_detection = None
    existing_annotations = []
    if focus_id:
        latest_detection = Detection.objects.filter(
            pk=focus_id
        ).select_related('camera').first()
    if latest_detection is None and recent:
        latest_detection = recent[0]

    if latest_detection:
        try:
            existing_annotations = list(
                Annotation.objects.filter(detection=latest_detection).order_by('created_at')
            )
        except Exception:
            existing_annotations = []

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
        'existing_annotations': existing_annotations,
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
        detections = list(Detection.objects.filter(
            Q(ai_plate_text__icontains=plate) | Q(manual_plate_text__icontains=plate)
        ).order_by('-created_at')[:50])
        challans = list(Challan.objects.filter(plate_number__icontains=plate).order_by('-issue_date')[:20])
    return render(request, 'dashboard/officer/vehicle_tracking.html', {
        'plate': plate,
        'detections': detections,
        'challans': challans,
    })


@role_required('OFFICER', 'IT')
def frame_timeline(request):
    """JSON feed for officer's Live Tracking trail — camera-assignment scoped.

    Uses LiveTrackingService for consistent data serialization.
    """
    from django.http import JsonResponse
    from admin.shared import LiveTrackingService

    service = LiveTrackingService(
        user=request.user,
        selected_camera_id=request.GET.get('camera_id') or '',
        plate_query=request.GET.get('plate') or '',
        limit=60,
    )

    detections = service.get_recent_detections()

    # Check camera assignment (LiveTrackingService already filters, but verify)
    camera_id = request.GET.get('camera_id')
    if camera_id and service.camera_not_found:
        return JsonResponse({'items': [], 'camera_not_found': True})

    items = service.serialize_detections(detections)

    return JsonResponse({
        'items': items,
        'count': len(items),
        'camera_not_found': service.camera_not_found,
    })


@role_required('IT', 'OFFICER')
def ai_assist_frame(request):
    """
    Run the existing ONNX pipeline (plate detector + car-side classifier)
    on a frame the officer is about to manually annotate, so the modal can
    pre-fill a plate bbox / side / suggested violation instead of the
    officer typing everything blind. Officer can still edit/override
    anything before submitting — this is assistance, not auto-submission.
    """
    from django.http import JsonResponse
    import base64
    import tempfile
    import os as _os

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    frame_url = (request.POST.get('frame_url') or '').strip()
    camera_id = (request.POST.get('camera_id') or '').strip()
    image_bytes = None

    # Prefer multipart file upload from Live Tracking canvas capture
    up = request.FILES.get('frame') or request.FILES.get('frame_image') or request.FILES.get('image')
    if up:
        try:
            image_bytes = up.read()
        except Exception:
            image_bytes = None

    if not image_bytes and not frame_url:
        return JsonResponse({'ok': False, 'error': 'No frame provided. Capture video frame or upload image.'}, status=400)

    if not image_bytes and frame_url.startswith('data:'):
        try:
            _header, b64data = frame_url.split(',', 1)
            image_bytes = base64.b64decode(b64data)
        except Exception:
            return JsonResponse({'ok': False, 'error': 'Could not decode frame image.'}, status=400)
    elif not image_bytes and frame_url:
        from django.conf import settings as _dj_settings
        from urllib.parse import urlparse
        parsed = urlparse(frame_url)
        is_relative_same_site = (
            not parsed.scheme and not parsed.netloc and frame_url.startswith('/')
        )
        media_url = getattr(_dj_settings, 'MEDIA_URL', '/media/')
        if is_relative_same_site and frame_url.startswith(media_url):
            try:
                rel_path = frame_url[len(media_url):].lstrip('/')
                abs_path = _os.path.normpath(_os.path.join(_dj_settings.MEDIA_ROOT, rel_path))
                media_root_norm = _os.path.normpath(_dj_settings.MEDIA_ROOT)
                if abs_path.startswith(media_root_norm + _os.sep) and _os.path.isfile(abs_path):
                    with open(abs_path, 'rb') as fh:
                        image_bytes = fh.read()
            except Exception:
                image_bytes = None

    if not image_bytes:
        return JsonResponse({'ok': False, 'error': 'Could not read frame image.'}, status=400)

    camera = None
    if camera_id:
        try:
            camera = Camera.objects.get(pk=camera_id)
        except Camera.DoesNotExist:
            camera = None

    from detections.ai import run_pipeline, is_models_available

    if not is_models_available():
        return JsonResponse({'ok': False, 'error': 'AI models are not available on this server.'}, status=503)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        result = run_pipeline(tmp_path, camera=camera)
    except Exception as e:
        log.error("AI assist inference failed: %s", e)
        return JsonResponse({'ok': False, 'error': f'AI inference failed: {e}'}, status=500)
    finally:
        if tmp_path and _os.path.exists(tmp_path):
            try:
                _os.remove(tmp_path)
            except OSError:
                pass

    if result.get('error'):
        return JsonResponse({'ok': False, 'error': result['error']}, status=422)

    raw = result.get('raw_ai_response') or {}
    plate_found = bool(result.get('bbox'))

    plate_text = result.get('plate_text') or raw.get('ocr_text') or ''
    ocr_conf = float(raw.get('ocr_confidence') or 0.0)
    owner = {}
    if plate_text:
        try:
            owner = lookup_owner_by_plate(plate_text) or {}
        except Exception:
            owner = {}

    return JsonResponse({
        'ok': True,
        'plate_found': plate_found,
        'plate_text': plate_text or None,
        'ocr_confidence': ocr_conf,
        'bbox_norm': raw.get('bbox_norm'),
        'vehicle_bbox': raw.get('vehicle_bbox'),
        'confidence': result.get('confidence') or 0.0,
        'side': result.get('side'),
        'side_confidence': raw.get('side_confidence') or 0.0,
        'detected_violation': bool(result.get('detected_violation')),
        'violation_side': raw.get('violation_side'),
        'image_size': raw.get('image_size'),
        'suggested_violation_type': 'wrong_way' if result.get('detected_violation') else None,
        'owner_name': owner.get('owner_name'),
        'cnic': owner.get('cnic'),
        'address': owner.get('address'),
        'phone': owner.get('phone'),
        'integration_status': owner.get('integration_status'),
        'integration_message': owner.get('integration_message'),
        'note': (
            "AI located plate, ran OCR, and classified side — officer must verify before challan."
            if plate_found else
            "AI could not locate a plate. Draw a plate rectangle; OCR will run on the crop."
        ),
    })


@role_required('IT', 'OFFICER')
def ocr_plate_crop(request):
    """OCR a plate crop (drawn by officer). Returns plate text + Excise/NADRA owner if available."""
    from django.http import JsonResponse
    import base64
    import json
    import tempfile
    import os as _os
    from PIL import Image
    from io import BytesIO

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    frame_url = (request.POST.get('frame_url') or '').strip()
    up = request.FILES.get('frame') or request.FILES.get('frame_image')
    image_bytes = up.read() if up else None

    # Bbox: accept either explicit x/y/w/h fields or the `plate_box` JSON array
    # (normalized x1,y1,x2,y2) that the Live Tracking canvas sends.
    def _read_box():
        pb = (request.POST.get('plate_box') or '').strip()
        if pb:
            try:
                vals = json.loads(pb)
                if isinstance(vals, (list, tuple)) and len(vals) >= 4:
                    x1, y1, x2, y2 = [float(v) for v in vals[:4]]
                    return x1, y1, x2 - x1, y2 - y1
            except (ValueError, TypeError):
                pass
        try:
            return (float(request.POST.get('x', 0)),
                    float(request.POST.get('y', 0)),
                    float(request.POST.get('w', 0)),
                    float(request.POST.get('h', 0)))
        except (TypeError, ValueError):
            return None

    box = _read_box()
    if box is None:
        return JsonResponse({'ok': False, 'error': 'Invalid bbox'}, status=400)
    x, y, w, h = box

    if not image_bytes and frame_url.startswith('data:'):
        try:
            _header, b64data = frame_url.split(',', 1)
            image_bytes = base64.b64decode(b64data)
        except Exception:
            return JsonResponse({'ok': False, 'error': 'Could not decode image'}, status=400)
    elif not image_bytes and frame_url.startswith('/'):
        from django.conf import settings as _dj_settings
        media_url = getattr(_dj_settings, 'MEDIA_URL', '/media/')
        if frame_url.startswith(media_url):
            rel = frame_url[len(media_url):].lstrip('/')
            abs_path = _os.path.normpath(_os.path.join(_dj_settings.MEDIA_ROOT, rel))
            if abs_path.startswith(_os.path.normpath(_dj_settings.MEDIA_ROOT) + _os.sep) and _os.path.isfile(abs_path):
                with open(abs_path, 'rb') as fh:
                    image_bytes = fh.read()

    if not image_bytes:
        return JsonResponse({'ok': False, 'error': 'No image'}, status=400)

    try:
        im = Image.open(BytesIO(image_bytes)).convert('RGB')
        W, H = im.size
        # accept normalized or pixel coords
        if w <= 1.5 and h <= 1.5:
            left, top = int(x * W), int(y * H)
            right, bottom = int((x + w) * W), int((y + h) * H)
        else:
            left, top, right, bottom = int(x), int(y), int(x + w), int(y + h)
        left, top = max(0, left), max(0, top)
        right, bottom = min(W, right), min(H, bottom)
        if right - left < 4 or bottom - top < 4:
            return JsonResponse({'ok': False, 'error': 'Crop too small'}, status=400)
        crop = im.crop((left, top, right, bottom))
        from detections.ai import _ocr_plate_image
        ocr_out = _ocr_plate_image(crop)
        plate_text, ocr_conf = ocr_out[0], ocr_out[1]
        ocr_engine = ocr_out[2] if len(ocr_out) > 2 else ""
        owner = {}
        if plate_text:
            try:
                owner = lookup_owner_by_plate(plate_text) or {}
            except Exception:
                owner = {}
        return JsonResponse({
            'ok': True,
            'plate_text': plate_text or None,
            'ocr_confidence': float(ocr_conf or 0),
            'ocr_engine': ocr_engine,
            'owner_name': owner.get('owner_name'),
            'cnic': owner.get('cnic'),
            'address': owner.get('address'),
            'phone': owner.get('phone'),
            'integration_status': owner.get('integration_status'),
            'integration_message': owner.get('integration_message'),
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@role_required('OFFICER', 'IT')
def manual_annotation(request):
    """Full annotation workspace: AI detect + OCR + officer verify + challan."""
    from admin.shared import LiveTrackingService
    from cameras.models import Camera

    camera_id = request.GET.get('camera_id') or ''
    svc = LiveTrackingService(
        user=request.user,
        selected_camera_id=camera_id or None,
        plate_query='',
        status_filter='',
    )
    cameras = svc.get_available_cameras()
    recent = svc.get_recent_detections()[:12]
    latest = svc.get_latest_detection()
    return render(request, 'dashboard/officer/manual_annotation.html', {
        'cameras': cameras,
        'selected_camera': svc.camera or (cameras[0] if cameras else None),
        'selected_camera_id': camera_id,
        'recent_detections': recent,
        'latest_detection': latest,
        'stream_url': svc.resolve_stream_url(),
    })


@role_required('OFFICER', 'IT')
def submit_annotation(request):
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('officer_portal:manual_annotation')

    camera_id = request.POST.get('camera_id', '').strip()
    frame_url = request.POST.get('frame_url', '').strip()
    selected_quadrants = request.POST.get('selected_quadrants', '').strip()
    plate_number = (request.POST.get('plate_number') or request.POST.get('plate_text') or '').strip().upper()
    violation_type = (request.POST.get('violation_type') or 'wrong_way').strip() or 'wrong_way'
    owner_name = request.POST.get('owner_name', '').strip()
    cnic = request.POST.get('cnic', '').strip()
    address = request.POST.get('address', '').strip()
    phone = request.POST.get('phone', '').strip()
    fine_amount = request.POST.get('fine_amount', '500').strip()
    officer_note = (request.POST.get('officer_note') or request.POST.get('notes') or '').strip()
    action_mode = (request.POST.get('action_mode') or 'detection_challan').strip()
    detection_id = request.POST.get('detection_id', '').strip()

    # Server-side input sanitization (mirrors challans.views.home)
    import re as _re
    plate_number = _re.sub(r'[^A-Z0-9-]', '', plate_number)[:12]
    cnic = _re.sub(r'[^0-9-]', '', cnic)[:15]
    camera_id = _re.sub(r'\D', '', camera_id)
    selected_quadrants = ','.join(
        q for q in selected_quadrants.split(',') if q.strip() in ('1', '2', '3', '4')
    )
    try:
        fine_amount = int(_re.sub(r'\D', '', fine_amount) or '500')
        fine_amount = min(max(fine_amount, 0), 1000000)
    except (ValueError, TypeError):
        fine_amount = 500

    # AI-assist fields (present only if the officer clicked "Auto-Detect with AI"
    # in the annotation modal). These are informational/audit metadata only —
    # the officer's typed plate_number and choices above always take precedence.
    ai_used = request.POST.get('ai_assist_used') == '1'
    ai_confidence_raw = request.POST.get('ai_confidence', '').strip()
    ai_side = request.POST.get('ai_side', '').strip() or None
    ai_bbox_norm = request.POST.get('ai_bbox_norm', '').strip()
    try:
        ai_confidence = float(ai_confidence_raw) if ai_confidence_raw else None
    except (ValueError, TypeError):
        ai_confidence = None

    if not plate_number and action_mode != 'annotation_only':
        messages.error(request, "Plate number is required for manual annotation.")
        return redirect('officer_portal:manual_annotation')

    # Prefer Excise/NADRA auto owner when officer did not type one
    if plate_number and not owner_name:
        try:
            od = lookup_owner_by_plate(plate_number) or {}
            owner_name = owner_name or (od.get('owner_name') or '')
            cnic = cnic or (od.get('cnic') or '')
            address = address or (od.get('address') or '')
            phone = phone or (od.get('phone') or '')
        except Exception:
            pass

    camera = None
    if camera_id:
        try:
            camera = Camera.objects.get(pk=camera_id)
        except Camera.DoesNotExist:
            pass

    import base64
    from django.core.files.base import ContentFile
    frame_image = None

    # 1) Live Tracking sends the captured canvas frame as a real multipart
    #    file upload (fd.append('frame_image', blob, 'frame.jpg')). This was
    #    previously never read — the view only looked at frame_url — so every
    #    "Save & Challan" click from Live Tracking silently dropped the
    #    captured evidence frame. Read the uploaded file first.
    uploaded_frame = request.FILES.get('frame_image') or request.FILES.get('frame')
    if uploaded_frame:
        try:
            frame_image = ContentFile(
                uploaded_frame.read(),
                name=f"manual_frame_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            )
        except Exception:
            frame_image = None

    # 2) Fallback: frame_url as base64 data-URI or an already-uploaded /media/ path
    #    (used by the full Manual Annotation page, which posts a normal <form>).
    if not frame_image and frame_url:
        if frame_url.startswith('data:'):
            try:
                _header, b64data = frame_url.split(',', 1)
                frame_image = ContentFile(
                    base64.b64decode(b64data),
                    name=f"manual_frame_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                )
            except Exception:
                frame_image = None
        else:
            from django.conf import settings as _dj_settings
            from urllib.parse import urlparse
            import os as _os

            parsed = urlparse(frame_url)
            is_relative_same_site = (
                not parsed.scheme and not parsed.netloc and frame_url.startswith('/')
            )
            media_url = getattr(_dj_settings, 'MEDIA_URL', '/media/')
            if is_relative_same_site and frame_url.startswith(media_url):
                try:
                    rel_path = frame_url[len(media_url):].lstrip('/')
                    abs_path = _os.path.normpath(_os.path.join(_dj_settings.MEDIA_ROOT, rel_path))
                    media_root_norm = _os.path.normpath(_dj_settings.MEDIA_ROOT)
                    if abs_path.startswith(media_root_norm + _os.sep) and _os.path.isfile(abs_path):
                        with open(abs_path, 'rb') as fh:
                            frame_image = ContentFile(
                                fh.read(),
                                name=f"manual_frame_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            )
                except Exception:
                    frame_image = None

    detection = None
    if detection_id:
        detection = Detection.objects.filter(pk=detection_id).first()
    if detection is not None:
        detection.is_manually_annotated = True
        detection.manual_plate_text = plate_number or detection.manual_plate_text
        detection.manual_violation_type = violation_type
        detection.reviewed_by = request.user
        detection.reviewed_at = timezone.now()
        if officer_note:
            detection.review_notes = officer_note
        if action_mode == 'annotation_only':
            detection.save()
        elif action_mode == 'detection_only':
            detection.status = Detection.CONFIRMED
            detection.save()
        else:
            detection.status = Detection.CONFIRMED
            detection.save()
    else:
        detection = Detection.objects.create(
            camera=camera,
            raw_image=frame_image,
            ai_plate_text=None,
            ai_confidence=ai_confidence,
            ai_side_classification=ai_side if ai_side in ('front', 'back') else None,
            ai_detected_violation=False,
            status=Detection.MANUAL if action_mode == 'annotation_only' else Detection.CONFIRMED,
            is_manually_annotated=True,
            manual_plate_text=plate_number,
            manual_violation_type=violation_type,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
            review_notes=officer_note or 'Manual annotation by officer (AI doubt/ignored)',
        )

    quadrant_images = {}
    try:
        from PIL import Image as PILImage
        import io
        import json as _json
        if frame_image:
            frame_image.seek(0)
            pil_img = PILImage.open(frame_image).convert('RGB')
            w, h = pil_img.size
            # Always keep full frame on detection
            full_buf = io.BytesIO()
            pil_img.save(full_buf, format='JPEG', quality=90)
            detection.raw_image.save(
                f"full_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                ContentFile(full_buf.getvalue()),
                save=False,
            )
            # Prefer officer-drawn vehicle / plate boxes (normalized 0..1 or pixels)
            def _box_to_px(raw):
                if not raw:
                    return None
                if isinstance(raw, str):
                    try:
                        raw = _json.loads(raw)
                    except Exception:
                        return None
                if not isinstance(raw, (list, tuple)) or len(raw) < 4:
                    return None
                x1, y1, x2, y2 = [float(v) for v in raw[:4]]
                # normalized?
                if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
                    x1, x2 = x1 * w, x2 * w
                    y1, y2 = y1 * h, y2 * h
                x1, x2 = sorted((max(0, x1), min(w, x2)))
                y1, y2 = sorted((max(0, y1), min(h, y2)))
                if x2 - x1 < 4 or y2 - y1 < 4:
                    return None
                return (int(x1), int(y1), int(x2), int(y2))

            vbox = _box_to_px(request.POST.get('vehicle_box') or request.POST.get('vehicle_bbox'))
            pbox = _box_to_px(request.POST.get('plate_box') or request.POST.get('plate_bbox'))
            # Fallback: AI assist bbox as vehicle
            if not vbox:
                vbox = _box_to_px(request.POST.get('ai_bbox_norm') or ai_bbox_norm)
            ts = timezone.now().strftime('%Y%m%d_%H%M%S')
            if vbox:
                crop = pil_img.crop(vbox)
                buf = io.BytesIO(); crop.save(buf, format='JPEG', quality=90)
                detection.vehicle_image.save(f'vehicle_{ts}.jpg', ContentFile(buf.getvalue()), save=False)
                quadrant_images['q1'] = ContentFile(buf.getvalue(), name=f'manual_q1_{ts}.jpg')
            if pbox:
                crop = pil_img.crop(pbox)
                buf = io.BytesIO(); crop.save(buf, format='JPEG', quality=95)
                detection.plate_image.save(f'plate_{ts}.jpg', ContentFile(buf.getvalue()), save=False)
                quadrant_images['q2'] = ContentFile(buf.getvalue(), name=f'manual_q2_{ts}.jpg')
            # Legacy fixed quadrants if still selected and no drawn boxes
            if not vbox and not pbox:
                quadrants = [
                    ('q1', (0, 0, w // 2, h // 2)),
                    ('q2', (w // 2, 0, w, h // 2)),
                    ('q3', (0, h // 2, w // 2, h)),
                    ('q4', (w // 2, h // 2, w, h)),
                ]
                selected_list = (
                    [q.strip() for q in selected_quadrants.split(',') if q.strip()]
                    if selected_quadrants else ['1', '2', '3', '4']
                )
                for label, box in quadrants:
                    qnum = {'q1': '1', 'q2': '2', 'q3': '3', 'q4': '4'}[label]
                    if qnum not in selected_list:
                        continue
                    cropped = pil_img.crop(box)
                    buf = io.BytesIO()
                    cropped.save(buf, format='JPEG', quality=85)
                    quadrant_images[label] = ContentFile(
                        buf.getvalue(),
                        name=f"manual_{label}_{ts}.jpg"
                    )
    except Exception:
        pass

    for field_name, cfile in quadrant_images.items():
        setattr(detection, f'manual_{field_name}_image', cfile)
    raw_response = {
        'manual_annotation': True,
        'selected_quadrants': selected_quadrants,
        'officer': request.user.username,
        'annotated_at': timezone.now().isoformat(),
        'ai_assist_used': ai_used,
    }
    if ai_used:
        raw_response['ai_assist'] = {
            'confidence': ai_confidence,
            'side': ai_side,
            'bbox_norm': ai_bbox_norm or None,
        }
    detection.ai_raw_response = raw_response
    detection.save()

    try:
        fine_val = float(fine_amount)
    except (ValueError, TypeError):
        fine_val = 500.0

    due_date = timezone.localdate() + datetime.timedelta(days=14)
    from django.db import transaction
    challan = None
    try:
        with transaction.atomic():
            if action_mode == 'detection_challan' and plate_number:
                # Block duplicate: same detection already has a challan, or same plate+camera within 2 minutes
                existing = Challan.objects.filter(detection=detection).first()
                if existing:
                    challan = existing
                    messages.warning(
                        request,
                        f"Challan already exists for this frame ({existing.ticket_no}). No duplicate issued."
                    )
                else:
                    recent_dup = Challan.objects.filter(
                        plate_number__iexact=plate_number,
                        camera=camera,
                        created_at__gte=timezone.now() - datetime.timedelta(minutes=2),
                    ).first()
                    if recent_dup and camera_id:
                        challan = recent_dup
                        messages.warning(
                            request,
                            f"Possible duplicate: {recent_dup.ticket_no} for {plate_number} on this camera "
                            f"was just issued. Not creating another."
                        )
                    else:
                        challan = None  # will create below
                if challan is None:
                    challan = Challan.objects.create(
                        detection=detection,
                        ticket_no=Challan.objects.generate_ticket_no(plate_number[:3] if plate_number else 'LRN'),
                        plate_number=plate_number,
                        owner_name=owner_name or None,
                        cnic=cnic or None,
                        address=address or None,
                        phone=phone or None,
                        violation_type=violation_type,
                        fine_amount=fine_val,
                        location=camera.location if camera else None,
                        camera=camera,
                        ai_confidence=ai_confidence if ai_used else None,
                        legal_direction=camera.legal_direction if camera else None,
                        issue_date=timezone.localdate(),
                        due_date=due_date,
                        payment_status=Challan.UNPAID,
                        created_by=request.user,
                    )

            AuditLog.write(
                request, 'detection.manual_annotate', 'Detection', detection.id,
                camera_id=camera.camera_id if camera else None,
                plate=plate_number,
                challan=getattr(challan, 'ticket_no', None),
                mode=action_mode,
                quadrants=selected_quadrants,
                ai_assist_used=ai_used,
            )

            import json as _json
            annotations_json = request.POST.get('annotations_json', '[]').strip()
            try:
                annotations_list = _json.loads(annotations_json) if annotations_json else []
            except (ValueError, TypeError):
                annotations_list = []
            if annotations_list:
                for ann in annotations_list:
                    try:
                        Annotation.objects.create(
                            detection=detection,
                            created_by=request.user,
                            type=ann.get('type', Annotation.TYPE_MARKER),
                            object_type=ann.get('object_type', Annotation.OBJECT_VEHICLE),
                            violation_type=ann.get('violation_type') or ann.get('subtype'),
                            label=ann.get('label', '')[:100],
                            coordinates=ann.get('coords', {}) if isinstance(ann.get('coords'), dict) else {'raw': str(ann.get('coords', ''))},
                        )
                    except Exception:
                        pass
                AuditLog.write(
                    request, 'annotation.bulk_create', 'Annotation', detection.id,
                    count=len(annotations_list),
                    detection_id=detection.id,
                )
    except Exception as e:
        log.error("Manual annotation submission failed: %s", e)
        messages.error(request, f"Failed to create manual challan: {e}")
        return redirect('officer_portal:live_tracking')

    if challan:
        messages.success(
            request,
            f"Manual challan {challan.ticket_no} created for plate {plate_number}."
        )
    elif action_mode == 'detection_only':
        messages.success(request, f"Detection confirmed for plate {plate_number or '—'}. No challan issued.")
    else:
        messages.success(request, "Annotation saved.")

    # AJAX / fetch clients (Live Tracking UI)
    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.headers.get('Accept') or '')
        or request.POST.get('format') == 'json'
    )
    if wants_json or request.FILES.get('frame_image'):
        from django.http import JsonResponse
        return JsonResponse({
            'ok': True,
            'success': True,
            'detection_id': detection.id if detection else None,
            'challan_id': getattr(challan, 'id', None),
            'ticket_no': getattr(challan, 'ticket_no', None),
            'plate_number': plate_number,
        })
    return redirect('officer_portal:live_tracking')


@officer_or_dig_required
def officer_profile(request):
    user = request.user
    if request.method == 'POST':
        user.phone = request.POST.get('phone', user.phone) or user.phone
        if hasattr(user, 'department'):
            user.department = request.POST.get('department', user.department) or user.department
        user.save()
        from django.contrib import messages
        messages.success(request, 'Profile updated.')
        return redirect('officer_portal:profile')
    return render(request, 'dashboard/officer/profile.html', {'profile_user': user})



@role_required('OFFICER', 'IT')
def annotation_save(request):
    """Save canvas shapes from live-tracking to Annotation model."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    import json
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    shapes = payload.get('shapes') or []
    camera_id = payload.get('camera_id')
    detection_id = payload.get('detection_id')
    try:
        from detections.models import Annotation, Detection
        det = None
        if detection_id:
            det = Detection.objects.filter(pk=detection_id).first()
        if det is None and camera_id:
            det = Detection.objects.filter(camera_id=camera_id).order_by('-created_at').first()
        if det is None:
            return JsonResponse({'ok': False, 'error': 'No detection to attach annotation'}, status=400)
        type_map = {'rect': Annotation.TYPE_BOX, 'ellipse': Annotation.TYPE_BOX,
                    'line': Annotation.TYPE_LINE, 'freehand': Annotation.TYPE_POLYGON}
        saved = 0
        for s in shapes:
            Annotation.objects.create(
                detection=det,
                created_by=request.user,
                type=type_map.get(s.get('type'), Annotation.TYPE_BOX),
                object_type=Annotation.OBJECT_VEHICLE,
                label=s.get('type', 'shape'),
                coordinates=s,
            )
            saved += 1
        try:
            AuditLog.write(
                request, 'annotation.save', 'Detection', det.id,
                shapes=saved, camera_id=str(camera_id or ''),
            )
        except Exception:
            pass
        return JsonResponse({'ok': True, 'saved': saved})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
