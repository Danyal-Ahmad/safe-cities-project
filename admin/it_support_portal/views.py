import platform

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from accounts.models import User
from accounts.decorators import it_required
from challans.models import Challan
from detections.models import Detection
from cameras.models import Camera
from admin.dig_portal.models import AuditLog
from detections.ai import is_models_available, get_model_info

from .models import PaymentMethod


@it_required
def dashboard(request):
    from django.db.models import Sum
    from django.utils import timezone
    from datetime import timedelta
    from admin.dig_portal.models import ChallanTemplate, Banner, Alert

    today = timezone.localdate()
    last_24h = timezone.now() - timedelta(hours=24)
    last_7d = timezone.now() - timedelta(days=7)
    last_30d = timezone.now() - timedelta(days=30)

    cameras = Camera.objects.all()
    cameras_total = cameras.count()
    cameras_online = cameras.filter(health_status='online').count()
    cameras_offline = cameras.filter(health_status='offline').count()
    cameras_streaming = cameras.filter(is_streaming=True).count()
    cameras_active = cameras.filter(is_active=True).count()
    cameras_with_issues = cameras.exclude(health_status='online').count()

    detections_total = Detection.objects.count()
    detections_24h = Detection.objects.filter(created_at__gte=last_24h).count()
    detections_7d = Detection.objects.filter(created_at__gte=last_7d).count()
    detections_confirmed = Detection.objects.filter(status__in=['confirmed', 'auto_confirmed']).count()
    detections_pending = Detection.objects.filter(status='pending').count()

    challans_total = Challan.objects.count()
    challans_paid = Challan.objects.filter(payment_status='PAID').count()
    challans_unpaid = Challan.objects.filter(payment_status='UNPAID').count()
    challans_overdue = Challan.objects.filter(due_date__lt=today).exclude(payment_status='PAID').count()
    revenue_30d = Challan.objects.filter(
        payment_status='PAID', paid_at__gte=last_30d
    ).aggregate(total=Sum('fine_amount'))['total'] or 0

    users_total = User.objects.count()
    staff_count = User.objects.filter(role__in=['DIG', 'SSP', 'SUPV', 'OFFICER', 'AUDIT', 'IT']).count()
    citizen_count = User.objects.filter(role='USER').count()
    active_users_24h = User.objects.filter(last_login__gte=last_24h).count()

    daily = []
    for d in range(6, -1, -1):
        day = timezone.now() - timedelta(days=d)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = Detection.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count()
        daily.append({'date': day_start.strftime('%b %d'), 'count': count})

    challan_daily = []
    for d in range(6, -1, -1):
        day = timezone.now() - timedelta(days=d)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = Challan.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count()
        challan_daily.append({'date': day_start.strftime('%b %d'), 'count': count})

    from django.db.models import Count as CountQ
    violation_dist = list(
        Challan.objects.filter(created_at__gte=last_30d)
        .values('violation_type').annotate(count=CountQ('id'))
        .order_by('-count')[:6]
    )

    camera_health = list(
        cameras.values('camera_id', 'location', 'health_status', 'is_streaming', 'is_active')[:6]
    )

    recent_audit = AuditLog.objects.order_by('-timestamp')[:8]

    recent_detections = Detection.objects.select_related('camera').order_by('-created_at')[:6]

    templates_count = ChallanTemplate.objects.filter(is_active=True).count()
    banners_active = Banner.objects.filter(is_active=True).count()
    alerts_active = Alert.objects.filter(is_active=True).count()
    payment_methods_count = PaymentMethod.objects.count()
    payment_methods_active = PaymentMethod.objects.filter(status='active').count()

    return render(request, 'dashboard/it_support/dashboard.html', {
        'cameras_total': cameras_total, 'cameras_online': cameras_online,
        'cameras_offline': cameras_offline, 'cameras_streaming': cameras_streaming,
        'cameras_active': cameras_active, 'cameras_with_issues': cameras_with_issues,
        'detections_total': detections_total, 'detections_24h': detections_24h,
        'detections_7d': detections_7d, 'detections_confirmed': detections_confirmed,
        'detections_pending': detections_pending,
        'challans_total': challans_total, 'challans_paid': challans_paid,
        'challans_unpaid': challans_unpaid, 'challans_overdue': challans_overdue,
        'revenue_30d': revenue_30d,
        'users_total': users_total, 'staff_count': staff_count,
        'citizen_count': citizen_count, 'active_users_24h': active_users_24h,
        'ai_available': is_models_available(), 'model_info': get_model_info(),
        'python_version': platform.python_version(), 'platform': platform.platform(),
        'templates_count': templates_count, 'banners_active': banners_active,
        'alerts_active': alerts_active,
        'payment_methods_count': payment_methods_count, 'payment_methods_active': payment_methods_active,
        'daily_detections': daily, 'daily_challans': challan_daily,
        'violation_dist': violation_dist, 'camera_health': camera_health,
        'recent_audit': recent_audit, 'recent_detections': recent_detections,
    })


