import datetime
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db.models import Count, Sum, Q
from django.utils import timezone

from accounts.decorators import role_required
from accounts.models import User
from challans.models import Challan
from appeals.models import ChallanAppeal
from admin.dig_portal.models import AuditLog


AUDIT_ROLES = ('AUDIT', 'DIG')


@role_required(*AUDIT_ROLES)
def dashboard(request):
    now = timezone.now()
    today = now.date()
    last_7d = now - datetime.timedelta(days=7)

    total_challans = Challan.objects.count()
    total_paid = Challan.objects.filter(payment_status='PAID').count()
    total_unpaid = Challan.objects.filter(payment_status='UNPAID').count()
    total_voided = Challan.objects.filter(payment_status='VOIDED').count()
    revenue_collected = Challan.objects.filter(payment_status='PAID').aggregate(t=Sum('fine_amount'))['t'] or 0
    revenue_pending = Challan.objects.filter(payment_status='UNPAID').aggregate(t=Sum('fine_amount'))['t'] or 0
    audit_entries = AuditLog.objects.count()
    audit_24h = AuditLog.objects.filter(timestamp__gte=now - datetime.timedelta(hours=24)).count()
    audit_7d = AuditLog.objects.filter(timestamp__gte=last_7d).count()
    anomalies = _detect_anomalies()
    audit_categories = [
        ('user.create',          'Users Created',         'fa-user-plus',     'primary'),
        ('user.toggle',          'Users Toggled',         'fa-user-check',    'info'),
        ('admin.edit',          'Admins Updated',        'fa-user-shield',   'violet'),
        ('admin.toggle',         'Admins Toggled',        'fa-shield-halved', 'warning'),
        ('camera.add',           'Cameras Added',         'fa-video',         'success'),
        ('camera.edit',          'Cameras Updated',       'fa-pen-to-square', 'info'),
        ('camera.delete',        'Cameras Deleted',       'fa-trash',         'danger'),
        ('camera.toggle',        'Cameras Toggled',       'fa-toggle-on',     'warning'),
        ('challan.manual_create','Manual Challans',       'fa-file-circle-plus', 'primary'),
        ('detection.confirm',    'Detections Confirmed',  'fa-check',         'success'),
        ('detection.reject',     'Detections Rejected',   'fa-xmark',         'danger'),
        ('detection.flag',       'Detections Flagged',    'fa-flag',          'warning'),
        ('detection.manual_annotate', 'Manual Annotations', 'fa-pen-fancy',   'violet'),
        ('banner.create',        'Banners Created',       'fa-image',         'info'),
        ('banner.update',        'Banners Updated',       'fa-pen',           'primary'),
        ('banner.delete',        'Banners Deleted',       'fa-trash-can',     'danger'),
        ('payment_settings.update', 'Payment Config Changes', 'fa-credit-card', 'warning'),
        ('payment_method.create','Payment Methods Added', 'fa-plus',          'success'),
        ('payment_method.update','Payment Methods Updated', 'fa-pen',         'info'),
        ('payment_method.toggle','Payment Methods Toggled', 'fa-toggle-on',   'warning'),
        ('payment_method.delete','Payment Methods Removed', 'fa-trash',      'danger'),
        ('ssp.approve_high_value','SSP Approvals',        'fa-stamp',         'primary'),
        ('ssp.appeal_decision',  'SSP Appeal Decisions',  'fa-gavel',         'info'),
        ('supervisor.appeal_override', 'Supervisor Overrides', 'fa-arrows-rotate', 'warning'),
        ('appeal.submit',        'Appeals Submitted',     'fa-envelope',      'success'),
        ('appeal.escalate',      'Appeals Escalated',     'fa-arrow-up',      'danger'),
    ]
    category_counts = []
    for action, label, icon, color in audit_categories:
        cnt = AuditLog.objects.filter(action=action).count()
        category_counts.append({'action': action, 'label': label, 'icon': icon, 'color': color, 'count': cnt})

    top_categories = sorted(category_counts, key=lambda c: c['count'], reverse=True)[:8]
    cat_labels = [c['label'] for c in top_categories]
    cat_counts = [c['count'] for c in top_categories]

    days_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_start = datetime.datetime.combine(day, datetime.time.min).replace(tzinfo=datetime.timezone.utc)
        day_end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time.min).replace(tzinfo=datetime.timezone.utc)
        cnt = AuditLog.objects.filter(timestamp__gte=day_start, timestamp__lt=day_end).count()
        days_data.append({'label': day.strftime('%a'), 'count': cnt})

    recent_logs = AuditLog.objects.select_related('actor').order_by('-timestamp')[:12]

    challan_status = {
        'paid': total_paid,
        'unpaid': total_unpaid,
        'voided': total_voided,
    }

    return render(request, 'dashboard/audit/dashboard.html', {
        'total_challans': total_challans, 'total_paid': total_paid,
        'total_unpaid': total_unpaid, 'total_voided': total_voided,
        'revenue_collected': revenue_collected, 'revenue_pending': revenue_pending,
        'audit_entries': audit_entries, 'audit_24h': audit_24h, 'audit_7d': audit_7d,
        'anomalies': anomalies,
        'category_counts': category_counts,
        'cat_labels': cat_labels,
        'cat_counts': cat_counts,
        'days_data': days_data,
        'recent_logs': recent_logs,
        'challan_status': challan_status,
    })


