"""Audit document PDF service — renders government-style audit documents.

Templates live under templates/audit/audit_templates/ or in the AuditTemplate
database (Audit Studio designs). Every generated document is signed by the
generating Audit Officer and countersigned by the DIG, with a SHA-256 digest
stored on the AuditDocument record for tamper evidence.
"""
import datetime
import hashlib
import logging
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger('wrongway.audit_pdf')

AUDIT_TEMPLATES_DIR = Path(settings.BASE_DIR) / 'templates' / 'audit' / 'audit_templates'

FILE_TEMPLATE_MAP = {
    'audit_summary_report': 'audit/audit_templates/audit_summary_report.html',
    'compliance_certificate': 'audit/audit_templates/compliance_certificate.html',
    'financial_audit_statement': 'audit/audit_templates/financial_audit_statement.html',
    'security_incident_report': 'audit/audit_templates/security_incident_report.html',
    'operational_review_letter': 'audit/audit_templates/operational_review_letter.html',
}
DEFAULT_TEMPLATE_KEY = 'audit_summary_report'

AUDIT_TEMPLATE_META = {
    'audit_summary_report': ('Periodic Audit Summary Report', 'Enforcement, evidence integrity and financial position with findings'),
    'compliance_certificate': ('Certificate of Compliance', 'Certifies the pipeline meets the five-step evidence standard'),
    'financial_audit_statement': ('Financial Audit Statement', 'Revenue collected / outstanding with auditor note and triple signatures'),
    'security_incident_report': ('Security & Authentication Incident Report', 'Login activity, failed attempts, source IPs and audited actions'),
    'operational_review_letter': ('Operational Review Letter', 'Official letter to the DIG with recommendations and CC list'),
}

LOGO_LEFT = Path(settings.BASE_DIR) / 'static' / 'img' / 'project_logo.png'
LOGO_RIGHT = Path(settings.BASE_DIR) / 'static' / 'img' / 'university_logo.png'


def _period_stats(period_from, period_to):
    from challans.models import Challan
    from detections.models import Detection
    from admin.dig_portal.models import AuditLog, LoginEvent

    from_dt = datetime.datetime.combine(period_from, datetime.time.min,
                                        tzinfo=datetime.timezone.utc)
    to_dt = datetime.datetime.combine(period_to + datetime.timedelta(days=1),
                                      datetime.time.min, tzinfo=datetime.timezone.utc)

    challans = Challan.objects.filter(created_at__gte=from_dt, created_at__lt=to_dt)
    detections = Detection.objects.filter(created_at__gte=from_dt, created_at__lt=to_dt)
    logins = LoginEvent.objects.filter(timestamp__gte=from_dt, timestamp__lt=to_dt)
    audit_logs = AuditLog.objects.filter(timestamp__gte=from_dt, timestamp__lt=to_dt)

    challans_issued = challans.count()
    challans_paid = challans.filter(payment_status='PAID').count()
    challans_unpaid = challans.filter(payment_status='UNPAID').count()
    challans_voided = challans.filter(payment_status='VOIDED').count()
    revenue = sum(float(c.fine_amount or 0) for c in challans.filter(payment_status='PAID'))
    revenue_pending = sum(float(c.fine_amount or 0) for c in challans.filter(payment_status='UNPAID'))

    confirmed = detections.filter(status='confirmed').count()
    pending = detections.filter(status=Detection.PENDING).count()
    rejected = detections.filter(status=Detection.REJECTED).count()
    flagged = detections.filter(status=Detection.FLAGGED).count()

    evidence_pass = 0
    evidence_total = 0
    for d in detections.filter(status=Detection.CONFIRMED).only('evidence_checks')[:500]:
        checks = d.evidence_checks or []
        if checks:
            evidence_total += 1
            if all(c.get('passed') for c in checks):
                evidence_pass += 1

    login_success = logins.filter(success=True).count()
    login_failed = logins.filter(success=False).count()
    unique_ips = list({e.ip_address for e in logins if e.ip_address})

    from django.db.models import Count
    top_actions = list(
        audit_logs.values('action').annotate(c=Count('id')).order_by('-c')[:8]
    )

    return {
        'challans_issued': challans_issued,
        'challans_paid': challans_paid,
        'challans_unpaid': challans_unpaid,
        'challans_voided': challans_voided,
        'revenue_collected': revenue,
        'revenue_pending': revenue_pending,
        'detections_total': detections.count(),
        'detections_confirmed': confirmed,
        'detections_pending': pending,
        'detections_rejected': rejected,
        'detections_flagged': flagged,
        'evidence_pass': evidence_pass,
        'evidence_total': evidence_total,
        'evidence_pass_rate': round(evidence_pass / evidence_total * 100, 1) if evidence_total else 0.0,
        'login_success': login_success,
        'login_failed': login_failed,
        'unique_ips': unique_ips[:12],
        'unique_ip_count': len(unique_ips),
        'audit_log_count': audit_logs.count(),
        'top_actions': top_actions,
    }