@it_required
def pdf_settings(request):
    """Legacy URL - PDF settings live under System Settings tab."""
    from django.shortcuts import redirect
    return redirect('/portal/it/settings/?tab=pdf-settings')



@it_required
def payment_method_list(request):
    methods = PaymentMethod.objects.all().order_by('name')
    return render(request, 'dashboard/it_support/payment_method_list.html', {
        'methods': methods,
        'active_count': methods.filter(status=PaymentMethod.STATUS_ACTIVE).count(),
        'total_count': methods.count(),
    })


@it_required
def payment_method_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, "Name is required.")
            return _render_pm_edit(request, pm=None, is_add=True)
        if PaymentMethod.objects.filter(name__iexact=name).exists():
            messages.error(request, f"A payment method named '{name}' already exists.")
            return _render_pm_edit(request, pm=None, is_add=True)

        type_code = request.POST.get('type', PaymentMethod.TYPE_WALLET)
        if type_code in ('bank', 'cash'):
            messages.error(request, 'Bank transfer and cash are not allowed. Use JazzCash, EasyPaisa, or card.')
            return redirect('it_support_portal:payment_method_list')
        pm = PaymentMethod(
            name=name,
            provider=request.POST.get('provider', '').strip(),
            type=type_code,
            status=request.POST.get('status', PaymentMethod.STATUS_DISABLED),
            config=_collect_pm_config(request, type_code),
            transaction_settings=_collect_pm_tx_settings(request),
            created_by=request.user,
        )
        pm.save()
        AuditLog.write(request, 'payment_method.create', 'PaymentMethod', pm.id,
                       name=pm.name, provider=pm.provider, type=pm.type)
        messages.success(request, f"Payment method '{pm.name}' created.")
        return redirect('it_support_portal:payment_method_list')
    return _render_pm_edit(request, pm=None, is_add=True)


@it_required
def payment_method_edit(request, method_id):
    pm = get_object_or_404(PaymentMethod, pk=method_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, "Name is required.")
            return _render_pm_edit(request, pm=pm, is_add=False)
        if PaymentMethod.objects.filter(name__iexact=name).exclude(pk=pm.pk).exists():
            messages.error(request, f"Another payment method named '{name}' already exists.")
            return _render_pm_edit(request, pm=pm, is_add=False)

        pm.name = name
        pm.provider = request.POST.get('provider', '').strip()
        pm.type = request.POST.get('type', PaymentMethod.TYPE_WALLET)
        pm.status = request.POST.get('status', PaymentMethod.STATUS_DISABLED)
        pm.config = _collect_pm_config(request, pm.type)
        pm.transaction_settings = _collect_pm_tx_settings(request)
        pm.save()
        AuditLog.write(request, 'payment_method.update', 'PaymentMethod', pm.id,
                       name=pm.name, provider=pm.provider, status=pm.status)
        messages.success(request, f"Payment method '{pm.name}' updated.")
        return redirect('it_support_portal:payment_method_list')
    return _render_pm_edit(request, pm=pm, is_add=False)


@it_required
def payment_method_toggle(request, method_id):
    pm = get_object_or_404(PaymentMethod, pk=method_id)
    if request.method == 'POST':
        if pm.status == PaymentMethod.STATUS_ACTIVE:
            pm.status = PaymentMethod.STATUS_DISABLED
        else:
            pm.status = PaymentMethod.STATUS_ACTIVE
        pm.save()
        AuditLog.write(request, 'payment_method.toggle', 'PaymentMethod', pm.id,
                       name=pm.name, status=pm.status)
        messages.success(request, f"Payment method '{pm.name}' is now {pm.get_status_display()}.")
    return redirect('it_support_portal:payment_method_list')


@it_required
def payment_method_delete(request, method_id):
    pm = get_object_or_404(PaymentMethod, pk=method_id)
    if request.method == 'POST':
        name = pm.name
        pm.delete()
        AuditLog.write(request, 'payment_method.delete', 'PaymentMethod', method_id, name=name)
        messages.success(request, f"Payment method '{name}' deleted.")
    return redirect('it_support_portal:payment_method_list')


def _collect_pm_config(request, type_code):
    config = {}
    if type_code == PaymentMethod.TYPE_WALLET:
        for f in ('merchant_id', 'password', 'integrity_salt', 'return_url'):
            v = request.POST.get(f'config_{f}', '').strip()
            if v:
                config[f] = v
    elif type_code == PaymentMethod.TYPE_CARD:
        for f in ('publishable_key', 'secret_key', 'webhook_secret'):
            v = request.POST.get(f'config_{f}', '').strip()
            if v:
                config[f] = v
    elif type_code == PaymentMethod.TYPE_GATEWAY:
        for f in ('api_key', 'api_secret', 'webhook_url', 'return_url'):
            v = request.POST.get(f'config_{f}', '').strip()
            if v:
                config[f] = v
    return config


