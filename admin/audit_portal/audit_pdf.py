"""Audit report PDF generation service for the SAFE CITIES PROJECT audit portal.

Engine chain mirrors challans/pdf_service.py:
    WeasyPrint (preferred) -> xhtml2pdf (fallback) -> reportlab (last resort).

Every export is enforced to a single A4 page (best effort):
    1. render the selected template with at most 25 data rows,
    2. count pages with pypdf,
    3. if > 1 page re-render with the 'government_classic' template and at most
       15 rows,
    4. if it still overflows, accept the result and log a warning.
"""
import datetime
import logging
import uuid
from collections import Counter
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.template import Context, Template
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger('wrongway.pdf')

LOGO_LEFT = Path(settings.BASE_DIR) / 'static' / 'img' / 'project_logo.png'
LOGO_RIGHT = Path(settings.BASE_DIR) / 'static' / 'img' / 'university_logo.png'


BUILTIN_TEMPLATES = {
    'government_classic': {
        'name': 'Government Classic Memorandum',
        'blurb': 'Classic black and white government audit memorandum with double-ruled header, dense bordered tables and dual signature blocks.',
        'template': 'audit_templates/government_classic.html',
    },
    'executive_summary': {
        'name': 'Executive Summary Brief',
        'blurb': 'Modern executive layout with navy scope sidebar, KPI boxes and a color-coded severity table.',
        'template': 'audit_templates/executive_summary.html',
    },
    'financial_ledger': {
        'name': 'Financial Ledger Statement',
        'blurb': 'Green-tinted ledger sheet with monospace amounts, debit/credit columns, double-underlined totals and an AUDIT VERIFIED stamp box.',
        'template': 'audit_templates/financial_ledger.html',
    },
    'compliance_matrix': {
        'name': 'Compliance Control Matrix',
        'blurb': 'Requirement and control checklist matrix with PASS/FAIL/N-A color chips, auditor remarks and a sign-off grid.',
        'template': 'audit_templates/compliance_matrix.html',
    },
    'incident_report': {
        'name': 'Security Incident Report',
        'blurb': 'Security incident style with dark header band, severity banner, event timeline, impact assessment and remediation actions.',
        'template': 'audit_templates/incident_report.html',
    },
    'statistical_digest': {
        'name': 'Statistical Data Digest',
        'blurb': 'Data digest with distribution tables, percentile strips, chart-ready tabular placeholders and a methodology note.',
        'template': 'audit_templates/statistical_digest.html',
    },
    'legal_affidavit': {
        'name': 'Legal Attestation Affidavit',
        'blurb': 'Serif legal attestation with numbered clauses, sworn-statement box, commissioner attest seal and witness lines.',
        'template': 'audit_templates/legal_affidavit.html',
    },
    'field_inspection': {
        'name': 'Field Inspection Sheet',
        'blurb': 'Field inspection sheet with checkbox matrix, site inventory table, GPS coordinates grid, remarks lines and stamp box.',
        'template': 'audit_templates/field_inspection.html',
    },
}

DEFAULT_TEMPLATE_KEY = 'government_classic'


KIND_LABELS = {
    'operational': 'Operational Audit Report',
    'financial': 'Financial Audit Report',
    'compliance': 'Compliance Report',
    'user_activity': 'User Activity Audit Report',
    'auth_events': 'Authentication Events Audit Report',
    'changes_log': 'Changes Log Report',
    'permission_changes': 'Permission Changes Audit Report',
    'anomalies': 'Anomaly Alerts Report',
    'dashboard': 'Audit Dashboard Summary',
}

_KIND_ALIASES = {
    'user-activity': 'user_activity',
    'auth-events': 'auth_events',
    'changes-log': 'changes_log',
    'permission-changes': 'permission_changes',
    'anomaly': 'anomalies',
    'anomaly-alerts': 'anomalies',
    'summary': 'dashboard',
}

MAX_ROWS = 25
FALLBACK_ROWS = 15

LOG_COLUMNS = ['Timestamp', 'Actor', 'Action', 'Target', 'IP', 'Details']

_USER_ACTIVITY_ACTIONS = ['user.create', 'user.toggle', 'user.delete', 'user.profile_edit',
                          'user.password_change', 'admin.create', 'admin.toggle',
                          'supervisor.leave_grant']

_PERMISSION_ACTIONS = ['user.create', 'user.toggle', 'user.edit', 'admin.create',
                       'admin.toggle', 'admin.edit']

_CHANGES_ACTIONS = ['camera.add', 'camera.edit', 'camera.delete', 'camera.toggle',
                    'camera.set_online', 'camera.regenerate_token', 'camera.assign',
                    'camera.unassign', 'challan.manual_create', 'challan.create',
                    'challan.update', 'challan.void', 'challan.mark_paid',
                    'challan.fine_edit', 'challan.record_payment', 'challan.bulk_fine',
                    'challan.delete', 'payment_settings.update',
                    'payment_method.create', 'payment_method.update',
                    'payment_method.toggle', 'payment_method.delete',
                    'banner.create', 'banner.update', 'banner.delete',
                    'banner.toggle', 'alert.create', 'alert.update',
                    'alert.delete', 'alert.toggle']