def _detect_anomalies():
    anomalies = []
    officer_dismissals = (
        User.objects.filter(role='OFFICER')
        .annotate(
            dismissed=Count(
                'appeals_reviewed',
                filter=Q(appeals_reviewed__status=ChallanAppeal.REJECTED),
            )
        )
        .filter(dismissed__gte=5)
        .order_by('-dismissed')
    )
    for o in officer_dismissals:
        anomalies.append({
            'type': 'HIGH_DISMISSAL_RATE',
            'severity': 'HIGH' if o.dismissed >= 10 else 'MEDIUM',
            'description': f"Officer {o.display_name} has rejected {o.dismissed} appeals",
            'target': o.username,
        })
    orphan_payments = Challan.objects.filter(payment_status='PAID', paid_at__isnull=True).count()
    if orphan_payments > 0:
        anomalies.append({
            'type': 'ORPHAN_PAYMENT', 'severity': 'HIGH',
            'description': f"{orphan_payments} challans marked PAID without paid_at timestamp",
            'target': '-',
        })
    zero_challans = Challan.objects.filter(fine_amount=0).count()
    if zero_challans > 0:
        anomalies.append({
            'type': 'ZERO_AMOUNT_CHALLAN', 'severity': 'LOW',
            'description': f"{zero_challans} challans with zero fine amount",
            'target': '-',
        })
    return anomalies


@role_required(*AUDIT_ROLES)
def anomaly_alerts(request):
    anomalies = _detect_anomalies()
    return render(request, 'dashboard/audit/anomaly_alerts.html', {'anomalies': anomalies})


@role_required(*AUDIT_ROLES)
def compliance_reports(request):
    by_type = dict(Challan.objects.values('violation_type').annotate(c=Count('id')).values_list('violation_type', 'c'))
    by_status = dict(Challan.objects.values('payment_status').annotate(c=Count('id')).values_list('payment_status', 'c'))
    by_location = dict(Challan.objects.values('location').annotate(c=Count('id'))
                       .order_by('-c')[:15].values_list('location', 'c'))
    return render(request, 'dashboard/audit/compliance_reports.html', {
        'by_type': by_type, 'by_status': by_status,
        'by_location': by_location,
    })


@role_required(*AUDIT_ROLES)
def financial_audit(request):
    payments = Challan.objects.filter(payment_status='PAID').order_by('-paid_at')[:100]
    total_collected = Challan.objects.filter(payment_status='PAID').aggregate(t=Sum('fine_amount'))['t'] or 0
    return render(request, 'dashboard/audit/financial_audit.html', {
        'payments': payments,
        'total_collected': total_collected,
    })


@role_required(*AUDIT_ROLES)
def operational_audit(request):
    logs = list(AuditLog.objects.select_related('actor').order_by('-timestamp')[:200])
    return render(request, 'dashboard/audit/operational_audit.html', {'logs': logs})


def _filtered_audit(request, template, actions, title, icon):
    qs = list(
        AuditLog.objects.filter(action__in=actions)
        .select_related('actor')
        .order_by('-timestamp')[:300]
    )
    return render(request, template, {
        'logs': qs,
        'title': title,
        'icon': icon,
        'actions': actions,
        'count': len(qs),
    })


@role_required(*AUDIT_ROLES)
def user_activity(request):
    return _filtered_audit(
        request,
        'dashboard/audit/user_activity.html',
        ['user.create', 'user.toggle', 'user.delete', 'user.profile_edit',
         'user.password_change', 'admin.create', 'admin.toggle',
         'supervisor.leave_grant'],
        'User Activity Audit',
        'fa-users',
    )