def _collect_pm_tx_settings(request):
    settings = {}
    for f in ('currency', 'environment', 'settlement_days'):
        v = request.POST.get(f'tx_{f}', '').strip()
        if v:
            settings[f] = v
    for f in ('min_amount', 'max_amount'):
        v = request.POST.get(f'tx_{f}', '').strip()
        if v:
            try:
                settings[f] = float(v)
            except ValueError:
                pass
    return settings


def _render_pm_edit(request, pm, is_add):
    if pm is None:
        pm = PaymentMethod(
            name='', provider='', type=PaymentMethod.TYPE_WALLET,
            status=PaymentMethod.STATUS_DISABLED,
            config={}, transaction_settings={},
        )
    if not isinstance(getattr(pm, 'config', None), dict):
        pm.config = {}
    if not isinstance(getattr(pm, 'transaction_settings', None), dict):
        pm.transaction_settings = {}
    return render(request, 'dashboard/it_support/payment_method_edit.html', {
        'pm': pm,
        'is_add': is_add,
        'types': PaymentMethod.TYPE_CHOICES,
        'statuses': PaymentMethod.STATUS_CHOICES,
    })


@it_required
def staff_list(request):
    staff = User.objects.filter(role__in=User.STAFF_ROLES).order_by('role', 'username')
    role_filter = request.GET.get('role')
    if role_filter:
        staff = staff.filter(role=role_filter)
    dept_filter = request.GET.get('department')
    if dept_filter:
        staff = staff.filter(department__icontains=dept_filter)
    region_filter = request.GET.get('region')
    if region_filter:
        staff = staff.filter(region__icontains=region_filter)
    return render(request, 'dashboard/it_support/staff_list.html', {
        'staff': staff,
        'role_filter': role_filter,
        'dept_filter': dept_filter,
        'region_filter': region_filter,
        'role_choices': User.ROLE_CHOICES,
        'total_count': User.objects.filter(role__in=User.STAFF_ROLES).count(),
    })



from django.http import JsonResponse
from accounts.decorators import permission_required, it_required


@it_required
@permission_required('live_tracking')
def live_tracking(request):
    """IT Support Live Vehicle Tracking (full camera access)."""
    from cameras.models import Camera
    from realtime.models import LiveFeed
    from admin.shared import LiveTrackingService

    selected_camera_id = request.GET.get('camera_id') or ''
    plate_q = (request.GET.get('plate') or '').strip().upper()
    status_q = (request.GET.get('status') or '').strip()

    svc = LiveTrackingService(
        user=request.user,
        selected_camera_id=selected_camera_id or None,
        plate_query=plate_q,
        status_filter=status_q,
        limit=80,
    )
    cameras = list(Camera.objects.all().order_by('-is_active', '-installed_date')[:100])
    recent = svc.get_recent_detections()
    latest = svc.get_latest_detection()
    stats = svc.get_stats(recent)
    live_feeds = list(
        LiveFeed.objects.filter(is_active=True).select_related('camera').order_by('-created_at')[:12]
    )
    return render(request, 'dashboard/shared/live_tracking.html', {
        'cameras': cameras,
        'has_assignment': True,
        'selected_camera_id': selected_camera_id,
        'selected_camera': svc.camera,
        'stream_url': svc.resolve_stream_url(),
        'camera_not_found': svc.camera_not_found,
        'plate_q': plate_q,
        'status_q': status_q,
        'recent_detections': recent,
        'latest_detection': latest,
        'live_feeds': live_feeds,
        'stat_total': stats['total'],
        'stat_violations': stats['violations'],
        'stat_pending': stats['pending'],
        'stat_unique_plates': stats['unique_plates'],
        'stat_avg_conf': stats['avg_confidence'],
        'status_choices': Detection.STATUS_CHOICES,
    })


@it_required
@permission_required('live_tracking_timeline')
def live_tracking_timeline(request):
    """JSON timeline for IT Live Tracking."""
    from admin.shared import LiveTrackingService

    plate = (request.GET.get('plate') or '').strip()
    camera_id = request.GET.get('camera_id') or ''
    status = (request.GET.get('status') or '').strip()
    svc = LiveTrackingService(
        user=request.user,
        selected_camera_id=camera_id or None,
        plate_query=plate,
        status_filter=status,
        limit=60,
    )
    detections = svc.get_recent_detections()
    items = svc.serialize_detections(detections)
    for it in items:
        it['bbox'] = it.get('bbox_norm')
        it['box'] = it.get('bbox_norm')
        it['confidence'] = it.get('confidence', 0)
    return JsonResponse({
        'items': items,
        'count': len(items),
        'camera_not_found': svc.camera_not_found,
    })




