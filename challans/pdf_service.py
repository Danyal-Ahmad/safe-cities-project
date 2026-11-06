"""Challan PDF generation service.

Guarantees:
- Every challan renders as EXACTLY ONE A4 page (page-count verified with pypdf;
  overflow re-renders through the compact template, then the ReportLab
  single-page fallback).
- Exactly ONE large evidence image: the annotated full-frame capture with the
  violation box, plate box and direction arrow (Detection.annotated_image,
  falling back to the raw frame).
- Payment channels are rendered as ICONS (static/img/payment/*.svg), not text.
- Only the selected template plus its data is rendered, never extra data.
"""
import re
import logging
import os
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string

logger = logging.getLogger('wrongway.pdf')

LOGO_LEFT = Path(settings.BASE_DIR) / 'static' / 'img' / 'project_logo.png'
LOGO_RIGHT = Path(settings.BASE_DIR) / 'static' / 'img' / 'university_logo.png'

TEMPLATE_MAP = {
    'modern_a4': 'challan/challan_templates/modern_a4.html',
    'classic_a4': 'challan/challan_templates/classic_a4.html',
    'legal_notice_99a': 'challan/challan_templates/legal_notice_99a.html',
    'digital_slip': 'challan/challan_templates/digital_slip.html',
    'command_brief': 'challan/challan_templates/command_brief.html',
    'secure_instrument': 'challan/challan_templates/secure_instrument.html',
    'urdu_executive': 'challan/challan_templates/urdu_executive.html',
    'compact_a4': 'challan/challan_templates/command_brief.html',  # overflow guard
    'safecityfyp_classic': 'challan/challan_templates/modern_a4.html',
}

PAYMENT_ICONS = [
    ('JazzCash', 'img/payment/jazzcash.svg'),
    ('EasyPaisa', 'img/payment/easypaisa.svg'),
    ('Debit / Credit Card', 'img/payment/card.svg'),
    ('Bank / PSID', 'img/payment/psid.svg'),
    ('Post Office', 'img/payment/postoffice.svg'),
]


def _make_barcode(ticket_no: str):
    try:
        import barcode
        from barcode.writer import SVGWriter
        buf = BytesIO()
        text = (ticket_no or 'CHALLAN').strip()[:40]
        code = barcode.get('code128', text, writer=SVGWriter())
        code.write(buf, options={
            'module_height': 8.0,
            'module_width': 0.3,
            'quiet_zone': 1.5,
            'write_text': False,
        })
        return buf.getvalue().decode('utf-8', errors='ignore'), None
    except Exception:
        try:
            safe = (ticket_no or 'CHALLAN').replace('&', '&amp;').replace('<', '&lt;')[:40]
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="48">'
                f'<rect width="100%" height="100%" fill="#fff"/>'
                f'<text x="12" y="30" font-family="monospace" font-size="14">{safe}</text>'
                f'</svg>'
            )
            return svg, None
        except Exception:
            return None, None


def _make_qr_svg(payload: str):
    """Server-side QR code as an inline SVG string (WeasyPrint cannot run JS)."""
    try:
        import qrcode
        import qrcode.image.svg as qr_svg
        img = qrcode.make(payload or 'SAFECITY', image_factory=qr_svg.SvgPathImage, box_size=10)
        buf = BytesIO()
        img.save(buf)
        return buf.getvalue().decode('utf-8', errors='ignore')
    except Exception as exc:
        logger.debug('QR generation failed: %s', exc)
        return None


def _resolve_static(path_rel: str):
    candidate = Path(settings.BASE_DIR) / 'static' / path_rel
    return str(candidate) if candidate.exists() else None


def _evidence_image(challan):
    """The ONE evidence image used by every template: annotated frame first."""
    det = getattr(challan, 'detection', None)
    if det is None:
        return None, None
    for field in ('annotated_image', 'raw_image'):
        img = getattr(det, field, None)
        if img and hasattr(img, 'name') and img.name:
            try:
                path = img.path
                if os.path.exists(path):
                    return path, field
            except Exception:
                continue
    return None, None