@role_required(*AUDIT_ROLES)
def auth_events(request):
    qs = AuditLog.objects.filter(
        Q(action__startswith='auth.')
        | Q(action__startswith='login.')
        | Q(action__startswith='password_reset')
        | Q(action='user.password_change')
        | Q(action='staff.password_change')
        | Q(action='account.locked')
    ).order_by('-timestamp')[:300]
    return render(request, 'dashboard/audit/auth_events.html', {
        'logs': qs,
        'title': 'Authentication Events Audit',
        'icon': 'fa-key',
        'count': qs.count(),
    })


@role_required(*AUDIT_ROLES)
def permission_changes(request):
    return _filtered_audit(
        request,
        'dashboard/audit/permission_changes.html',
        ['user.create', 'user.toggle', 'user.edit', 'admin.create', 'admin.toggle',
         'admin.edit'],
        'Permission Changes Audit',
        'fa-shield-halved',
    )


@role_required(*AUDIT_ROLES)
def camera_changes(request):
    return _filtered_audit(
        request,
        'dashboard/audit/changes_log.html',
        ['camera.add', 'camera.edit', 'camera.delete',
         'camera.toggle', 'camera.set_online', 'camera.auto_delete_empty',
         'camera.regenerate_token', 'camera.assign', 'camera.unassign'],
        'Camera Changes Audit',
        'fa-video',
    )


@role_required(*AUDIT_ROLES)
def challan_changes(request):
    return _filtered_audit(
        request,
        'dashboard/audit/changes_log.html',
        ['challan.manual_create', 'challan.create', 'challan.update',
         'challan.void', 'challan.mark_paid', 'challan.fine_edit',
         'challan.record_payment', 'challan.bulk_fine',
         'challan.delete', 'ssp.approve_high_value'],
        'Challan Changes Audit',
        'fa-file-invoice',
    )


@role_required(*AUDIT_ROLES)
def payment_changes(request):
    return _filtered_audit(
        request,
        'dashboard/audit/changes_log.html',
        ['payment_settings.update', 'payment_method.create',
         'payment_method.update', 'payment_method.toggle',
         'payment_method.delete', 'challan.record_payment',
         'challan.mark_paid'],
        'Payment Changes Audit',
        'fa-credit-card',
    )


@role_required(*AUDIT_ROLES)
def banner_changes(request):
    return _filtered_audit(
        request,
        'dashboard/audit/changes_log.html',
        ['banner.create', 'banner.update', 'banner.delete', 'banner.toggle'],
        'Banner Changes Audit',
        'fa-image',
    )


@role_required(*AUDIT_ROLES)
def alert_changes(request):
    return _filtered_audit(
        request,
        'dashboard/audit/changes_log.html',
        ['alert.create', 'alert.update', 'alert.delete', 'alert.toggle',
         'broadcast.send'],
        'Alert Changes Audit',
        'fa-bell',
    )


@role_required(*AUDIT_ROLES)
def audit_export(request):
    import csv
    from django.http import HttpResponse
    from django.utils import timezone as tz

    fmt = (request.GET.get('format') or 'csv').lower()
    kind = (request.GET.get('kind') or 'operational').lower()
    action_map = {
        'operational': None,
        'user-activity': ['user.create', 'user.toggle', 'user.delete', 'user.profile_edit',
                          'user.password_change', 'admin.create', 'admin.toggle'],
        'auth-events': None,
        'permission-changes': ['admin.permissions_update', 'admin.create', 'admin.toggle', 'admin.delete'],
        'camera-changes': ['camera.create', 'camera.edit', 'camera.delete', 'camera.toggle'],
        'challan-changes': ['challan.mark_paid', 'challan.mark_unpaid', 'challan.record_payment',
                            'challan.bulk_fine', 'blacklist.add'],
        'financial': None,
    }
    qs = AuditLog.objects.select_related('actor').order_by('-timestamp')
    actions = action_map.get(kind)
    if actions:
        qs = qs.filter(action__in=actions)
    elif kind == 'auth-events':
        from django.db.models import Q
        qs = qs.filter(
            Q(action__startswith='auth.') | Q(action__startswith='login.') |
            Q(action='user.password_change') | Q(action='staff.password_change')
        )
    rows = list(qs[:5000])

    if fmt == 'csv':
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="safecity_audit_{kind}.csv"'
        w = csv.writer(resp)
        w.writerow(['Timestamp', 'Actor', 'Action', 'Target model', 'Target ID', 'Details', 'IP'])
        for e in rows:
            det = e.details if isinstance(getattr(e, 'details', None), dict) else (e.details or '')
            w.writerow([
                e.timestamp.isoformat() if e.timestamp else '',
                (e.actor.username if e.actor else ''),
                e.action,
                e.target_model or '',
                e.target_id or '',
                str(det)[:500],
                getattr(e, 'ip_address', '') or '',
            ])
        return resp

    body_rows = []
    for e in rows[:2000]:
        actor = e.actor.username if e.actor else '-'
        body_rows.append(
            f"<tr><td>{e.timestamp}</td><td>{actor}</td><td>{e.action}</td>"
            f"<td>{e.target_model or ''} #{e.target_id or ''}</td></tr>"
        )
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>SafeCity Audit Export</title>"
        "<style>body{font-family:Arial,sans-serif;font-size:11px;margin:24px}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;text-align:left}"
        "th{background:#f1f5f9}@media print{body{margin:0}}</style></head><body>"
        f"<h1>SafeCity Audit - {kind}</h1><p>Generated {tz.now().strftime('%Y-%m-%d %H:%M')} · {len(body_rows)} rows</p>"
        "<table><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th></tr></thead><tbody>"
        + ''.join(body_rows) +
        "</tbody></table><script>window.onload=function(){window.print();}</script></body></html>"
    )
    resp = HttpResponse(html, content_type='text/html; charset=utf-8')
    resp['Content-Disposition'] = f'inline; filename="safecity_audit_{kind}.pdf.html"'
    return resp