def _studio_sample_context():
    import datetime
    from types import SimpleNamespace
    from challans.pdf_service import (
        _branding_context, _speed_context, _camera_context, _frame_evidence_context,
        amount_in_words, _make_qr_data_url, _make_barcode, _needs_nadra_excise_integration,
    )
    from admin.dig_portal.models import SystemSettings

    sys_settings = SystemSettings.get()
    detection = SimpleNamespace(
        ai_plate_text='LEA-1234', ai_confidence=0.93, created_at=datetime.datetime(2026, 11, 5, 14, 23, 0),
        ai_raw_response={'bbox_norm': [0.30, 0.42, 0.46, 0.58], 'ocr_confidence': 0.88,
                         'frame_evidence': [
                             {'plate': 'LEA-1234', 'confidence': 0.92, 'ocr_confidence': 0.86, 'timestamp': '2026-11-05 14:23:01', 'plate_complete': True},
                             {'plate': 'LEA-1234', 'confidence': 0.94, 'ocr_confidence': 0.89, 'timestamp': '2026-11-05 14:23:02', 'plate_complete': True},
                             {'plate': 'LEA-1234', 'confidence': 0.95, 'ocr_confidence': 0.91, 'timestamp': '2026-11-05 14:23:03', 'plate_complete': True},
                         ]},
        raw_image=None, plate_crop_image=None, vehicle_image=None, plate_image=None,
    )
    camera = SimpleNamespace(camera_id='CAM-001-SCP', location='Main Boulevard')
    challan = SimpleNamespace(
        ticket_no='20990001', plate_number='LEA-1234', owner_name='Ahmed Khan',
        cnic='35202-1234567-1', address='House 12, Street 4, Sector 7',
        phone='0300-1234567', vehicle_type='Car', make_year='2023', color='White',
        chassis_no='CHS-99887766', violation_type='wrong_way',
        get_violation_type_display=lambda: 'Wrong Way', fine_amount=2000,
        location='Main Boulevard', ai_confidence=0.93, moving_direction='DOWN',
        legal_direction='UP', issue_date=datetime.date(2026, 11, 5),
        due_date=datetime.date(2026, 12, 5), payment_status='UNPAID',
        get_payment_status_display=lambda: 'Unpaid', created_at=datetime.datetime(2026, 11, 5, 14, 25, 0),
        camera=camera, detection=detection, psid='209900011',
        payment_qr_payload='SAFECITY|PSID:209900011|TKT:20990001|PLT:LEA-1234|AMT:2000|STS:UNPAID',
        is_overdue=False,
    )
    bc_svg, _ = _make_barcode(challan.ticket_no)
    return {
        'challan': challan,
        'settings': sys_settings,
        'evidence_summary': {
            'checks': [{'check': c, 'passed': True, 'detail': 'verified'} for c in
                       ('plate_readability', 'frame_consistency', 'violation_logic', 'image_evidence', 'chain_integrity')],
            'passed': 5, 'total': 5, 'all_passed': True, 'hash': 'ab12cd34ef56' + '0' * 52,
            'track_id': 'TRK-1-LEA-0001', 'track_frames': 3, 'track_consistency': 1.0,
        },
        'template_config': sys_settings.template_config or {},
        'branding': _branding_context(sys_settings),
        'speed': _speed_context(challan),
        'camera_meta': _camera_context(challan),
        'frame_evidence': _frame_evidence_context(challan),
        'fine_in_words': amount_in_words(2000),
        'due_days': 30, 'appeal_days': 15, 'points_deducted': 0,
        'qr_code_data_url': _make_qr_data_url(challan.payment_qr_payload),
        'logo_left_path': None, 'logo_right_path': None,
        'quadrant_images': [], 'evidence_images': [],
        'barcode_svg': bc_svg, 'barcode_data_url': None,
        'needs_nadra_excise': _needs_nadra_excise_integration(challan),
    }


