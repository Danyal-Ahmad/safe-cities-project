import csv
import datetime
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings as dj_settings

from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from django.db.models import Count
from detections.models import Detection
from django.db.models import Q
from accounts.models import User
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from accounts.decorators import role_required


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
def audit_log(request):
    qs = AuditLog.objects.all()
    actor = request.GET.get('actor')
    if actor: qs = qs.filter(actor_id=actor)
    action_filter = request.GET.get('action')
    if action_filter: qs = qs.filter(action__icontains=action_filter)
    date_from = request.GET.get('date_from')
    if date_from: qs = qs.filter(timestamp__date__gte=date_from)
    date_to = request.GET.get('date_to')
    if date_to: qs = qs.filter(timestamp__date__lte=date_to)
    qs = qs[:500]
    users = User.objects.filter(role__in=['DIG', 'OFFICER'])
    return render(request, 'dashboard/dig/audit_log.html', {
        'logs': qs, 'users': users, 'actor': actor, 'action_filter': action_filter,
        'date_from': date_from, 'date_to': date_to,
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
def audit_export(request):
    qs = AuditLog.objects.all()[:100000]
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_log.csv"'
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Actor', 'Action', 'Target Model', 'Target ID', 'IP', 'Details'])
    for log in qs:
        writer.writerow([
            log.timestamp.isoformat(),
            str(log.actor) if log.actor else '',
            log.action, log.target_model, log.target_id or '',
            log.ip_address or '', str(log.details),
        ])
    return response


@role_required('DIG')
def audit_templates_select(request):
    from admin.audit_portal.audit_pdf import (BUILTIN_TEMPLATES,
                                              generate_audit_pdf,
                                              get_active_template_key,
                                              get_audit_templates,
                                              get_template_preview_html)
    from ..models import AuditPDFTemplate


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
        key = (request.POST.get('template_key') or '').strip()
        valid_keys = {t['key'] for t in get_audit_templates()}
        if action != 'activate':
            messages.error(
                request,
                "DIG access is select-only. Template creation, editing and deletion "
                "are performed by IT Support.")
        elif key not in valid_keys:
            messages.error(request, "Unknown template selection.")
        else:
            sys_settings = SystemSettings.get()
            sys_settings.audit_pdf_template = key
            sys_settings.save(update_fields=['audit_pdf_template'])
            if key.startswith('db:'):
                AuditPDFTemplate.objects.filter(pk=key[3:]).update(is_active=True)
            AuditLog.write(request, 'audit_template.select', 'SystemSettings', None,
                           template=key)
            messages.success(request, f"Active audit PDF template set to '{key}'.")
        return redirect('dig:audit_templates_select')

    templates = []
    for t in get_audit_templates():
        item = dict(t)
        item['preview_html'] = get_template_preview_html(t['key'])
        templates.append(item)
    return render(request, 'dashboard/dig/audit_templates_select.html', {
        'templates': templates,
        'active_template_key': get_active_template_key(),
        'builtin_count': len(BUILTIN_TEMPLATES),
        'db_count': sum(1 for t in templates if not t['is_builtin']),
    })


@role_required('DIG', 'SSP')
def flagged_detections(request):
    qs = Detection.objects.filter(status=Detection.FLAGGED).select_related('camera', 'reviewed_by').order_by('-created_at')[:200]
    return render(request, 'dashboard/dig/flagged_detections.html', {'flagged': qs})


def _evidence_panel(detection):
    checks = [c for c in (detection.evidence_checks or []) if isinstance(c, dict)]
    by_name = {c.get('check'): c for c in checks}
    ordered = []
    for name in INTEGRITY_CHECK_ORDER:
        c = by_name.get(name) or {}
        ordered.append({
            'name': name,
            'label': INTEGRITY_CHECK_LABELS.get(name, name.replace('_', ' ').title()),
            'passed': bool(c.get('passed')),
            'detail': c.get('detail') or '',
        })
    passed_count = sum(1 for c in ordered if c['passed'])
    frames_meta = detection.evidence_frames_meta or []
    frame_count = len(frames_meta) if frames_meta else detection.track_frames
    return {
        'checks': ordered,
        'passed_count': passed_count,
        'total': len(ordered),
        'frame_count': frame_count,
    }


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT')
def evidence_integrity(request):
    base = (Detection.objects.select_related('camera')
            .exclude(evidence_hash__isnull=True).exclude(evidence_hash='')
            .order_by('-created_at'))
    status_filter = (request.GET.get('status') or '').strip()
    if status_filter in (Detection.PENDING, Detection.CONFIRMED, Detection.REJECTED, Detection.FLAGGED):
        base = base.filter(status=status_filter)
    rows = []
    for d in base[:50]:
        panel = _evidence_panel(d)
        rows.append({
            'id': d.id,
            'camera': d.camera,
            'plate': d.effective_plate or '-',
            'status': d.status,
            'status_display': d.get_status_display(),
            'created_at': d.created_at,
            'track_id': d.track_id,
            'track_consistency': d.track_consistency,
            'evidence_hash': d.evidence_hash,
            'verify_url': reverse('dig:evidence_integrity_verify', args=[d.id]),
            **panel,
        })
    hashed_total = Detection.objects.exclude(evidence_hash__isnull=True).exclude(evidence_hash='').count()
    full_chain = sum(1 for r in rows if r['total'] == 5 and r['passed_count'] == 5)
    partial_chain = len(rows) - full_chain
    return render(request, 'dashboard/dig/evidence_integrity.html', {
        'detections': rows,
        'hashed_total': hashed_total,
        'full_chain': full_chain,
        'partial_chain': partial_chain,
        'status_filter': status_filter,
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT')
def evidence_integrity_verify(request, detection_id):
    detection = get_object_or_404(Detection, pk=detection_id)
    from detections.pipeline import build_evidence_hash
    stored = detection.evidence_hash or ''
    recomputed = ''
    if detection.evidence_checks:
        recomputed = build_evidence_hash(detection, detection.evidence_checks, detection.camera) or ''
    verified = bool(stored) and bool(recomputed) and stored == recomputed
    AuditLog.write(
        request, 'evidence.verify', 'Detection', detection.id,
        verified=verified,
        stored=(stored[:16] + '..') if stored else '',
        recomputed=(recomputed[:16] + '..') if recomputed else '',
    )
    return JsonResponse({
        'verified': verified,
        'recomputed': recomputed,
        'stored': stored,
    })


@role_required('DIG', 'SSP')
def login_events(request):
    from ..models import LoginEvent
    today = timezone.localdate()
    base = LoginEvent.objects.select_related('user').order_by('-timestamp')
    portal = (request.GET.get('portal') or '').strip()
    success = (request.GET.get('success') or '').strip()
    user_q = (request.GET.get('user') or '').strip()
    events = base
    if portal in ('admin', 'citizen'):
        events = events.filter(portal=portal)
    if success == '1':
        events = events.filter(success=True)
    elif success == '0':
        events = events.filter(success=False)
    if user_q:
        events = events.filter(Q(username_attempted__icontains=user_q) | Q(user__username__icontains=user_q))
    total = events.count()
    events = list(events[:200])

    week_ago = today - datetime.timedelta(days=7)
    week_qs = LoginEvent.objects.filter(timestamp__date__gte=week_ago)
    logins_7d = week_qs.filter(success=True).count()
    failed_7d = week_qs.filter(success=False).count()
    unique_users = week_qs.values('username_attempted').distinct().count()
    portal_rows = list(week_qs.values('portal').annotate(c=Count('id')).order_by('-c'))
    top_portal = portal_rows[0] if portal_rows else None
    top_portal_display = dict(LoginEvent.PORTAL_CHOICES).get(top_portal['portal'], '-') if top_portal else '-'

    trend_labels = []
    trend_success = []
    trend_failed = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        day_qs = LoginEvent.objects.filter(timestamp__date=d)
        trend_labels.append(d.strftime('%d %b'))
        trend_success.append(day_qs.filter(success=True).count())
        trend_failed.append(day_qs.filter(success=False).count())

    return render(request, 'dashboard/dig/login_events.html', {
        'events': events,
        'total': total,
        'logins_7d': logins_7d,
        'failed_7d': failed_7d,
        'unique_users': unique_users,
        'top_portal': top_portal_display,
        'trend_labels': trend_labels,
        'trend_success': trend_success,
        'trend_failed': trend_failed,
        'filters': {'portal': portal, 'success': success, 'user': user_q},
    })


@role_required('DIG', 'SSP')
def login_events_export(request):
    from ..models import LoginEvent
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="dig_login_events.csv"'
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Account', 'Portal', 'Outcome', 'Failure Reason',
                     'IP Address', 'Browser', 'OS', 'Device Type', 'Device'])
    for e in LoginEvent.objects.select_related('user').order_by('-timestamp')[:50000]:
        writer.writerow([
            e.timestamp.isoformat() if e.timestamp else '',
            e.user.username if e.user else e.username_attempted,
            e.get_portal_display(),
            'SUCCESS' if e.success else 'FAILED',
            e.failure_reason or '',
            e.ip_address or '',
            e.browser or '',
            e.os or '',
            e.device_type or '',
            e.device_summary or '',
        ])
    return response


INTEGRITY_CHECK_ORDER = (
    'plate_readability', 'frame_consistency', 'violation_logic',
    'image_evidence', 'chain_integrity',
)


INTEGRITY_CHECK_LABELS = {
    'plate_readability': 'Plate Readability',
    'frame_consistency': 'Frame Consistency',
    'violation_logic': 'Violation Logic',
    'image_evidence': 'Image Evidence',
    'chain_integrity': 'Chain Integrity',
}