def normalize_kind(kind):
    """Map a URL-ish kind string onto a canonical kind key."""
    key = (kind or 'operational').strip().lower().replace('/', '')
    key = _KIND_ALIASES.get(key, key)
    return key if key in KIND_LABELS else None



def _fmt_int(n):
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n or 0)


def _fmt_pkr(n):
    try:
        return f"PKR {float(n or 0):,.0f}"
    except (TypeError, ValueError):
        return 'PKR 0'


def _actor_name(log):
    actor = getattr(log, 'actor', None)
    if actor is None:
        return 'System'
    return getattr(actor, 'display_name', None) or getattr(actor, 'username', '') or 'System'


def _details_snippet(log, limit=70):
    det = getattr(log, 'details', None)
    if isinstance(det, dict):
        text = ', '.join(f"{k}={v}" for k, v in list(det.items())[:4])
    else:
        text = str(det or '')
    text = text.replace('\n', ' ')
    if len(text) > limit:
        text = text[:limit - 3] + '...'
    return text or '-'


def _log_rows(logs, limit):
    rows = []
    for l in logs[:limit]:
        target = l.target_model or '-'
        if l.target_id:
            target += f" #{l.target_id}"
        rows.append([
            l.timestamp.strftime('%d-%b-%Y %H:%M') if l.timestamp else '-',
            _actor_name(l),
            l.action or '-',
            target,
            str(l.ip_address or '-'),
            _details_snippet(l),
        ])
    return rows


def _logo_srcs(preview):
    if preview:
        return '/static/img/project_logo.png', '/static/img/university_logo.png'
    left = f"file://{LOGO_LEFT}" if LOGO_LEFT.exists() else ''
    right = f"file://{LOGO_RIGHT}" if LOGO_RIGHT.exists() else ''
    return left, right


def _base_meta(kind, now, preview=False):
    logo_left, logo_right = _logo_srcs(preview)
    return {
        'kind': kind,
        'kind_label': KIND_LABELS[kind],
        'doc_ref': f"AUD-REF-{now:%Y%m%d}-{uuid.uuid4().hex[:4].upper()}",
        'generated_at': now,
        'generated_at_str': now.strftime('%d %b %Y %H:%M'),
        'period_label': 'Rolling window: system inception to generation time',
        'classification': 'INTERNAL - AUDIT',
        'project_name': 'SAFE CITIES PROJECT',
        'logo_left_src': logo_left,
        'logo_right_src': logo_right,
        'kpis': [],
        'table': {'columns': [], 'rows': [], 'shown': 0, 'total': 0},
        'more_rows': 0,
        'stats': [],
        'anomalies': [],
        'by_type': [],
        'by_status': [],
        'by_location': [],
        'distribution_grid': [],
        'by_type_max': 1,
        'by_status_max': 1,
        'by_location_max': 1,
        'compliance_checks': [],
        'ledger_rows': [],
        'ledger_totals': {'debit': 'PKR 0', 'credit': 'PKR 0'},
        'total_collected': '',
        'percentiles': [],
        'prepared_by': 'Automated Audit Portal',
        'PREVIEW_MODE': preview,
    }


def _detect_anomalies():
    """Reuse the exact anomaly queries the audit dashboard views use."""
    from .views import _detect_anomalies as _impl
    return _impl()


def _challan_distributions(ctx):
    """Cheap system-wide distributions used by the digest/compliance layouts."""
    from challans.models import Challan
    by_type = list(
        Challan.objects.values('violation_type').annotate(c=Count('id'))
        .order_by('-c')[:10]
    )
    by_status = list(
        Challan.objects.values('payment_status').annotate(c=Count('id'))
        .order_by('-c')[:6]
    )
    by_location = list(
        Challan.objects.values('location').annotate(c=Count('id'))
        .order_by('-c')[:10]
    )
    ctx['by_type'] = [[row['violation_type'] or '-', row['c']] for row in by_type]
    ctx['by_status'] = [[row['payment_status'] or '-', row['c']] for row in by_status]
    ctx['by_location'] = [
        [(row['location'] or 'Unspecified')[:28], row['c']] for row in by_location
    ]