@it_required
def challan_studio(request):
    from admin.dig_portal.models import ChallanTemplate, SystemSettings
    from challans.pdf_service import FILE_TEMPLATE_MAP

    sys_settings = SystemSettings.get()
    active_key = sys_settings.pdf_template or 'standard_a4'

    if request.method == 'POST':
        action = request.POST.get('action') or ''
        if action == 'save':
            name = (request.POST.get('name') or '').strip()
            html = request.POST.get('html_content') or ''
            tid = request.POST.get('template_id') or ''
            if not name or len(html.strip()) < 80:
                messages.error(request, "A template name and complete HTML are required.")
                return redirect('it_support_portal:challan_studio')
            design_json = request.POST.get('design_json') or ''
            if len(design_json) > 400000:
                messages.error(request, "Design document too large.")
                return redirect('it_support_portal:challan_studio')
            if tid:
                obj = ChallanTemplate.objects.filter(pk=tid).first()
                if not obj:
                    messages.error(request, "Template not found.")
                    return redirect('it_support_portal:challan_studio')
                obj.name = name
                obj.html_content = html
                obj.design_json = design_json
                obj.save()
                AuditLog.write(request, 'challan_studio.save', 'ChallanTemplate', obj.id, name=name)
                messages.success(request, f"Template '{name}' saved.")
            else:
                obj = ChallanTemplate.objects.create(
                    name=name, html_content=html, design_json=design_json, uploaded_by=request.user)
                AuditLog.write(request, 'challan_studio.create', 'ChallanTemplate', obj.id, name=name)
                messages.success(request, f"Template '{name}' created.")
            if request.POST.get('activate') == '1':
                ChallanTemplate.objects.exclude(pk=obj.pk).update(is_active=False)
                obj.is_active = True
                obj.save()
                sys_settings.pdf_template = f'db:{obj.id}'
                sys_settings.save(update_fields=['pdf_template'])
                AuditLog.write(request, 'challan_studio.activate', 'ChallanTemplate', obj.id, name=name)
                messages.success(request, f"Template '{name}' is now the active challan layout.")
            return redirect('it_support_portal:challan_studio')

        if action == 'delete':
            tid = request.POST.get('template_id') or ''
            obj = ChallanTemplate.objects.filter(pk=tid).first()
            if obj:
                name = obj.name
                if sys_settings.pdf_template == f'db:{obj.id}':
                    sys_settings.pdf_template = 'standard_a4'
                    sys_settings.save(update_fields=['pdf_template'])
                obj.delete()
                AuditLog.write(request, 'challan_studio.delete', 'ChallanTemplate', int(tid), name=name)
                messages.success(request, f"Template '{name}' deleted.")
            return redirect('it_support_portal:challan_studio')

        if action == 'duplicate':
            tid = request.POST.get('template_id') or ''
            obj = ChallanTemplate.objects.filter(pk=tid).first()
            if obj:
                copy = ChallanTemplate.objects.create(
                    name=f"{obj.name} (Copy)", html_content=obj.html_content,
                    uploaded_by=request.user, is_active=False)
                AuditLog.write(request, 'challan_studio.duplicate', 'ChallanTemplate', copy.id, source=obj.id)
                messages.success(request, f"Template duplicated as '{copy.name}'.")
            return redirect('it_support_portal:challan_studio')

        if action == 'activate':
            tid = request.POST.get('template_id') or ''
            if tid.startswith('db:'):
                obj = ChallanTemplate.objects.filter(pk=tid[3:]).first()
                if obj:
                    ChallanTemplate.objects.exclude(pk=obj.pk).update(is_active=False)
                    obj.is_active = True
                    obj.save()
                    sys_settings.pdf_template = f'db:{obj.id}'
                    sys_settings.save(update_fields=['pdf_template'])
                    AuditLog.write(request, 'challan_studio.activate', 'ChallanTemplate', obj.id, name=obj.name)
                    messages.success(request, f"Active challan template set to '{obj.name}'.")
            elif tid in FILE_TEMPLATE_MAP:
                ChallanTemplate.objects.update(is_active=False)
                sys_settings.pdf_template = tid
                sys_settings.save(update_fields=['pdf_template'])
                AuditLog.write(request, 'challan_studio.activate_file', 'ChallanTemplateFile', 0, key=tid)
                messages.success(request, f"Active challan template set to '{tid}'.")
            return redirect('it_support_portal:challan_studio')

    templates = list(ChallanTemplate.objects.order_by('-created_at'))
    builtin_files = []
    import pathlib
    from django.conf import settings as dj_settings
    from django.template import Template, Context
    sample_ctx = Context(_studio_sample_context())
    fs_dir = pathlib.Path(dj_settings.BASE_DIR) / 'templates' / 'challan' / 'challan_templates'
    for key in FILE_TEMPLATE_MAP:
        fp = fs_dir / f'{key}.html'
        if fp.is_file():
            try:
                preview = Template(fp.read_text(encoding='utf-8', errors='ignore')).render(sample_ctx)
            except Exception:
                preview = ''
            builtin_files.append({'key': key, 'size': fp.stat().st_size, 'preview_html': preview})
    studio_templates = []
    for t in templates:
        try:
            preview = Template(t.html_content or '').render(sample_ctx) if t.html_content else ''
        except Exception:
            preview = ''
        studio_templates.append({
            'id': t.id, 'name': t.name, 'is_active': (active_key == f'db:{t.id}'),
            'created_at': t.created_at, 'size': len(t.html_content or ''),
            'preview_html': preview, 'has_design': bool(t.design_json),
            'updated': t.updated_at,
        })
    return render(request, 'dashboard/it_support/challan_studio.html', {
        'studio_templates': studio_templates,
        'builtin_files': builtin_files,
        'active_key': active_key,
    })


@it_required
def challan_studio_preview(request):
    from django.http import HttpResponse
    if request.method != 'POST':
        return HttpResponse(status=405)
    html = request.POST.get('html_content') or ''
    if len(html.strip()) < 80:
        return HttpResponse('Template HTML too short.', status=400)
    from django.template import Template, Context
    from challans.pdf_service import _render_html_to_pdf
    try:
        rendered = Template(html).render(Context(_studio_sample_context()))
    except Exception as e:
        return HttpResponse(f'Template render error: {e}', status=400, content_type='text/plain')
    pdf = _render_html_to_pdf(rendered)
    if not pdf:
        return HttpResponse('PDF engine failed to render the preview.', status=500)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="studio-preview.pdf"'
    return response