@role_required(*AUDIT_ROLES)
def login_events(request):
    """Every authentication attempt with account, IP and device fingerprint."""
    from admin.dig_portal.models import LoginEvent
    from django.utils import timezone as tz
    import datetime as _dt

    qs = LoginEvent.objects.select_related('user').order_by('-timestamp')
    f_user = (request.GET.get('user') or '').strip()
    f_outcome = (request.GET.get('outcome') or '').strip()
    f_ip = (request.GET.get('ip') or '').strip()
    f_days = (request.GET.get('days') or '').strip()
    if f_user:
        qs = qs.filter(Q(user__username__icontains=f_user) | Q(username_attempted__icontains=f_user))
    if f_outcome == 'success':
        qs = qs.filter(success=True)
    elif f_outcome == 'failed':
        qs = qs.filter(success=False)
    if f_ip:
        qs = qs.filter(ip_address__icontains=f_ip)
    if f_days.isdigit() and int(f_days) > 0:
        since = tz.now() - _dt.timedelta(days=int(f_days))
        qs = qs.filter(timestamp__gte=since)

    total = qs.count()
    events = list(qs[:400])
    success_count = sum(1 for e in events if e.success)
    unique_ips = len({e.ip_address for e in events if e.ip_address})
    unique_users = len({e.username_attempted for e in events})
    return render(request, 'dashboard/audit/login_events.html', {
        'events': events,
        'total': total,
        'success_count': success_count,
        'failed_count': len(events) - success_count,
        'unique_ips': unique_ips,
        'unique_users': unique_users,
        'filters': {'user': f_user, 'outcome': f_outcome, 'ip': f_ip, 'days': f_days},
    })


@role_required(*AUDIT_ROLES)
def login_events_export(request):
    import csv
    from django.http import HttpResponse
    from admin.dig_portal.models import LoginEvent
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="safecity_login_events.csv"'
    w = csv.writer(resp)
    w.writerow(['Timestamp', 'Account', 'Portal', 'Outcome', 'Failure reason',
                'IP address', 'Browser', 'OS', 'Device type', 'Device', 'Session'])
    for e in LoginEvent.objects.select_related('user').order_by('-timestamp')[:10000]:
        w.writerow([
            e.timestamp.isoformat() if e.timestamp else '',
            (e.user.username if e.user else e.username_attempted),
            e.get_portal_display(),
            'SUCCESS' if e.success else 'FAILED',
            e.failure_reason or '',
            e.ip_address or '',
            e.browser or '',
            e.os or '',
            e.device_type or '',
            e.device_summary or '',
            e.session_key or '',
        ])
    return resp