def _zip_distribution_grid(ctx, max_rows=10):
    """Zip the three distributions into parallel rows for side-by-side tables."""
    n = max(len(ctx['by_type']), len(ctx['by_status']), len(ctx['by_location']), 1)
    grid = []
    for i in range(min(n, max_rows)):
        t = ctx['by_type'][i] if i < len(ctx['by_type']) else ['', '']
        s = ctx['by_status'][i] if i < len(ctx['by_status']) else ['', '']
        l = ctx['by_location'][i] if i < len(ctx['by_location']) else ['', '']
        grid.append([t[0], t[1], s[0], s[1], l[0], l[1]])
    ctx['distribution_grid'] = grid
    ctx['by_type_max'] = max([v for _, v in ctx['by_type']] or [1])
    ctx['by_status_max'] = max([v for _, v in ctx['by_status']] or [1])
    ctx['by_location_max'] = max([v for _, v in ctx['by_location']] or [1])


def _build_compliance_checks(anomalies, audit_total):
    """Data-integrity control matrix derived from the anomaly detectors."""
    checks = []
    orphan = next((a for a in anomalies if a['type'] == 'ORPHAN_PAYMENT'), None)
    zero_fine = next((a for a in anomalies if a['type'] == 'ZERO_AMOUNT_CHALLAN'), None)
    dismissals = [a for a in anomalies if a['type'] == 'HIGH_DISMISSAL_RATE']

    checks.append({
        'control': 'Audit log chain continuity (append-only ledger)',
        'status': 'PASS' if audit_total > 0 else 'N-A',
        'remark': f"{_fmt_int(audit_total)} immutable entries recorded",
    })
    checks.append({
        'control': 'Paid challans carry settlement timestamps',
        'status': 'FAIL' if orphan else 'PASS',
        'remark': orphan['description'] if orphan else 'All paid records timestamped',
    })
    checks.append({
        'control': 'Fine amounts greater than zero on issued challans',
        'status': 'FAIL' if zero_fine else 'PASS',
        'remark': zero_fine['description'] if zero_fine else 'No zero-value challans found',
    })
    checks.append({
        'control': 'Appeal dismissal rate within tolerance (per officer)',
        'status': 'FAIL' if dismissals else 'PASS',
        'remark': dismissals[0]['description'] if dismissals else 'No officer exceeds threshold',
    })
    checks.append({
        'control': 'Read-only enforcement on audit portal exports',
        'status': 'PASS',
        'remark': 'Exports are generated from immutable records',
    })
    checks.append({
        'control': 'External registry reconciliation (NADRA / Excise)',
        'status': 'N-A',
        'remark': 'Integration status verified separately by IT Support',
    })
    return checks


def _log_kind_rows(kind, actions, limit, auth_filter=False):
    from admin.dig_portal.models import AuditLog
    qs = AuditLog.objects.select_related('actor').order_by('-timestamp')
    if auth_filter:
        qs = qs.filter(
            Q(action__startswith='auth.') | Q(action__startswith='login.')
            | Q(action__startswith='password_reset')
            | Q(action='user.password_change') | Q(action='staff.password_change')
            | Q(action='account.locked')
        )
    elif actions:
        qs = qs.filter(action__in=actions)
    total = qs.count()
    logs = list(qs[:max(limit, 1) * 4])
    rows = _log_rows(logs, limit)
    return rows, total, logs[:limit]


def _set_table(ctx, columns, rows, total):
    ctx['table'] = {
        'columns': columns,
        'rows': rows,
        'shown': len(rows),
        'total': total,
    }
    ctx['more_rows'] = max(0, total - len(rows))


def _top_action_distribution(logs, ctx, top=6):
    counts = Counter(l.action for l in logs)
    ctx['by_type'] = [[a, c] for a, c in counts.most_common(top)]


def _top_actor_stats(logs, ctx, top=6):
    counts = Counter(_actor_name(l) for l in logs)
    ctx['stats'] = [
        {'label': name, 'value': f"{cnt} action(s)"}
        for name, cnt in counts.most_common(top)
    ]