@it_required
def challan_studio_data(request):
    from django.http import JsonResponse
    import pathlib
    from django.conf import settings as dj_settings
    from admin.dig_portal.models import ChallanTemplate
    from challans.pdf_service import FILE_TEMPLATE_MAP

    items = [
        {'kind': 'db', 'id': t.id, 'name': t.name, 'html': t.html_content or '',
         'design': t.design_json or '', 'has_design': bool(t.design_json)}
        for t in ChallanTemplate.objects.order_by('-created_at')
    ]
    fs_dir = pathlib.Path(dj_settings.BASE_DIR) / 'templates' / 'challan' / 'challan_templates'
    for key in FILE_TEMPLATE_MAP:
        fp = fs_dir / f'{key}.html'
        if fp.is_file():
            items.append({'kind': 'builtin', 'key': key, 'name': key, 'html': fp.read_text(encoding='utf-8', errors='ignore')})
    return JsonResponse({'items': items})


def _audit_studio_sample_context():
    import datetime
    from types import SimpleNamespace
    from admin.audit_portal.pdf_service import build_audit_context
    from admin.dig_portal.models import SystemSettings
    from accounts.models import User

    sys_settings = SystemSettings.get()
    auditor = SimpleNamespace(
        id=5, username='audit@safecities.project', get_full_name=lambda: 'Ayesha Audit',
        designation='Audit Officer', staff_id='PSC-2026-AUD-005',
        signature=None, signature_stamp=None, get_role_display=lambda: 'Audit Officer',
    )
    dig = SimpleNamespace(
        id=1, username='dig@safecities.project', get_full_name=lambda: 'Aamir DIG',
        designation='Deputy Inspector General (Traffic)', staff_id='PSC-2026-DIG-001',
        signature=None, signature_stamp=None, get_role_display=lambda: 'DIG',
    )
    ctx = build_audit_context(
        datetime.date(2026, 10, 1), datetime.date(2026, 11, 5),
        auditor, 'Studio Preview', 'audit_summary_report')
    ctx['generated_by_ctx'] = {
        'name': 'Ayesha Audit', 'designation': 'Audit Officer', 'staff_id': 'PSC-2026-AUD-005',
        'signature_url': None, 'stamp_url': None,
    }
    ctx['countersigned_by_ctx'] = {
        'name': 'Aamir DIG', 'designation': 'Deputy Inspector General (Traffic)',
        'staff_id': 'PSC-2026-DIG-001', 'signature_url': None, 'stamp_url': None,
    }
    return ctx


AUDIT_TEMPLATE_META = {
    'audit_summary_report': ('Periodic Audit Summary Report', 'Enforcement, evidence integrity and financial position with findings'),
    'compliance_certificate': ('Certificate of Compliance', 'Certifies the pipeline meets the five-step evidence standard'),
    'financial_audit_statement': ('Financial Audit Statement', 'Revenue collected / outstanding with auditor note and triple signatures'),
    'security_incident_report': ('Security & Authentication Incident Report', 'Login activity, failed attempts, source IPs and audited actions'),
    'operational_review_letter': ('Operational Review Letter', 'Official letter to the DIG with recommendations and CC list'),
}