@role_required(*AUDIT_ROLES)
def uploads_log(request):
    """Audit of every upload: videos (with tamper-evident hashes), template
    uploads, signature uploads and backup downloads."""
    from video_processor.models import VideoUpload
    from admin.dig_portal.models import ChallanTemplate

    uploads = [
        {
            'kind': 'video', 'id': u.id, 'label': u.original_filename or f'upload #{u.id}',
            'by': u.uploaded_by, 'at': u.created_at, 'sha256': u.file_sha256 or '-',
            'meta': f"{u.camera.camera_id if u.camera else '-'} · {u.get_status_display()}",
            'size_mb': round(u.video_file.size / 1048576, 2) if u.video_file else 0,
            'frames': u.total_frames_extracted,
            'bursts': u.burst_evidence_collected,
        }
        for u in VideoUpload.objects.select_related('camera', 'uploaded_by').order_by('-created_at')[:200]
    ]
    template_logs = AuditLog.objects.filter(
        Q(action__startswith='challan_template') | Q(action__startswith='challan_studio')
        | Q(action__startswith='audit_studio') | Q(action__startswith='audit_template')
    ).select_related('actor').order_by('-timestamp')[:200]
    for log in template_logs:
        uploads.append({
            'kind': 'template', 'id': log.target_id or '', 'label': log.details.get('name') or log.action,
            'by': log.actor, 'at': log.timestamp, 'sha256': '-',
            'meta': log.action, 'size_mb': 0, 'frames': 0, 'bursts': 0,
        })
    uploads.sort(key=lambda x: x['at'], reverse=True)
    video_count = VideoUpload.objects.count()
    template_count = ChallanTemplate.objects.count()
    return render(request, 'dashboard/audit/uploads_log.html', {
        'uploads': uploads[:400],
        'video_count': video_count,
        'template_count': template_count,
    })


@role_required(*AUDIT_ROLES)
def generate_document(request):
    """Auditor: generate a signed, government-style audit document."""
    import datetime
    from django import forms
    from admin.audit_portal.pdf_service import (
        FILE_TEMPLATE_MAP, generate_audit_pdf, save_audit_document, AUDIT_TEMPLATE_META,
    )
    from admin.dig_portal.models import SystemSettings, AuditTemplate, AuditDocument

    sys_settings = SystemSettings.get()
    active_key = sys_settings.audit_template or 'audit_summary_report'

    today = datetime.date.today()
    initial = {'period_from': today - datetime.timedelta(days=30), 'period_to': today}

    class DocForm(forms.Form):
        period_from = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
        period_to = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
        title = forms.CharField(max_length=200, required=False,
                                widget=forms.TextInput(attrs={'placeholder': 'Optional custom title'}))
        template_key = forms.ChoiceField(choices=[(k, AUDIT_TEMPLATE_META.get(k, (k,))[0]) for k in FILE_TEMPLATE_MAP])

    if request.method == 'POST':
        form = DocForm(request.POST)
        if form.is_valid():
            f, t = form.cleaned_data['period_from'], form.cleaned_data['period_to']
            if f > t:
                messages.error(request, "Period start must be before period end.")
                return redirect('audit_portal:generate_document')
            try:
                doc = save_audit_document(
                    f, t, request.user,
                    title=form.cleaned_data.get('title') or None,
                    template_key=form.cleaned_data['template_key'],
                )
                AuditLog.write(request, 'audit.document_generate', 'AuditDocument', doc.id,
                               title=doc.title, period=f"{f} → {t}", template=doc.template_key,
                               sha256=doc.sha256[:16])
                messages.success(request, f"Audit document '{doc.title}' generated and signed.")
                return redirect('audit_portal:generate_document')
            except Exception as e:
                messages.error(request, f"Generation failed: {e}")
                return redirect('audit_portal:generate_document')
    else:
        try:
            initial['template_key'] = active_key if active_key in FILE_TEMPLATE_MAP else 'audit_summary_report'
        except Exception:
            pass
        form = DocForm(initial=initial)

    documents = AuditDocument.objects.select_related('generated_by').order_by('-created_at')[:50]
    db_templates = AuditTemplate.objects.count()
    return render(request, 'dashboard/audit/generate_document.html', {
        'form': form,
        'documents': documents,
        'template_meta': {k: AUDIT_TEMPLATE_META.get(k, (k, '')) for k in FILE_TEMPLATE_MAP},
        'active_key': active_key,
        'db_templates': db_templates,
    })


@role_required(*AUDIT_ROLES)
def audit_document_download(request, doc_id):
    from admin.dig_portal.models import AuditDocument
    from django.http import FileResponse, Http404
    doc = AuditDocument.objects.filter(pk=doc_id).first()
    if not doc or not doc.pdf_file:
        raise Http404
    AuditLog.write(request, 'audit.document_download', 'AuditDocument', doc.id, title=doc.title)
    return FileResponse(open(doc.pdf_file.path, 'rb'), as_attachment=True,
                        filename=f"{doc.title}.pdf".replace('/', '-'))