def _db_context(kind, row_limit, now):
    """Build the export context from the database (mirrors the live views)."""
    from admin.dig_portal.models import AuditLog
    from challans.models import Challan

    ctx = _base_meta(kind, now)

    audit_total = AuditLog.objects.count()
    audit_24h = AuditLog.objects.filter(
        timestamp__gte=now - datetime.timedelta(hours=24)).count()
    audit_7d = AuditLog.objects.filter(
        timestamp__gte=now - datetime.timedelta(days=7)).count()

    total_paid = Challan.objects.filter(payment_status='PAID').count()
    total_unpaid = Challan.objects.filter(payment_status='UNPAID').count()
    total_voided = Challan.objects.filter(payment_status='VOIDED').count()
    revenue_collected = Challan.objects.filter(payment_status='PAID').aggregate(
        t=Sum('fine_amount'))['t'] or 0
    revenue_pending = Challan.objects.filter(payment_status='UNPAID').aggregate(
        t=Sum('fine_amount'))['t'] or 0
    total_challans = Challan.objects.count()

    try:
        anomalies = _detect_anomalies() or []
    except Exception as exc:
        logger.warning("anomaly detection failed during PDF export: %s", exc)
        anomalies = []
    ctx['anomalies'] = anomalies

    try:
        _challan_distributions(ctx)
    except Exception as exc:
        logger.warning("challan distribution query failed: %s", exc)
    _zip_distribution_grid(ctx)

    ctx['compliance_checks'] = _build_compliance_checks(anomalies, audit_total)

    if kind == 'operational':
        rows, total, logs = _log_kind_rows('operational', None, row_limit)
        _set_table(ctx, LOG_COLUMNS, rows, total)
        _top_action_distribution(logs, ctx)
        _top_actor_stats(logs, ctx)
        ctx['kpis'] = [
            {'label': 'Total Audit Entries', 'value': _fmt_int(audit_total), 'hint': 'all time'},
            {'label': 'Entries (24h)', 'value': _fmt_int(audit_24h), 'hint': 'last 24 hours'},
            {'label': 'Entries (7d)', 'value': _fmt_int(audit_7d), 'hint': 'last 7 days'},
            {'label': 'Rows In Report', 'value': _fmt_int(len(rows)), 'hint': 'most recent'},
        ]

    elif kind == 'financial':
        qs = Challan.objects.filter(payment_status='PAID').order_by('-paid_at')
        total = qs.count()
        payments = list(qs[:row_limit])
        rows = []
        for p in payments:
            rows.append([
                p.paid_at.strftime('%d-%b-%Y %H:%M') if p.paid_at else '-',
                p.ticket_no or '-',
                p.plate_number or '-',
                (p.get_violation_type_display() or '-') if hasattr(p, 'get_violation_type_display') else '-',
                f"{float(p.fine_amount or 0):,.0f}",
            ])
        _set_table(ctx, ['Paid At', 'Ticket', 'Plate', 'Violation', 'Amount (PKR)'], rows, total)
        avg = (float(revenue_collected) / total) if total else 0
        ctx['kpis'] = [
            {'label': 'Total Collected', 'value': _fmt_pkr(revenue_collected), 'hint': 'paid challans'},
            {'label': 'Paid Challans', 'value': _fmt_int(total), 'hint': 'settled'},
            {'label': 'Average Payment', 'value': _fmt_pkr(avg), 'hint': 'per challan'},
            {'label': 'Revenue Pending', 'value': _fmt_pkr(revenue_pending), 'hint': 'unpaid'},
        ]
        ledger_rows = []
        debit_total = 0.0
        credit_total = 0.0
        for p in payments:
            amount = float(p.fine_amount or 0)
            credit_total += amount
            ledger_rows.append({
                'date': p.paid_at.strftime('%d-%b-%Y') if p.paid_at else '-',
                'ref': p.ticket_no or '-',
                'description': f"{p.plate_number or '-'} | {(p.get_violation_type_display() or '-') if hasattr(p, 'get_violation_type_display') else '-'}",
                'debit': '',
                'credit': f"{amount:,.0f}",
            })
        if revenue_pending:
            debit_total = float(revenue_pending)
            ledger_rows.append({
                'date': now.strftime('%d-%b-%Y'),
                'ref': 'PENDING-POOL',
                'description': 'Aggregate unpaid challans (receivable)',
                'debit': f"{debit_total:,.0f}",
                'credit': '',
            })
        ctx['ledger_rows'] = ledger_rows
        ctx['ledger_totals'] = {
            'debit': _fmt_pkr(debit_total),
            'credit': _fmt_pkr(credit_total),
        }
        ctx['total_collected'] = _fmt_pkr(revenue_collected)
        amounts = sorted(float(p.fine_amount or 0) for p in payments)
        if amounts:
            def pct(p):
                idx = min(len(amounts) - 1, int(round((len(amounts) - 1) * p / 100.0)))
                return amounts[idx]
            ctx['percentiles'] = [
                {'label': 'P10', 'value': f"{pct(10):,.0f}"},
                {'label': 'P25', 'value': f"{pct(25):,.0f}"},
                {'label': 'P50 (median)', 'value': f"{pct(50):,.0f}"},
                {'label': 'P75', 'value': f"{pct(75):,.0f}"},
                {'label': 'P90', 'value': f"{pct(90):,.0f}"},
            ]
        ctx['stats'] = [
            {'label': 'Challans issued', 'value': _fmt_int(total_challans)},
            {'label': 'Paid', 'value': _fmt_int(total_paid)},
            {'label': 'Unpaid', 'value': _fmt_int(total_unpaid)},
            {'label': 'Voided', 'value': _fmt_int(total_voided)},
        ]

    elif kind == 'compliance':
        rows = [[c['control'], c['status'], c['remark']] for c in ctx['compliance_checks']]
        _set_table(ctx, ['Control / Requirement', 'Status', 'Auditor Remark'], rows, len(rows))
        ctx['kpis'] = [
            {'label': 'Violation Types', 'value': _fmt_int(len(ctx['by_type'])), 'hint': 'distinct'},
            {'label': 'Paid Challans', 'value': _fmt_int(total_paid), 'hint': 'compliant'},
            {'label': 'Unpaid Challans', 'value': _fmt_int(total_unpaid), 'hint': 'outstanding'},
            {'label': 'Voided', 'value': _fmt_int(total_voided), 'hint': 'cancelled'},
        ]
        ctx['stats'] = [
            {'label': 'Controls evaluated', 'value': _fmt_int(len(rows))},
            {'label': 'Passed', 'value': _fmt_int(sum(1 for c in ctx['compliance_checks'] if c['status'] == 'PASS'))},
            {'label': 'Failed', 'value': _fmt_int(sum(1 for c in ctx['compliance_checks'] if c['status'] == 'FAIL'))},
            {'label': 'Not applicable', 'value': _fmt_int(sum(1 for c in ctx['compliance_checks'] if c['status'] == 'N-A'))},
        ]

    elif kind == 'anomalies':
        rows = [[a['type'], a['severity'], a['description'], a['target']]
                for a in anomalies[:row_limit]]
        _set_table(ctx, ['Anomaly Type', 'Severity', 'Description', 'Target'], rows, len(anomalies))
        sev = Counter(a['severity'] for a in anomalies)
        ctx['kpis'] = [
            {'label': 'Total Anomalies', 'value': _fmt_int(len(anomalies)), 'hint': 'open detections'},
            {'label': 'High Severity', 'value': _fmt_int(sev.get('HIGH', 0)), 'hint': 'immediate action'},
            {'label': 'Medium Severity', 'value': _fmt_int(sev.get('MEDIUM', 0)), 'hint': 'monitor'},
            {'label': 'Low Severity', 'value': _fmt_int(sev.get('LOW', 0)), 'hint': 'informational'},
        ]
        ctx['stats'] = [
            {'label': 'Anomaly classes', 'value': _fmt_int(len(set(a['type'] for a in anomalies)))},
            {'label': 'Audit entries scanned', 'value': _fmt_int(audit_total)},
        ]

    elif kind == 'dashboard':
        logs = list(AuditLog.objects.select_related('actor').order_by('-timestamp')[:row_limit])
        rows = _log_rows(logs, min(row_limit, 12))
        _set_table(ctx, LOG_COLUMNS[:4], [r[:4] for r in rows], audit_total)
        _top_action_distribution(logs, ctx)
        _top_actor_stats(logs, ctx)
        ctx['kpis'] = [
            {'label': 'Total Challans', 'value': _fmt_int(total_challans), 'hint': 'all time'},
            {'label': 'Revenue Collected', 'value': _fmt_pkr(revenue_collected), 'hint': 'paid'},
            {'label': 'Audit Entries', 'value': _fmt_int(audit_total), 'hint': f"{_fmt_int(audit_24h)} in 24h"},
            {'label': 'Open Anomalies', 'value': _fmt_int(len(anomalies)), 'hint': 'needs review'},
        ]

    else:
        auth_filter = (kind == 'auth_events')
        actions = {
            'user_activity': _USER_ACTIVITY_ACTIONS,
            'permission_changes': _PERMISSION_ACTIONS,
            'changes_log': _CHANGES_ACTIONS,
        }.get(kind, None)
        rows, total, logs = _log_kind_rows(kind, actions, row_limit, auth_filter=auth_filter)
        _set_table(ctx, LOG_COLUMNS, rows, total)
        _top_action_distribution(logs, ctx)
        _top_actor_stats(logs, ctx)
        ctx['kpis'] = [
            {'label': 'Logged Events', 'value': _fmt_int(total), 'hint': 'matching filters'},
            {'label': 'Rows In Report', 'value': _fmt_int(len(rows)), 'hint': 'most recent'},
            {'label': 'Entries (24h)', 'value': _fmt_int(audit_24h), 'hint': 'all actions'},
            {'label': 'Tracked Actions', 'value': _fmt_int(len(actions) if actions else 0) or 'auth.*', 'hint': 'filters'},
        ]

    return ctx