@it_required
def audit_studio(request):
    from admin.dig_portal.models import AuditTemplate, SystemSettings
    from admin.audit_portal.pdf_service import FILE_TEMPLATE_MAP

    sys_settings = SystemSettings.get()
    active_key = sys_settings.audit_template or 'audit_summary_report'

    if request.method == 'POST':
        action = request.POST.get('action') or ''
        if action == 'save':
            name = (request.POST.get('name') or '').strip()
            html = request.POST.get('html_content') or ''
            design_json = request.POST.get('design_json') or ''
            tid = request.POST.get('template_id') or ''
            if not name or len(html.strip()) < 80:
                messages.error(request, "A template name and complete HTML are required.")
                return redirect('it_support_portal:audit_studio')
            if len(design_json) > 400000:
                messages.error(request, "Design document too large.")
                return redirect('it_support_portal:audit_studio')
            if tid:
                obj = AuditTemplate.objects.filter(pk=tid).first()
                if not obj:
                    messages.error(request, "Template not found.")
                    return redirect('it_support_portal:audit_studio')
                obj.name = name
                obj.html_content = html
                obj.design_json = design_json
                obj.save()
                AuditLog.write(request, 'audit_studio.save', 'AuditTemplate', obj.id, name=name)
                messages.success(request, f"Audit template '{name}' saved.")
            else:
                obj = AuditTemplate.objects.create(name=name, html_content=html,
                                                   design_json=design_json, created_by=request.user)
                AuditLog.write(request, 'audit_studio.create', 'AuditTemplate', obj.id, name=name)
                messages.success(request, f"Audit template '{name}' created.")
            if request.POST.get('activate') == '1':
                AuditTemplate.objects.exclude(pk=obj.pk).update(is_active=False)
                obj.is_active = True
                obj.save()
                sys_settings.audit_template = f'db:{obj.id}'
                sys_settings.save(update_fields=['audit_template'])
                AuditLog.write(request, 'audit_studio.activate', 'AuditTemplate', obj.id, name=name)
                messages.success(request, f"Audit template '{name}' is now the active audit document layout.")
            return redirect('it_support_portal:audit_studio')

        if action == 'delete':
            tid = request.POST.get('template_id') or ''
            obj = AuditTemplate.objects.filter(pk=tid).first()
            if obj:
                name = obj.name
                if sys_settings.audit_template == f'db:{obj.id}':
                    sys_settings.audit_template = 'audit_summary_report'
                    sys_settings.save(update_fields=['audit_template'])
                obj.delete()
                AuditLog.write(request, 'audit_studio.delete', 'AuditTemplate', int(tid), name=name)
                messages.success(request, f"Audit template '{name}' deleted.")
            return redirect('it_support_portal:audit_studio')

        if action == 'duplicate':
            tid = request.POST.get('template_id') or ''
            obj = AuditTemplate.objects.filter(pk=tid).first()
            if obj:
                copy = AuditTemplate.objects.create(
                    name=f"{obj.name} (Copy)", html_content=obj.html_content,
                    design_json=obj.design_json, created_by=request.user)
                AuditLog.write(request, 'audit_studio.duplicate', 'AuditTemplate', copy.id, source=obj.id)
                messages.success(request, f"Audit template duplicated as '{copy.name}'.")
            return redirect('it_support_portal:audit_studio')

        if action == 'activate':
            tid = request.POST.get('template_id') or ''
            if tid.startswith('db:'):
                obj = AuditTemplate.objects.filter(pk=tid[3:]).first()
                if obj:
                    AuditTemplate.objects.exclude(pk=obj.pk).update(is_active=False)
                    obj.is_active = True
                    obj.save()
                    sys_settings.audit_template = f'db:{obj.id}'
                    sys_settings.save(update_fields=['audit_template'])
                    AuditLog.write(request, 'audit_studio.activate', 'AuditTemplate', obj.id, name=obj.name)
                    messages.success(request, f"Active audit template set to '{obj.name}'.")
            elif tid in FILE_TEMPLATE_MAP:
                AuditTemplate.objects.update(is_active=False)
                sys_settings.audit_template = tid
                sys_settings.save(update_fields=['audit_template'])
                AuditLog.write(request, 'audit_studio.activate_file', 'AuditTemplateFile', 0, key=tid)
                messages.success(request, f"Active audit template set to '{tid}'.")
            return redirect('it_support_portal:audit_studio')

    import pathlib
    from django.conf import settings as dj_settings
    from django.template import Template, Context
    sample_ctx = Context(_audit_studio_sample_context())

    builtin_files = []
    fs_dir = pathlib.Path(dj_settings.BASE_DIR) / 'templates' / 'audit' / 'audit_templates'
    for key in FILE_TEMPLATE_MAP:
        fp = fs_dir / f'{key}.html'
        if fp.is_file():
            try:
                preview = Template(fp.read_text(encoding='utf-8', errors='ignore')).render(sample_ctx)
            except Exception:
                preview = ''
            name, blurb = AUDIT_TEMPLATE_META.get(key, (key, ''))
            builtin_files.append({'key': key, 'name': name, 'blurb': blurb,
                                  'size': fp.stat().st_size, 'preview_html': preview})

    studio_templates = []
    for t in AuditTemplate.objects.order_by('-created_at'):
        try:
            preview = Template(t.html_content or '').render(sample_ctx) if t.html_content else ''
        except Exception:
            preview = ''
        studio_templates.append({
            'id': t.id, 'name': t.name, 'is_active': (active_key == f'db:{t.id}'),
            'created_at': t.created_at, 'size': len(t.html_content or ''),
            'preview_html': preview, 'has_design': bool(t.design_json),
            'updated': t.updated_at,
        })
    return render(request, 'dashboard/it_support/audit_studio.html', {
        'studio_templates': studio_templates,
        'builtin_files': builtin_files,
        'active_key': active_key,
    })


@it_required
def audit_studio_data(request):
    from django.http import JsonResponse
    import pathlib
    from django.conf import settings as dj_settings
    from admin.dig_portal.models import AuditTemplate
    from admin.audit_portal.pdf_service import FILE_TEMPLATE_MAP

    items = [
        {'kind': 'db', 'id': t.id, 'name': t.name, 'html': t.html_content or '',
         'design': t.design_json or '', 'has_design': bool(t.design_json)}
        for t in AuditTemplate.objects.order_by('-created_at')
    ]
    fs_dir = pathlib.Path(dj_settings.BASE_DIR) / 'templates' / 'audit' / 'audit_templates'
    for key in FILE_TEMPLATE_MAP:
        fp = fs_dir / f'{key}.html'
        if fp.is_file():
            items.append({'kind': 'builtin', 'key': key, 'name': key,
                          'html': fp.read_text(encoding='utf-8', errors='ignore')})
    return JsonResponse({'items': items})