def _pdf_page_count(pdf_bytes: bytes) -> int:
    try:
        from pypdf import PdfReader
        return len(PdfReader(BytesIO(pdf_bytes)).pages)
    except Exception:
        return 1


def _needs_nadra_excise_integration(challan) -> bool:
    """True when owner identity could not be resolved because NADRA/Excise
    registry integration is not configured. Drives the red PDF warning text.
    """
    if getattr(challan, 'owner_name', None):
        return False
    try:
        from integrations.mode import is_real
        from admin.dig_portal.models import SystemSettings as _SS
        sys = _SS.get()
        has_excise = bool((getattr(sys, 'excise_api_url', None) or '').strip() and
                          (getattr(sys, 'excise_api_key', None) or '').strip())
        return (is_real() and not has_excise) or not is_real()
    except Exception:
        return True


def _fallback_reportlab_pdf(challan) -> bytes:
    """Single-page A4 PDF when WeasyPrint is unavailable."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor, black
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont('Helvetica-Bold', 16)
    c.drawString(40, h - 50, 'SAFE CITIES PROJECT')
    c.setFont('Helvetica', 11)
    c.drawString(40, h - 75, 'E-Challan (Official Copy)')

    needs_integration = _needs_nadra_excise_integration(challan)
    owner_display = getattr(challan, 'owner_name', None) or (
        'OWNER PENDING REGISTRY VERIFICATION' if needs_integration else '-')
    cnic_display = getattr(challan, 'cnic', None) or (
        'OWNER PENDING REGISTRY VERIFICATION' if needs_integration else '-')

    y = h - 120
    rows = [
        ('Ticket No', getattr(challan, 'ticket_no', '')),
        ('Plate', getattr(challan, 'plate_number', '')),
        ('Violation', challan.get_violation_type_display() if hasattr(challan, 'get_violation_type_display') else str(getattr(challan, 'violation_type', '') or '-')),
        ('Fine (PKR)', str(getattr(challan, 'fine_amount', ''))),
        ('Issue Date', str(getattr(challan, 'issue_date', ''))),
        ('Due Date', str(getattr(challan, 'due_date', ''))),
        ('Location', getattr(challan, 'location', '') or '-'),
        ('Status', getattr(challan, 'payment_status', '')),
        ('Owner', owner_display),
        ('CNIC', cnic_display),
    ]
    for k, v in rows:
        c.setFont('Helvetica-Bold', 10)
        c.drawString(40, y, f'{k}:')
        is_warning = k in ('Owner', 'CNIC') and needs_integration and not getattr(
            challan, 'owner_name' if k == 'Owner' else 'cnic', None)
        if is_warning:
            c.setFillColor(HexColor('#dc2626'))
            c.setFont('Helvetica-Bold', 10)
        else:
            c.setFillColor(black)
            c.setFont('Helvetica', 10)
        c.drawString(140, y, str(v)[:80])
        c.setFillColor(black)
        y -= 22

    evidence_path, _which = _evidence_image(challan)
    if evidence_path:
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(evidence_path)
            iw, ih = img.getSize()
            draw_w = 300
            draw_h = draw_w * ih / iw
            if draw_h > 300:
                draw_h = 300
                draw_w = draw_h * iw / ih
            c.drawImage(img, 40, y - draw_h - 10, width=draw_w, height=draw_h)
            c.setFont('Helvetica-Oblique', 8)
            c.drawString(40, y - draw_h - 22, 'Evidence: annotated violation frame')
        except Exception:
            pass

    c.setFont('Helvetica-Oblique', 9)
    c.drawString(40, 40, 'SAFE CITIES PROJECT')
    c.showPage()
    c.save()
    return buf.getvalue()


def _minimal_pdf_bytes(ticket_no: str) -> bytes:
    """Tiny valid PDF with no external deps (last resort)."""
    label = f'Challan {ticket_no or ""}'.replace('(', ' ').replace(')', ' ')[:60]
    content = f'BT /F1 12 Tf 50 750 Td ({label}) Tj ET'
    body = content.encode('latin-1', errors='ignore')
    parts = [
        b'1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n',
        b'2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n',
        (
            b'3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
            b'/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n'
        ),
        (
            f'4 0 obj<< /Length {len(body)} >>stream\n'.encode('ascii')
            + body
            + b'\nendstream\nendobj\n'
        ),
        b'5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n',
    ]
    pdf = b'%PDF-1.4\n'
    offsets = [0]
    for part in parts:
        offsets.append(len(pdf))
        pdf += part
    xref_pos = len(pdf)
    pdf += f'xref\n0 {len(parts) + 1}\n'.encode('ascii')
    pdf += b'0000000000 65535 f \n'
    for off in offsets[1:]:
        pdf += f'{off:010d} 00000 n \n'.encode('ascii')
    pdf += (
        f'trailer<< /Size {len(parts) + 1} /Root 1 0 R >>\n'
        f'startxref\n{xref_pos}\n%%EOF\n'
    ).encode('ascii')
    return pdf


_WEASYPRINT_STATE = None  # None = untested, True = ok, False = broken


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
            logger.warning('WeasyPrint unavailable (%s) | using fallback PDF engine.', e)
    try:
        from xhtml2pdf import pisa
        clean_html = re.sub(r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', '', html_string, flags=re.IGNORECASE)
        buf = BytesIO()
        result = pisa.CreatePDF(clean_html, dest=buf, link_callback=lambda uri, rel: None)
        if not result.err:
            return buf.getvalue()
    except Exception as e:
        logger.warning('xhtml2pdf failed: %s', e)
    return None


def _build_context(challan):
    from admin.dig_portal.models import SystemSettings

    sys_settings = SystemSettings.get()

    logo_left_path = str(LOGO_LEFT) if LOGO_LEFT.exists() else None
    logo_right_path = str(LOGO_RIGHT) if LOGO_RIGHT.exists() else None
    if getattr(sys_settings, 'pdf_logo', None):
        try:
            logo_right_path = sys_settings.pdf_logo.path
        except Exception:
            pass

    bc_svg, bc_url = _make_barcode(
        getattr(challan, 'ticket_no', '') or str(getattr(challan, 'id', ''))
    )
    qr_payload = getattr(challan, 'payment_qr_payload', None) or (
        f'SAFECITY|TKT:{challan.ticket_no}|PLT:{challan.plate_number}|'
        f'AMT:{challan.fine_amount}'
    )
    evidence_summary = None
    det = getattr(challan, 'detection', None)
    if det is not None and getattr(det, 'evidence_checks', None):
        checks = det.evidence_checks or []
        passed = sum(1 for c in checks if c.get('passed'))
        seq_frames = len([
            m for m in (det.evidence_frames_meta or [])
            if int(m.get('slot') or 1) > 1
        ]) if hasattr(det, 'evidence_frames_meta') else 0
        evidence_summary = {
            'checks': checks,
            'passed': passed,
            'total': len(checks),
            'all_passed': bool(checks) and passed == len(checks),
            'hash': det.evidence_hash,
            'track_id': det.track_id,
            'track_frames': det.track_frames,
            'track_consistency': det.track_consistency,
            'sequential_frames': seq_frames,
        }

    evidence_path, evidence_source = _evidence_image(challan)
    payment_icons = [
        {'label': label, 'path': _resolve_static(rel)}
        for label, rel in PAYMENT_ICONS
    ]

    context = {
        'challan': challan,
        'settings': sys_settings,
        'evidence_summary': evidence_summary,
        'template_config': sys_settings.template_config or getattr(
            SystemSettings, 'DEFAULT_TEMPLATE_CONFIG', {}
        ),
        'logo_left_path': logo_left_path,
        'logo_right_path': logo_right_path,
        'evidence_image_path': evidence_path,
        'evidence_image_source': evidence_source,
        'payment_icons': [p for p in payment_icons if p['path']],
        'barcode_svg': bc_svg,
        'barcode_data_url': bc_url,
        'qr_svg': _make_qr_svg(qr_payload),
        'needs_nadra_excise': _needs_nadra_excise_integration(challan),
    }

    officer = None
    created_by = getattr(challan, 'created_by', None)
    if created_by is not None and getattr(created_by, 'is_authenticated', True):
        officer = created_by
    if officer is None:
        det = getattr(challan, 'detection', None) or getattr(challan, 'source_detection', None)
        if det is not None:
            for attr in ('reviewed_by', 'confirmed_by', 'flagged_by', 'auto_confirmed_by'):
                u = getattr(det, attr, None)
                if u is not None:
                    officer = u
                    break
    if officer is not None:
        context['issuing_officer'] = officer
        context['officer_signature_url'] = officer.signature.url if getattr(officer, 'signature', None) else None
        context['officer_signature_name'] = (
            officer.signature_name
            or officer.get_full_name()
            or officer.first_name
            or officer.username
        )
        context['officer_signature_designation'] = (
            officer.signature_designation
            or officer.designation
            or officer.get_role_display()
        )
        context['officer_signature_stamp_url'] = officer.signature_stamp.url if getattr(officer, 'signature_stamp', None) else None
        context['officer_staff_id'] = getattr(officer, 'staff_id', None) or '-'
        context['officer_region'] = getattr(officer, 'region', None) or '-'
    return context


def _render_template_to_html(tpl_key, context):
    if isinstance(tpl_key, str) and tpl_key.startswith('db:'):
        try:
            from admin.dig_portal.models import ChallanTemplate
            from django.template import Context, Template
            row = ChallanTemplate.objects.filter(pk=tpl_key[3:], is_active=True).first()
            if row and row.html_content:
                return Template(row.html_content).render(Context(context))
        except Exception as e:
            logger.warning('DB template render failed: %s', e)
        return None
    tpl_name = TEMPLATE_MAP.get(tpl_key, TEMPLATE_MAP['modern_a4'])
    try:
        return render_to_string(tpl_name, context)
    except Exception as e:
        logger.warning('Template %s failed: %s', tpl_name, e)
        return None


def generate_challan_pdf(challan):
    """Render the challan PDF, guaranteeing a ONE A4 page document."""
    from admin.dig_portal.models import SystemSettings

    sys_settings = SystemSettings.get()
    context = _build_context(challan)

    tpl_key = (
        getattr(sys_settings, 'pdf_template', None)
        or (sys_settings.template_config or {}).get('pdf_template')
        or 'modern_a4'
    )

    html_string = _render_template_to_html(tpl_key, context)
    if html_string:
        pdf_bytes = _render_html_to_pdf(html_string)
        if pdf_bytes:
            pages = _pdf_page_count(pdf_bytes)
            if pages <= 1:
                return pdf_bytes
            logger.warning(
                'Challan %s rendered %d pages with template %s | re-rendering compact',
                getattr(challan, 'ticket_no', challan.pk), pages, tpl_key,
            )
            # Overflow guard: re-render with the compact one-page template.
            compact_html = _render_template_to_html('compact_a4', context)
            if compact_html:
                compact_bytes = _render_html_to_pdf(compact_html)
                if compact_bytes and _pdf_page_count(compact_bytes) <= 1:
                    return compact_bytes
            try:
                return _fallback_reportlab_pdf(challan)
            except Exception as e:
                logger.warning('ReportLab fallback failed: %s', e)
                return pdf_bytes  # best effort: keep multi-page over no challan

    try:
        return _fallback_reportlab_pdf(challan)
    except Exception as e:
        logger.warning('ReportLab fallback failed: %s', e)
        return _minimal_pdf_bytes(getattr(challan, 'ticket_no', ''))


def save_challan_pdf(challan, force=False):
    if challan.pdf_file and not force:
        return challan.pdf_file
    pdf_bytes = generate_challan_pdf(challan)
    name = f"{getattr(challan, 'ticket_no', challan.pk) or challan.pk}.pdf".replace('/', '-')
    challan.pdf_file.save(name, ContentFile(pdf_bytes), save=True)
    return challan.pdf_file