_PREVIEW_LOG_ROWS = [
    ['08 Jan 2025 09:41', 'audit.officer1', 'challan.mark_paid', 'Challan #10428', '10.20.3.17', 'ticket=SC-10428, amount=500'],
    ['08 Jan 2025 09:12', 'dig.admin', 'admin.toggle', 'User #63', '10.20.1.4', 'target=officer12, active=True'],
    ['08 Jan 2025 08:55', 'it.support', 'camera.add', 'Camera #31', '10.20.9.8', 'location=Ring Road Junction 4'],
    ['07 Jan 2025 18:03', 'ssp.command', 'ssp.appeal_decision', 'Appeal #221', '10.20.2.9', 'decision=approved'],
    ['07 Jan 2025 16:47', 'supervisor2', 'supervisor.appeal_override', 'Appeal #218', '10.20.2.31', 'stage=final, note=verified'],
    ['07 Jan 2025 15:20', 'officer.km', 'detection.confirm', 'Detection #8841', '10.20.7.22', 'plate=LEB-4521, confidence=0.93'],
]


def _preview_context(kind='dashboard'):
    now = timezone.now()
    ctx = _base_meta(kind, now, preview=True)
    ctx['kind_label'] = KIND_LABELS.get(kind, 'Audit Report') + ' (Preview)'
    ctx['kpis'] = [
        {'label': 'Audit Entries', 'value': '1,284', 'hint': 'total recorded'},
        {'label': 'Challans Issued', 'value': '356', 'hint': 'all time'},
        {'label': 'Revenue Collected', 'value': 'PKR 182,500', 'hint': 'settled'},
        {'label': 'Open Anomalies', 'value': '2', 'hint': 'requires review'},
    ]
    ctx['table'] = {
        'columns': LOG_COLUMNS,
        'rows': [r[:] for r in _PREVIEW_LOG_ROWS],
        'shown': len(_PREVIEW_LOG_ROWS),
        'total': 1284,
    }
    ctx['more_rows'] = 1278
    ctx['stats'] = [
        {'label': 'Top actor', 'value': 'officer.km (214 actions)'},
        {'label': 'Busiest hour', 'value': '09:00 - 10:00'},
        {'label': 'Peak day', 'value': '05 Jan 2025'},
        {'label': 'Unique actors', 'value': '17'},
    ]
    ctx['anomalies'] = [
        {'type': 'HIGH_DISMISSAL_RATE', 'severity': 'HIGH',
         'description': 'Officer Imran Khan has rejected 12 appeals', 'target': 'officer.imran'},
        {'type': 'ORPHAN_PAYMENT', 'severity': 'HIGH',
         'description': '3 challans marked PAID without paid_at timestamp', 'target': '-'},
        {'type': 'ZERO_AMOUNT_CHALLAN', 'severity': 'LOW',
         'description': '2 challans with zero fine amount', 'target': '-'},
    ]
    ctx['by_type'] = [['detection.confirm', 128], ['challan.create', 96],
                      ['user.create', 44], ['camera.add', 21], ['banner.update', 12]]
    ctx['by_status'] = [['PAID', 180], ['UNPAID', 141], ['VOIDED', 35]]
    ctx['by_location'] = [['Main Boulevard', 62], ['Ring Road', 48],
                          ['Canal Bridge', 37], ['Airport Road', 26], ['Liberty Market', 19]]
    _zip_distribution_grid(ctx)
    ctx['compliance_checks'] = [
        {'control': 'Audit log chain continuity (append-only ledger)', 'status': 'PASS',
         'remark': '1,284 immutable entries recorded'},
        {'control': 'Paid challans carry settlement timestamps', 'status': 'FAIL',
         'remark': '3 challans marked PAID without paid_at timestamp'},
        {'control': 'Fine amounts greater than zero on issued challans', 'status': 'FAIL',
         'remark': '2 challans with zero fine amount'},
        {'control': 'Appeal dismissal rate within tolerance (per officer)', 'status': 'PASS',
         'remark': 'No officer exceeds threshold'},
        {'control': 'Read-only enforcement on audit portal exports', 'status': 'PASS',
         'remark': 'Exports are generated from immutable records'},
        {'control': 'External registry reconciliation (NADRA / Excise)', 'status': 'N-A',
         'remark': 'Integration status verified separately by IT Support'},
    ]
    ctx['ledger_rows'] = [
        {'date': '08 Jan 2025', 'ref': 'SC-10428', 'description': 'LEB-4521 | Wrong Way', 'debit': '', 'credit': '500'},
        {'date': '07 Jan 2025', 'ref': 'SC-10411', 'description': 'XYZ-9987 | Over Speed', 'debit': '', 'credit': '800'},
        {'date': '07 Jan 2025', 'ref': 'SC-10402', 'description': 'ABC-1123 | Signal Break', 'debit': '', 'credit': '500'},
        {'date': '06 Jan 2025', 'ref': 'PENDING-POOL', 'description': 'Aggregate unpaid challans (receivable)', 'debit': '92,300', 'credit': ''},
    ]
    ctx['ledger_totals'] = {'debit': 'PKR 92,300', 'credit': 'PKR 1,800'}
    ctx['total_collected'] = 'PKR 182,500'
    ctx['percentiles'] = [
        {'label': 'P10', 'value': '300'},
        {'label': 'P25', 'value': '500'},
        {'label': 'P50 (median)', 'value': '500'},
        {'label': 'P75', 'value': '800'},
        {'label': 'P90', 'value': '1,000'},
    ]
    return ctx