@it_required
def audit_studio_preview(request):
    from django.http import HttpResponse
    if request.method != 'POST':
        return HttpResponse(status=405)
    html = request.POST.get('html_content') or ''
    if len(html.strip()) < 80:
        return HttpResponse('Template HTML too short.', status=400)
    from django.template import Template, Context
    from challans.pdf_service import _render_html_to_pdf
    try:
        rendered = Template(html).render(Context(_audit_studio_sample_context()))
    except Exception as e:
        return HttpResponse(f'Template render error: {e}', status=400, content_type='text/plain')
    pdf = _render_html_to_pdf(rendered)
    if not pdf:
        return HttpResponse('PDF engine failed to render the preview.', status=500)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="audit-studio-preview.pdf"'
    return response


# ---------------------------------------------------------------------------
# Ads Studio: full CRUD for all advertising channels.
# IT Support owns ad content. DIG only selects/prioritizes (dig:ads_select).
# ---------------------------------------------------------------------------
@it_required
def ads_studio(request):
    from admin.dig_portal.models import Banner

    banners = Banner.objects.all().order_by('-priority', '-created_at')
    channel_counts = {}
    for code, _label in Banner.PLACEMENT_CHOICES:
        channel_counts[code] = Banner.objects.filter(placement=code).count()

    return render(request, 'dashboard/it_support/ads_studio.html', {
        'banners': banners,
        'channel_counts': channel_counts,
        'placements': Banner.PLACEMENT_CHOICES,
        'audiences': Banner.AUDIENCE_CHOICES,
        'banner_types': Banner.BANNER_TYPE_CHOICES,
        'active_count': Banner.objects.filter(is_active=True).count(),
    })


@it_required
def ads_studio_action(request):
    """Single POST endpoint for ad create/update/delete/toggle."""
    from admin.dig_portal.models import Banner
    from django.utils import timezone as dj_tz

    if request.method != 'POST':
        return redirect('it_support_portal:ads_studio')

    action = request.POST.get('action', '')
    banner_id = request.POST.get('banner_id')

    def _parse_dt(raw):
        raw = (raw or '').strip()
        if not raw:
            return None
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(raw)
            if dj_tz.is_naive(dt):
                dt = dj_tz.make_aware(dt)
            return dt
        except ValueError:
            return None

    def _form_banner(b):
        b.title = (request.POST.get('title') or '').strip() or b.title
        b.banner_type = request.POST.get('banner_type') or b.banner_type
        b.html_content = request.POST.get('html_content') or ''
        b.image_link = (request.POST.get('image_link') or '').strip()
        b.placement = request.POST.get('placement') or b.placement
        b.audience = request.POST.get('audience') or b.audience
        b.bg_color = (request.POST.get('bg_color') or b.bg_color or '#1F4E79')[:20]
        b.text_color = (request.POST.get('text_color') or b.text_color or '#FFFFFF')[:20]
        b.is_active = request.POST.get('is_active') == 'on'
        try:
            b.priority = max(-100, min(1000, int(request.POST.get('priority') or 0)))
        except (TypeError, ValueError):
            pass
        b.start_at = _parse_dt(request.POST.get('start_at'))
        b.expires_at = _parse_dt(request.POST.get('expires_at'))
        if request.FILES.get('image'):
            b.image = request.FILES['image']
        return b

    if action == 'create':
        title = (request.POST.get('title') or '').strip()
        placement = request.POST.get('placement') or ''
        if not title or placement not in dict(Banner.PLACEMENT_CHOICES):
            messages.error(request, "Title and a valid channel are required.")
            return redirect('it_support_portal:ads_studio')
        banner = Banner(title=title, placement=placement, created_by=request.user)
        banner = _form_banner(banner)
        banner.save()
        AuditLog.write(request, 'ad.create', 'Banner', banner.pk,
                       title=banner.title[:80], placement=banner.placement)
        messages.success(request, f"Ad '{banner.title}' created in the {banner.placement} channel.")
        return redirect('it_support_portal:ads_studio')

    banner = get_object_or_404(Banner, pk=banner_id)
    if action == 'edit':
        banner = _form_banner(banner)
        banner.save()
        AuditLog.write(request, 'ad.edit', 'Banner', banner.pk, title=banner.title[:80])
        messages.success(request, f"Ad '{banner.title}' updated.")
    elif action == 'toggle':
        banner.is_active = not banner.is_active
        banner.save(update_fields=['is_active'])
        AuditLog.write(request, 'ad.toggle', 'Banner', banner.pk,
                       title=banner.title[:80], active=banner.is_active)
        messages.success(request, f"'{banner.title}' is now {'active' if banner.is_active else 'inactive'}.")
    elif action == 'delete':
        AuditLog.write(request, 'ad.delete', 'Banner', banner.pk, title=banner.title[:80])
        messages.success(request, f"Ad '{banner.title}' deleted.")
        banner.delete()
    else:
        messages.error(request, "Unknown ad action.")
    return redirect('it_support_portal:ads_studio')
