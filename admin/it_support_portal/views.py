import json
import platform

from django.conf import settings as django_settings
from django.core.mail import EmailMessage, get_connection
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from datetime import timedelta

from accounts.models import AdminPasswordResetRequest, User
from accounts.decorators import it_required, role_required
from challans.models import Challan
from detections.models import Detection
from cameras.models import Camera
from admin.dig_portal.models import AuditLog, Notification, SystemSettings
from detections.ai import is_models_available, get_model_info
from payments.models import PaymentTransaction

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
    detections_confirmed = Detection.objects.filter(status=Detection.CONFIRMED).count()
    detections_pending = Detection.objects.filter(status=Detection.PENDING).count()

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

    db_status = _db_status()
    gateway_status = _gateway_status()

    return render(request, 'dashboard/it_support/dashboard.html', {
        'db_status': db_status,
        'gateway_status': gateway_status,
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


@it_required
def audit_templates_manage(request):
    from admin.audit_portal.audit_pdf import (BUILTIN_TEMPLATES,
                                              generate_audit_pdf,
                                              get_active_template_key,
                                              get_audit_templates,
                                              get_template_preview_html)
    from admin.dig_portal.models import (AuditPDFTemplate, AuditLog,
                                         SystemSettings)


    sample_key = (request.GET.get('sample') or '').strip()
    if sample_key:
        if sample_key not in {t['key'] for t in get_audit_templates()}:
            return HttpResponse('Unknown template key.', status=404)
        pdf_bytes = generate_audit_pdf('dashboard', {}, sample_key)
        if not pdf_bytes:
            return HttpResponse('PDF engine unavailable.', status=503)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="audit_sample_{sample_key.replace(":", "_")}.pdf"')
        return resp

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        sys_settings = SystemSettings.get()

        if action == 'create_audit_template':
            name = (request.POST.get('template_name') or '').strip()
            description = (request.POST.get('template_description') or '').strip()
            html = (request.POST.get('html_content') or '').strip()
            if not name or not html:
                messages.error(request, "Template name and HTML content are required.")
                return redirect('it_support_portal:audit_templates')
            obj = AuditPDFTemplate.objects.create(
                name=name, description=description, html_content=html,
                is_active=False, uploaded_by=request.user)
            AuditLog.write(request, 'audit_template.create', 'AuditPDFTemplate', obj.id,
                           name=obj.name)
            messages.success(request, f"Audit template '{obj.name}' created.")
            return redirect('it_support_portal:audit_templates')

        if action == 'update_audit_template':
            tid = request.POST.get('template_id') or ''
            obj = AuditPDFTemplate.objects.filter(pk=tid).first()
            if not obj:
                messages.error(request, "Template not found.")
                return redirect('it_support_portal:audit_templates')
            obj.name = (request.POST.get('template_name') or '').strip() or obj.name
            obj.description = (request.POST.get('template_description') or '').strip()
            obj.html_content = (request.POST.get('html_content') or '').strip() or obj.html_content
            obj.save()
            AuditLog.write(request, 'audit_template.update', 'AuditPDFTemplate', obj.id,
                           name=obj.name)
            messages.success(request, f"Template '{obj.name}' updated.")
            return redirect('it_support_portal:audit_templates')

        if action == 'delete_audit_template':
            tid = request.POST.get('template_id') or ''
            obj = AuditPDFTemplate.objects.filter(pk=tid).first()
            if not obj:
                messages.error(request, "Template not found.")
                return redirect('it_support_portal:audit_templates')
            name = obj.name
            was_active = (sys_settings.audit_pdf_template == f'db:{obj.pk}')
            obj.delete()
            if was_active:
                sys_settings.audit_pdf_template = 'government_classic'
                sys_settings.save(update_fields=['audit_pdf_template'])
            AuditLog.write(request, 'audit_template.delete', 'AuditPDFTemplate', None,
                           name=name)
            msg = f"Template '{name}' deleted."
            if was_active:
                msg += " Active layout reverted to 'government_classic'."
            messages.success(request, msg)
            return redirect('it_support_portal:audit_templates')

        if action == 'activate_audit_template':
            key = (request.POST.get('template_key') or '').strip()
            valid_keys = {t['key'] for t in get_audit_templates()}
            if key not in valid_keys:
                messages.error(request, "Unknown template key.")
                return redirect('it_support_portal:audit_templates')
            sys_settings.audit_pdf_template = key
            sys_settings.save(update_fields=['audit_pdf_template'])
            if key.startswith('db:'):
                AuditPDFTemplate.objects.filter(pk=key[3:]).update(is_active=True)
            AuditLog.write(request, 'audit_template.activate', 'SystemSettings', None,
                           template=key)
            messages.success(request, f"Active audit PDF template set to '{key}'.")
            return redirect('it_support_portal:audit_templates')

        messages.error(request, "Unrecognised audit template action.")
        return redirect('it_support_portal:audit_templates')

    templates = []
    for t in get_audit_templates():
        item = dict(t)
        item['preview_html'] = get_template_preview_html(t['key'])
        templates.append(item)
    db_templates = list(AuditPDFTemplate.objects.all())
    for ct in db_templates:
        ct.preview_html = get_template_preview_html(f'db:{ct.pk}')
    return render(request, 'dashboard/it_support/audit_templates.html', {
        'templates': templates,
        'db_templates': db_templates,
        'active_template_key': get_active_template_key(),
        'builtin_count': len(BUILTIN_TEMPLATES),
        'db_count': len(db_templates),
    })


def _db_status():
    engine = connection.settings_dict['ENGINE'].split('.')[-1]
    labels = {
        'postgresql': 'PostgreSQL',
        'sqlite3': 'SQLite',
        'mysql': 'MySQL',
        'oracle': 'Oracle',
    }
    label = labels.get(engine, engine)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return {'engine': engine, 'label': label, 'ok': True, 'error': ''}
    except Exception as exc:
        return {'engine': engine, 'label': label, 'ok': False, 'error': str(exc)}


def _gateway_status():
    try:
        sys_settings = SystemSettings.get()
        mode = sys_settings.integration_mode
    except Exception:
        mode = 'demo'
    methods = PaymentMethod.objects.filter(status=PaymentMethod.STATUS_ACTIVE).count()
    return {'mode': mode, 'methods': methods}


def _age_text(delta_minutes):
    if delta_minutes is None:
        return 'Never'
    if delta_minutes < 1:
        return f'{max(1, int(delta_minutes * 60))}s ago'
    if delta_minutes < 60:
        return f'{int(delta_minutes)}m ago'
    hours = delta_minutes / 60.0
    if hours < 24:
        return f'{int(hours)}h {int(delta_minutes % 60)}m ago'
    return f'{int(hours // 24)}d {int(hours % 24)}h ago'


def _camera_freshness_stats():
    now = timezone.now()
    cameras = list(Camera.objects.all().order_by('camera_id'))
    buckets = {'fresh': [], 'stale': [], 'dead': [], 'never': []}
    for cam in cameras:
        if cam.last_frame_at:
            frame_age = (now - cam.last_frame_at).total_seconds() / 60.0
            if frame_age < 5:
                bucket = 'fresh'
            elif frame_age <= 60:
                bucket = 'stale'
            else:
                bucket = 'dead'
        else:
            frame_age = None
            bucket = 'never'
        health_age = (
            (now - cam.last_health_check).total_seconds() / 60.0
            if cam.last_health_check else None
        )
        cam.it_frame_age_minutes = frame_age
        cam.it_frame_age_text = _age_text(frame_age)
        cam.it_frame_bucket = bucket
        cam.it_health_age_text = _age_text(health_age)
        buckets[bucket].append(cam)
    severity = {'dead': 0, 'never': 1, 'stale': 2, 'fresh': 3}
    cameras.sort(key=lambda c: (severity[c.it_frame_bucket], c.camera_id))
    total = len(cameras)
    fresh = len(buckets['fresh'])
    return {
        'cameras': cameras,
        'buckets': buckets,
        'total': total,
        'fresh': fresh,
        'stale': len(buckets['stale']),
        'dead': len(buckets['dead']),
        'never': len(buckets['never']),
        'fresh_pct': round(fresh * 100.0 / total, 1) if total else 0,
    }


def _run_camera_heartbeat_scan(timeout_seconds=120):
    cutoff = timezone.now() - timedelta(seconds=timeout_seconds)
    stale = Camera.objects.filter(is_active=True, health_status='online').filter(
        Q(last_health_check__lt=cutoff) | Q(last_health_check__isnull=True)
    )
    return stale.update(health_status='offline')


@role_required('IT', 'DIG')
def payment_transactions(request):
    transactions = PaymentTransaction.objects.select_related('challan').order_by('-created_at')

    status_filter = (request.GET.get('status') or '').strip()
    provider_filter = (request.GET.get('provider') or '').strip()
    q = (request.GET.get('q') or '').strip()

    if status_filter:
        transactions = transactions.filter(status=status_filter)
    if provider_filter:
        transactions = transactions.filter(provider__iexact=provider_filter)
    if q:
        transactions = transactions.filter(
            Q(txn_ref__icontains=q) | Q(ticket_no__icontains=q) | Q(gateway_ref__icontains=q)
        )

    paginator = Paginator(transactions, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    query_params = {}
    if status_filter:
        query_params['status'] = status_filter
    if provider_filter:
        query_params['provider'] = provider_filter
    if q:
        query_params['q'] = q
    filter_qs = urlencode(query_params)

    last_7d = timezone.now() - timedelta(days=7)
    success_total = PaymentTransaction.objects.filter(
        status=PaymentTransaction.STATUS_SUCCESS
    ).aggregate(total=Sum('amount'))['total'] or 0
    failed_7d = PaymentTransaction.objects.filter(
        status=PaymentTransaction.STATUS_FAILED, created_at__gte=last_7d
    ).count()
    provider_breakdown = list(
        PaymentTransaction.objects.values('provider')
        .annotate(count=Count('id'), volume=Sum('amount'))
        .order_by('-count')
    )
    status_counts = {
        code: PaymentTransaction.objects.filter(status=code).count()
        for code, _label in PaymentTransaction.STATUS_CHOICES
    }
    status_rows = [
        {'code': code, 'label': label, 'count': status_counts.get(code, 0)}
        for code, label in PaymentTransaction.STATUS_CHOICES
    ]

    return render(request, 'dashboard/it_support/payment_transactions.html', {
        'page_obj': page_obj,
        'transactions': page_obj.object_list,
        'status_filter': status_filter,
        'provider_filter': provider_filter,
        'q': q,
        'filter_qs': filter_qs,
        'status_choices': PaymentTransaction.STATUS_CHOICES,
        'status_rows': status_rows,
        'status_counts': status_counts,
        'success_total': success_total,
        'failed_7d': failed_7d,
        'provider_breakdown': provider_breakdown,
        'pending_count': status_counts.get(PaymentTransaction.STATUS_PENDING, 0),
        'total_count': PaymentTransaction.objects.count(),
    })


@role_required('IT', 'DIG')
def payment_transaction_detail(request, txn_id):
    txn = get_object_or_404(
        PaymentTransaction.objects.select_related('challan'), pk=txn_id
    )

    if request.method == 'POST':
        if (request.POST.get('action') or '').strip() == 'mark_failed':
            if txn.status != PaymentTransaction.STATUS_PENDING:
                messages.error(
                    request,
                    f"Only pending transactions can be marked as failed. Current status: {txn.get_status_display()}."
                )
                return redirect('it_support_portal:payment_transaction_detail', txn_id=txn.id)
            txn.status = PaymentTransaction.STATUS_FAILED
            txn.save(update_fields=['status', 'updated_at'])
            AuditLog.write(
                request, 'payment.mark_failed', 'PaymentTransaction', txn.id,
                ticket_no=txn.ticket_no, txn_ref=txn.txn_ref,
                provider=txn.provider, amount=str(txn.amount),
            )
            detail_url = reverse('dig:payment_list')
            Notification.objects.bulk_create([
                Notification(
                    recipient=dig_user,
                    title='Payment transaction marked failed',
                    message=(
                        f"IT Support marked transaction {txn.txn_ref or txn.ticket_no} "
                        f"({txn.provider}, PKR {txn.amount}) as failed."
                    ),
                    category='system',
                    target_url=detail_url,
                )
                for dig_user in User.objects.filter(role='DIG', is_active=True)
            ])
            messages.success(
                request,
                f"Transaction {txn.txn_ref or txn.ticket_no} marked as failed. DIG office notified."
            )
        return redirect('it_support_portal:payment_transaction_detail', txn_id=txn.id)

    raw_response_pretty = ''
    if txn.raw_response:
        try:
            raw_response_pretty = json.dumps(txn.raw_response, indent=2, default=str)
        except Exception:
            raw_response_pretty = str(txn.raw_response)

    return render(request, 'dashboard/it_support/payment_transaction_detail.html', {
        'txn': txn,
        'raw_response_pretty': raw_response_pretty,
        'can_mark_failed': txn.status == PaymentTransaction.STATUS_PENDING,
    })


@role_required('IT', 'DIG')
def camera_heartbeats(request):
    stats = _camera_freshness_stats()
    bucket_filter = (request.GET.get('bucket') or '').strip()
    cameras = stats['cameras']
    if bucket_filter in ('fresh', 'stale', 'dead', 'never'):
        cameras = stats['buckets'][bucket_filter]
    return render(request, 'dashboard/it_support/camera_heartbeats.html', {
        'stats': stats,
        'cameras': cameras,
        'bucket_filter': bucket_filter,
    })


@role_required('IT', 'DIG')
def camera_heartbeat_run(request):
    if request.method != 'POST':
        return redirect('it_support_portal:camera_heartbeats')
    marked = _run_camera_heartbeat_scan()
    AuditLog.write(request, 'camera.healthcheck_run', 'Camera', None, marked_offline=marked)
    if marked:
        messages.success(request, f"Heartbeat scan complete: {marked} camera(s) marked offline.")
    else:
        messages.success(request, "Heartbeat scan complete: every online camera has a fresh heartbeat.")
    return redirect('it_support_portal:camera_heartbeats')


@it_required
def system_health(request):
    camera_stats = _camera_freshness_stats()
    db_status = _db_status()
    gateway_status = _gateway_status()
    sys_settings = SystemSettings.get()
    tc = sys_settings.template_config or {}
    smtp_config = {
        'host': (tc.get('smtp_host') or '').strip(),
        'port': tc.get('smtp_port') or 587,
        'user': (tc.get('smtp_user') or '').strip(),
        'from': (tc.get('smtp_from') or '').strip(),
        'tls': str(tc.get('smtp_tls', '1')) not in ('0', 'false', 'False', 'no', ''),
    }
    return render(request, 'dashboard/it_support/system_health.html', {
        'db_challans': Challan.objects.count(),
        'db_detections': Detection.objects.count(),
        'db_users': User.objects.count(),
        'db_cameras': Camera.objects.count(),
        'db_status': db_status,
        'gateway_status': gateway_status,
        'camera_stats': camera_stats,
        'ai_available': is_models_available(),
        'model_info': get_model_info(),
        'email_enabled': sys_settings.email_enabled,
        'smtp_config': smtp_config,
        'python_version': platform.python_version(),
        'platform': platform.platform(),
        'integration_mode': sys_settings.integration_mode,
    })


@it_required
def smtp_test(request):
    if request.method != 'POST':
        return redirect('it_support_portal:settings_edit')

    sys_settings = SystemSettings.get()
    recipient = (request.user.email or '').strip()
    if not recipient:
        messages.error(request, "Your account has no email address on file, so a test email cannot be sent.")
        return redirect('it_support_portal:settings_edit')

    tc = sys_settings.template_config or {}
    host = (tc.get('smtp_host') or '').strip()
    try:
        port = int(tc.get('smtp_port') or 587)
    except (TypeError, ValueError):
        port = 587
    username = (tc.get('smtp_user') or '').strip()
    password = tc.get('smtp_password') or ''
    from_email = (tc.get('smtp_from') or '').strip() or django_settings.DEFAULT_FROM_EMAIL
    use_tls = str(tc.get('smtp_tls', '1')) not in ('0', 'false', 'False', 'no', '')

    subject = 'Safe City SMTP test'
    body = (
        'This is a test email sent from the IT Support portal.\n\n'
        f'SMTP host: {host or "default Django email backend"}\n'
        f'SMTP port: {port}\n'
        f'TLS: {"yes" if use_tls else "no"}\n'
        f'Triggered by: {request.user.display_name} ({request.user.username})\n'
    )

    try:
        if host:
            mail_connection = get_connection(
                'django.core.mail.backends.smtp.EmailBackend',
                host=host, port=port,
                username=username or None, password=password or None,
                use_tls=use_tls, timeout=10, fail_silently=False,
            )
        else:
            mail_connection = get_connection()
        email = EmailMessage(subject, body, from_email, [recipient], connection=mail_connection)
        email.send()
        AuditLog.write(
            request, 'settings.smtp_test', 'SystemSettings', sys_settings.id,
            host=host or 'default', recipient=recipient, outcome='sent',
        )
        messages.success(
            request,
            f"Test email sent to {recipient} via {host or 'the default email backend'}."
        )
    except Exception as exc:
        AuditLog.write(
            request, 'settings.smtp_test', 'SystemSettings', sys_settings.id,
            host=host or 'default', recipient=recipient, outcome='failed', error=str(exc)[:300],
        )
        messages.error(request, f"SMTP connection failed: {exc}")

    return redirect('it_support_portal:settings_edit')


@role_required('IT', 'DIG')
def reset_requests(request):
    valid_statuses = [code for code, _label in AdminPasswordResetRequest.STATUS_CHOICES]
    status_filter = (request.GET.get('status') or '').strip()

    requests_qs = AdminPasswordResetRequest.objects.select_related('target_user', 'resolved_by')
    if status_filter in valid_statuses:
        requests_qs = requests_qs.filter(status=status_filter)
    requests_qs = requests_qs.order_by('-created_at')

    status_counts = {
        code: AdminPasswordResetRequest.objects.filter(status=code).count()
        for code in valid_statuses
    }
    status_rows = [
        {'code': code, 'label': label, 'count': status_counts.get(code, 0)}
        for code, label in AdminPasswordResetRequest.STATUS_CHOICES
    ]
    return render(request, 'dashboard/it_support/reset_requests.html', {
        'requests': requests_qs[:200],
        'status_filter': status_filter,
        'status_choices': AdminPasswordResetRequest.STATUS_CHOICES,
        'status_rows': status_rows,
        'status_counts': status_counts,
        'pending_count': status_counts.get(AdminPasswordResetRequest.STATUS_PENDING, 0),
        'resolved_count': status_counts.get(AdminPasswordResetRequest.STATUS_RESOLVED, 0),
        'cancelled_count': status_counts.get(AdminPasswordResetRequest.STATUS_CANCELLED, 0),
        'total_count': AdminPasswordResetRequest.objects.count(),
    })