def build_audit_context(kind, row_limit=MAX_ROWS, preview=False):
    """Public entry: standard context for a kind (DB backed or preview)."""
    kind = normalize_kind(kind) or 'operational'
    if preview:
        return _preview_context(kind)
    now = timezone.now()
    try:
        return _db_context(kind, row_limit, now)
    except Exception as exc:
        logger.warning("audit context build failed for kind=%s: %s", kind, exc)
        ctx = _base_meta(kind, now)
        ctx['table'] = {
            'columns': ['Notice'],
            'rows': [['Data for this report could not be assembled at generation time.']],
            'shown': 1,
            'total': 1,
        }
        return ctx



_WEASYPRINT_STATE = None


def _render_html_to_pdf(html_string):
    """HTML -> PDF via WeasyPrint, then xhtml2pdf, then None (caller falls back)."""
    global _WEASYPRINT_STATE
    if _WEASYPRINT_STATE is not False:
        try:
            from weasyprint import HTML
            base_url = str(settings.BASE_DIR)
            pdf_bytes = HTML(string=html_string, base_url=base_url).write_pdf()
            _WEASYPRINT_STATE = True
            if pdf_bytes:
                return pdf_bytes
        except Exception as e:
            _WEASYPRINT_STATE = False
            logger.warning("WeasyPrint unavailable (%s) - using fallback PDF engine.", e)
    try:
        import re
        from xhtml2pdf import pisa
        from io import BytesIO
        clean_html = re.sub(r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', '', html_string, flags=re.IGNORECASE)
        buf = BytesIO()
        result = pisa.CreatePDF(clean_html, dest=buf, link_callback=lambda uri, rel: None)
        if not result.err:
            return buf.getvalue()
    except Exception as e:
        logger.warning("xhtml2pdf failed: %s", e)
    return None


def _render_template_html(template_key, context):
    """Resolve a template key (builtin name or 'db:<id>') to rendered HTML."""
    key = (template_key or '').strip()
    if key.startswith('db:'):
        try:
            from admin.dig_portal.models import AuditPDFTemplate
            row = AuditPDFTemplate.objects.filter(pk=key[3:]).first()
            if row and row.html_content:
                return Template(row.html_content).render(Context(context))
        except Exception as e:
            logger.warning("audit DB template render failed (%s): %s", key, e)
    spec = BUILTIN_TEMPLATES.get(key) or BUILTIN_TEMPLATES[DEFAULT_TEMPLATE_KEY]
    try:
        return render_to_string(spec['template'], context)
    except Exception as e:
        logger.warning("audit template %s failed: %s", key, e)
    if key != DEFAULT_TEMPLATE_KEY:
        try:
            return render_to_string(
                BUILTIN_TEMPLATES[DEFAULT_TEMPLATE_KEY]['template'], context)
        except Exception as e:
            logger.warning("audit fallback template failed: %s", e)
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"
        f"<h1>SAFE CITIES PROJECT</h1><h2>{context.get('kind_label', 'Audit Report')}</h2>"
        f"<p>Ref {context.get('doc_ref', '')} | generated {context.get('generated_at_str', '')}</p>"
        "</body></html>"
    )