def _user_context(user):
    return {
        'name': (user.get_full_name() or user.username) if user else '—',
        'designation': getattr(user, 'designation', None) or (user.get_role_display() if user else '—'),
        'staff_id': getattr(user, 'staff_id', None) or '—',
        'signature_url': user.signature.url if (user and getattr(user, 'signature', None)) else None,
        'stamp_url': user.signature_stamp.url if (user and getattr(user, 'signature_stamp', None)) else None,
    }


def build_audit_context(period_from, period_to, generated_by, title, template_key):
    from admin.dig_portal.models import SystemSettings
    from accounts.models import User

    sys_settings = SystemSettings.get()
    dig = User.objects.filter(role=User.DIG, is_active=True).order_by('id').first()

    today = timezone.localdate()
    doc_no = f"AUD-{today.year}-{(period_from.strftime('%m'))}{(period_to.strftime('%m'))}-{template_key[:3].upper()}-{generated_by.id if generated_by else 0:03d}"

    return {
        'title': title,
        'doc_no': doc_no,
        'period_from': period_from,
        'period_to': period_to,
        'generated_at': timezone.localtime(),
        'generated_by': generated_by,
        'generated_by_ctx': _user_context(generated_by),
        'countersigned_by_ctx': _user_context(dig),
        'stats': _period_stats(period_from, period_to),
        'branding': {
            'authority_name_en': (sys_settings.template_config or {}).get(
                'header_text', 'SAFE CITY — TRAFFIC ENFORCEMENT'),
            'authority_name_ur': 'سیف سٹی ٹریفک پولیس',
            'govt_name': 'GOVERNMENT OF PUNJAB',
            'office_name': 'Safe City Authority — Audit & Compliance Wing',
            'helpline': '15',
            'website': 'safecity.gov.pk',
            'legal_ref_en': 'Section 99-A of the Motor Vehicles Ordinance, 1965',
        },
        'logo_left_path': str(LOGO_LEFT) if LOGO_LEFT.exists() else None,
        'logo_right_path': str(LOGO_RIGHT) if LOGO_RIGHT.exists() else None,
        'template_key': template_key,
    }


def generate_audit_pdf(period_from, period_to, generated_by, title=None, template_key=None):
    from admin.dig_portal.models import SystemSettings, AuditTemplate

    sys_settings = SystemSettings.get()
    tpl_key = template_key or sys_settings.audit_template or DEFAULT_TEMPLATE_KEY
    title = title or f"Audit Report {period_from:%d-%b-%Y} to {period_to:%d-%b-%Y}"

    context = build_audit_context(period_from, period_to, generated_by, title, tpl_key)

    html_string = None
    if tpl_key.startswith('db:'):
        try:
            row = AuditTemplate.objects.filter(pk=tpl_key[3:]).first()
            if row and row.html_content:
                from django.template import Template, Context
                html_string = Template(row.html_content).render(Context(context))
        except Exception as e:
            logger.warning('Audit DB template render failed: %s', e)
    else:
        tpl_name = FILE_TEMPLATE_MAP.get(tpl_key, FILE_TEMPLATE_MAP[DEFAULT_TEMPLATE_KEY])
        try:
            html_string = render_to_string(tpl_name, context)
        except Exception as e:
            logger.warning('Audit template %s failed: %s', tpl_name, e)

    from challans.pdf_service import _render_html_to_pdf
    if html_string:
        pdf_bytes = _render_html_to_pdf(html_string)
        if pdf_bytes:
            return pdf_bytes

    from challans.pdf_service import _minimal_pdf_bytes
    return _minimal_pdf_bytes(f"Audit {title}")


def save_audit_document(period_from, period_to, generated_by, title=None, template_key=None):
    from admin.dig_portal.models import AuditDocument, SystemSettings

    sys_settings = SystemSettings.get()
    tpl_key = template_key or sys_settings.audit_template or DEFAULT_TEMPLATE_KEY
    title = title or f"Audit Report {period_from:%d-%b-%Y} to {period_to:%d-%b-%Y}"
    pdf_bytes = generate_audit_pdf(period_from, period_to, generated_by, title, tpl_key)
    digest = hashlib.sha256(pdf_bytes).hexdigest()

    doc = AuditDocument.objects.create(
        template_key=tpl_key,
        title=title,
        period_from=period_from,
        period_to=period_to,
        generated_by=generated_by,
        sha256=digest,
    )
    from django.core.files.base import ContentFile
    doc.pdf_file.save(f"audit_{doc.id}_{period_from:%Y%m%d}_{period_to:%Y%m%d}.pdf",
                      ContentFile(pdf_bytes), save=True)
    try:
        from admin.dig_portal.models import AuditLog
        AuditLog.objects.create(
            actor=generated_by,
            action='audit.document_generate',
            target_model='AuditDocument', target_id=doc.id,
            details={'title': title, 'period': f'{period_from} → {period_to}',
                     'template': tpl_key, 'sha256': digest[:16]},
        )
    except Exception:
        pass
    return doc