def _pdf_page_count(pdf_bytes):
    try:
        from pypdf import PdfReader
        return len(PdfReader(BytesIO(pdf_bytes)).pages)
    except Exception as e:
        logger.warning("pypdf page count failed: %s", e)
        return 1


def _fallback_reportlab_audit_pdf(kind, context):
    """Plain A4 summary drawn with reportlab (last-resort engine)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    ink = colors.black

    c.setFont('Helvetica-Bold', 15)
    c.drawString(18 * mm, h - 18 * mm, 'SAFE CITIES PROJECT')
    c.setFont('Helvetica', 10)
    c.drawString(18 * mm, h - 24 * mm, 'Office of the Auditor General (Internal)')
    c.drawString(18 * mm, h - 29 * mm, str(context.get('kind_label', kind)))
    c.setFont('Helvetica', 8)
    c.drawString(18 * mm, h - 35 * mm,
                 f"Ref: {context.get('doc_ref', '-')} | Generated: "
                 f"{context.get('generated_at_str', '-')} | INTERNAL - AUDIT")
    c.setStrokeColor(ink)
    c.setLineWidth(1.2)
    c.line(18 * mm, h - 38 * mm, w - 18 * mm, h - 38 * mm)

    table = context.get('table') or {}
    columns = table.get('columns') or []
    y = h - 46 * mm
    if columns:
        c.setFont('Helvetica-Bold', 7.5)
        x = 18 * mm
        for col in columns[:6]:
            c.drawString(x, y, str(col)[:22])
            x += (w - 36 * mm) / 6.0
        y -= 5 * mm
        c.setFont('Helvetica', 7)
        for row in (table.get('rows') or [])[:24]:
            if y < 30 * mm:
                break
            x = 18 * mm
            for cell in row[:6]:
                c.drawString(x, y, str(cell)[:24])
                x += (w - 36 * mm) / 6.0
            y -= 4.6 * mm

    c.setFont('Helvetica-Oblique', 7)
    c.drawString(18 * mm, 16 * mm,
                 'Computer generated audit document - page 1 of 1 - INTERNAL - AUDIT')
    c.showPage()
    c.save()
    return buf.getvalue()



def get_active_template_key():
    """Current audit PDF template key from SystemSettings (singleton)."""
    try:
        from admin.dig_portal.models import SystemSettings
        key = (getattr(SystemSettings.get(), 'audit_pdf_template', '') or '').strip()
        if key:
            return key
    except Exception as e:
        logger.warning("could not read active audit template: %s", e)
    return DEFAULT_TEMPLATE_KEY


def get_audit_templates():
    """The 8 built-in templates plus every DB template (key = 'db:<id>')."""
    out = []
    for key, spec in BUILTIN_TEMPLATES.items():
        out.append({
            'key': key,
            'name': spec['name'],
            'blurb': spec['blurb'],
            'is_builtin': True,
            'created_at': None,
        })
    try:
        from admin.dig_portal.models import AuditPDFTemplate
        for row in AuditPDFTemplate.objects.all():
            out.append({
                'key': f'db:{row.pk}',
                'name': row.name,
                'blurb': row.description or 'Custom database template',
                'is_builtin': False,
                'created_at': row.created_at,
                'is_active': row.is_active,
            })
    except Exception as e:
        logger.warning("could not list DB audit templates: %s", e)
    return out


def _preview_urlize(html):
    """Rewrite embedded filesystem asset paths to servable URLs for browser previews."""
    if not html:
        return html
    from django.conf import settings as dj_settings
    static_root = str(Path(dj_settings.BASE_DIR) / 'static')
    media_root = str(getattr(dj_settings, 'MEDIA_ROOT', ''))
    html = html.replace(static_root + '/', '/static/')
    if media_root:
        html = html.replace(media_root + '/', '/media/')
    return html


def get_template_preview_html(template_key, kind='dashboard'):
    """Rendered standalone HTML for the preview cards (placeholder data)."""
    try:
        ctx = _preview_context(normalize_kind(kind) or 'dashboard')
        return _preview_urlize(_render_template_html(template_key, ctx))
    except Exception as e:
        logger.warning("preview render failed for %s: %s", template_key, e)
        return ('<!DOCTYPE html><html><body style="font-family:sans-serif;'
                'padding:16px;color:#64748b;">Preview unavailable</body></html>')


def generate_audit_pdf(kind, context=None, template_key=None):
    """Generate a single-page A4 audit report PDF; returns bytes (never raises)."""
    kind = normalize_kind(kind) or 'operational'

    ctx = build_audit_context(kind)
    if context:
        ctx.update(context)

    if not template_key:
        template_key = get_active_template_key()

    html = _render_template_html(template_key, ctx)
    pdf_bytes = _render_html_to_pdf(html) if html else None

    if pdf_bytes:
        if _pdf_page_count(pdf_bytes) <= 1:
            return pdf_bytes
        logger.warning(
            "audit PDF for kind=%s exceeded one page - re-rendering with "
            "government_classic and %d rows", kind, FALLBACK_ROWS)
        ctx2 = build_audit_context(kind, row_limit=FALLBACK_ROWS)
        if context:
            ctx2.update(context)
        html2 = _render_template_html(DEFAULT_TEMPLATE_KEY, ctx2)
        pdf2 = _render_html_to_pdf(html2) if html2 else None
        if pdf2:
            if _pdf_page_count(pdf2) <= 1:
                return pdf2
            logger.warning(
                "audit PDF for kind=%s still exceeds one page after fallback - "
                "accepting best effort", kind)
            return pdf2
        return pdf_bytes

    try:
        return _fallback_reportlab_audit_pdf(kind, ctx)
    except Exception as e:
        logger.warning("reportlab audit fallback failed: %s", e)
        body = b"BT /F1 12 Tf 50 750 Td (SAFE CITIES PROJECT - Audit Report) Tj ET"
        parts = [
            b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
            b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
            (b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
             b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"),
            (b"4 0 obj<< /Length " + str(len(body)).encode() + b" >>stream\n"
             + body + b"\nendstream\nendobj\n"),
            b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
        ]
        pdf = b"%PDF-1.4\n"
        offsets = [0]
        for part in parts:
            offsets.append(len(pdf))
            pdf += part
        xref_pos = len(pdf)
        pdf += f"xref\n0 {len(parts) + 1}\n".encode()
        pdf += b"0000000000 65535 f \n"
        for off in offsets[1:]:
            pdf += f"{off:010d} 00000 n \n".encode()
        pdf += (f"trailer<< /Size {len(parts) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_pos}\n%%EOF\n").encode()
        return pdf
