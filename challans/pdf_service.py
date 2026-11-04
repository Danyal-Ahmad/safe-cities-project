import base64
import datetime
import os
import re
import logging
from io import BytesIO
from pathlib import Path

from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.conf import settings

logger = logging.getLogger('wrongway.pdf')

LOGO_LEFT = Path(settings.BASE_DIR) / 'static' / 'img' / 'project_logo.png'
LOGO_RIGHT = Path(settings.BASE_DIR) / 'static' / 'img' / 'university_logo.png'

CHALLAN_TEMPLATES_DIR = Path(settings.BASE_DIR) / 'templates' / 'challan' / 'challan_templates'

FILE_TEMPLATE_MAP = {
    'standard_a4':      'challan/challan_templates/standard_a4.html',
    'bilingual_a4':     'challan/challan_templates/bilingual_a4.html',
    'notice_classic_a4': 'challan/challan_templates/notice_classic_a4.html',
    'psca_urdu_a4':     'challan/challan_templates/psca_urdu_a4.html',
    'government_grid_a4': 'challan/challan_templates/government_grid_a4.html',
}
DEFAULT_TEMPLATE_KEY = 'standard_a4'
LEGACY_TEMPLATE_ALIASES = {
    'modern_a4': 'standard_a4',
    'classic_a4': 'government_grid_a4',
    'legal_notice_99a': 'notice_classic_a4',
    'digital_slip': 'bilingual_a4',
    'safecityfyp_classic': 'standard_a4',
}

BRANDING_DEFAULTS = {
    'authority_name_en': 'SAFE CITY TRAFFIC POLICE',
    'authority_name_ur': 'سیف سٹی ٹریفک پولیس',
    'authority_name_en_short': 'Safe City Traffic Police',
    'authority_name_ur_short': 'سیف سٹی ٹریفک پولیس',
    'govt_name': 'GOVERNMENT OF PUNJAB',
    'tagline_part_1': 'SERVICE',
    'tagline_part_2': 'SECURITY',
    'tagline_part_3': 'SAFETY',
    'tagline_en': 'SERVICE · SECURITY · SAFETY',
    'tagline_ur': 'خدمت · حفاظت · سیکورٹی',
    'slogan_ur_line_1': 'قانون کی پاسداری',
    'slogan_ur_line_2': 'ہم سب کی ذمہ داری',
    'helpline': '15',
    'website': 'safecity.gov.pk',
    'portal_name': 'Safe City E-Challan Portal',
    'office_name': 'Safe City Traffic Police Headquarters',
    'social_handle': '@SafeCityPolice',
    'footer_slogan_ur': 'قانون کی پاسداری · ہم سب کی ذمہ داری',
    'legal_ref_en': 'Section 99-A of the Motor Vehicles Ordinance, 1965',
    'legal_ref_ur': 'موٹر وہیکلز آرڈیننس 1965ء کی دفعہ 99-اے',
    'bank_names': 'National Bank of Pakistan / Bank of Punjab',
    'wallet_names': 'JazzCash / EasyPaisa',
    'pay_website': 'safecity.gov.pk/pay',
    'footer_1_en': 'Computer generated document',
    'footer_1_ur': 'کمپیوٹر سے تیار شدہ دستاویز',
    'footer_2_en': 'Verifiable at the official portal',
    'footer_2_ur': 'سرکاری پورٹل پر تصدیق کے قابل',
    'footer_3_en': 'Safe City Authority',
    'footer_3_sub': 'Traffic Enforcement Wing',
    'footer_3_ur': 'سیف سٹی اتھارٹی',
    'officer_title_en': 'Authorized Traffic Officer',
    'officer_title_ur': 'مجاز ٹریفک افسر',
}

_ONES = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
         'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
         'Seventeen', 'Eighteen', 'Nineteen']
_TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']


def _three_digit_to_words(n):
    out = []
    if n >= 100:
        out.append(_ONES[n // 100] + ' Hundred')
        n %= 100
    if n >= 20:
        out.append(_TENS[n // 10] + ('' if n % 10 == 0 else '-' + _ONES[n % 10]))
    elif n > 0:
        out.append(_ONES[n])
    return ' '.join(out)


def amount_in_words(amount) -> str:
    try:
        n = int(float(amount or 0))
    except (TypeError, ValueError):
        return ''
    if n <= 0:
        return 'Zero Rupees Only'
    parts = []
    units = [(10000000, 'Crore'), (100000, 'Lac'), (1000, 'Thousand'), (1, '')]
    for div, label in units:
        q, n = divmod(n, div)
        if q:
            parts.append(_three_digit_to_words(q) + (' ' + label if label else ''))
    return ', '.join(parts) + ' Rupees Only'


def _make_barcode(ticket_no: str):
    svg = None
    data_url = None
    text = (ticket_no or "CHALLAN").strip()[:40]
    try:
        import barcode
        from barcode.writer import SVGWriter
        buf = BytesIO()
        code = barcode.get("code128", text, writer=SVGWriter())
        code.write(buf, options={
            "module_height": 8.0,
            "module_width": 0.3,
            "quiet_zone": 1.5,
            "write_text": False,
        })
        svg = buf.getvalue().decode("utf-8", errors="ignore")
    except Exception:
        try:
            safe = text.replace("&", "&amp;").replace("<", "&lt;")
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="48">'
                f'<rect width="100%" height="100%" fill="#fff"/>'
                f'<text x="12" y="30" font-family="monospace" font-size="14">{safe}</text>'
                f'</svg>'
            )
        except Exception:
            svg = None
    return svg, data_url


def _make_qr_data_url(payload: str) -> str:
    try:
        import qrcode
        buf = BytesIO()
        img = qrcode.make(payload or 'SAFECITY', box_size=6, border=2)
        img.save(buf, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception as e:
        logger.debug('QR generation failed: %s', e)
        return ''


def _branding_context(sys_settings) -> dict:
    cfg = dict(BRANDING_DEFAULTS)
    tc = getattr(sys_settings, 'template_config', None) or {}
    if tc.get('header_text'):
        cfg['authority_name_en'] = str(tc['header_text']).upper()
        cfg['authority_name_en_short'] = str(tc['header_text']).title()
    if tc.get('footer_text'):
        cfg['pay_note_en'] = tc['footer_text']
    if tc.get('account_number'):
        cfg['account_number'] = tc['account_number']
    else:
        cfg['account_number'] = 'C0263A'
    return cfg


def _speed_context(challan):
    if getattr(challan, 'violation_type', '') == 'over_speed':
        return {'allowed': '—', 'detected': '—', 'excess': '—', 'applicable': True}
    return {'allowed': 'N/A', 'detected': 'N/A', 'excess': 'N/A', 'applicable': False}


def _camera_context(challan):
    det = getattr(challan, 'detection', None)
    camera = getattr(challan, 'camera', None) or getattr(det, 'camera', None)
    ts = getattr(det, 'created_at', None) or getattr(challan, 'created_at', None) or datetime.datetime.now()
    bbox = {'x': 0, 'y': 0, 'w': 0, 'h': 0}
    raw = getattr(det, 'ai_raw_response', None) or {}
    norm = raw.get('bbox_norm') or raw.get('plate_bbox_norm')
    if norm and len(norm) == 4:
        try:
            x1, y1, x2, y2 = [float(v) for v in norm]
            bbox = {'x': x1 * 100, 'y': y1 * 100, 'w': (x2 - x1) * 100, 'h': (y2 - y1) * 100}
        except (TypeError, ValueError):
            pass
    return {
        'id': getattr(camera, 'camera_id', None) or 'CAM-SAFECITY',
        'location': getattr(camera, 'location', None) or getattr(challan, 'location', '') or '—',
        'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
        'direction': getattr(challan, 'moving_direction', None) or '—',
        'legal_direction': getattr(challan, 'legal_direction', None) or '—',
        'bbox': bbox,
        'has_bbox': bbox['w'] > 0,
    }


def _frame_evidence_context(challan):
    det = getattr(challan, 'detection', None)
    frames = []
    raw = getattr(det, 'ai_raw_response', None) or {}
    for i, rec in enumerate((raw.get('frame_evidence') or [])[:3], start=1):
        frames.append({
            'index': i,
            'plate': rec.get('plate') or '—',
            'confidence': rec.get('confidence') or 0.0,
            'ocr_confidence': rec.get('ocr_confidence') or 0.0,
            'timestamp': rec.get('timestamp') or '—',
            'complete': rec.get('plate_complete', True),
        })
    if not frames and det is not None:
        frames.append({
            'index': 1,
            'plate': getattr(det, 'ai_plate_text', '') or '—',
            'confidence': getattr(det, 'ai_confidence', 0.0) or 0.0,
            'ocr_confidence': (raw.get('ocr_confidence') or 0.0),
            'timestamp': (getattr(det, 'created_at', None) or datetime.datetime.now()).strftime('%Y-%m-%d %H:%M:%S'),
            'complete': True,
        })
    return frames


def _get_quadrant_images(challan):
    evidence = []
    det = getattr(challan, "detection", None)
    if det is None:
        return evidence
    for field, label in (('raw_image', 'Full frame'), ('vehicle_image', 'Vehicle'),
                         ('plate_crop_image', 'Plate'), ('plate_image', 'Plate')):
        img = getattr(det, field, None)
        if img and hasattr(img, 'name') and label not in [e[0] for e in evidence]:
            try:
                if os.path.exists(img.path):
                    evidence.append((label, img.path))
            except Exception:
                pass
    if not evidence:
        for label, img in (("Full frame", getattr(det, "raw_image", None)),):
            if img and hasattr(img, "path"):
                try:
                    if os.path.exists(img.path):
                        evidence.append((label, img.path))
                except Exception:
                    pass
    return evidence


def _fallback_reportlab_pdf(challan) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor, black

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, h - 50, "SAFE CITY TRAFFIC ENFORCEMENT")
    c.setFont("Helvetica", 11)
    c.drawString(40, h - 75, "E-Challan (Official Copy)")

    needs_integration = _needs_nadra_excise_integration(challan)
    owner_display = getattr(challan, "owner_name", None) or (
        "NEED TO INTEGRATE NADRA/EXCISE APIS" if needs_integration else "-"
    )
    cnic_display = getattr(challan, "cnic", None) or (
        "NEED TO INTEGRATE NADRA/EXCISE APIS" if needs_integration else "-"
    )

    y = h - 120
    rows = [
        ("Ticket No", getattr(challan, "ticket_no", "")),
        ("Plate", getattr(challan, "plate_number", "")),
        ("Violation", getattr(challan, "violation_type", "")),
        ("Fine (PKR)", str(getattr(challan, "fine_amount", ""))),
        ("Issue Date", str(getattr(challan, "issue_date", ""))),
        ("Due Date", str(getattr(challan, "due_date", ""))),
        ("Location", getattr(challan, "location", "") or "-"),
        ("Status", getattr(challan, "payment_status", "")),
        ("Owner", owner_display),
        ("CNIC", cnic_display),
    ]
    for k, v in rows:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, f"{k}:")
        is_warning = k in ("Owner", "CNIC") and needs_integration and not getattr(
            challan, "owner_name" if k == "Owner" else "cnic", None
        )
        if is_warning:
            c.setFillColor(HexColor("#dc2626"))
            c.setFont("Helvetica-Bold", 10)
        else:
            c.setFillColor(black)
            c.setFont("Helvetica", 10)
        c.drawString(140, y, str(v)[:80])
        c.setFillColor(black)
        y -= 22
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(40, 40, "This is a computer-generated e-challan. Generated by Safe City FYP.")
    c.showPage()
    c.save()
    return buf.getvalue()


def _minimal_pdf_bytes(ticket_no: str) -> bytes:
    label = f"Challan {ticket_no or ''}".replace("(", " ").replace(")", " ")[:60]
    content = f"BT /F1 12 Tf 50 750 Td ({label}) Tj ET"
    body = content.encode("latin-1", errors="ignore")
    parts = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        (
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
        ),
        (
            f"4 0 obj<< /Length {len(body)} >>stream\n".encode("ascii")
            + body
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for part in parts:
        offsets.append(len(pdf))
        pdf += part
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(parts) + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer<< /Size {len(parts) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    return pdf


def _needs_nadra_excise_integration(challan) -> bool:
    if getattr(challan, "owner_name", None):
        return False
    try:
        from integrations.mode import is_real
        from admin.dig_portal.models import SystemSettings as _SS
        sys = _SS.get()
        has_excise = bool((getattr(sys, "excise_api_url", None) or "").strip() and
                          (getattr(sys, "excise_api_key", None) or "").strip())
        return (is_real() and not has_excise) or not is_real()
    except Exception:
        return True


_WEASYPRINT_STATE = None


def _render_html_to_pdf(html_string):
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
            logger.warning("WeasyPrint unavailable (%s) — using fallback PDF engine.", e)
    try:
        from xhtml2pdf import pisa
        clean_html = re.sub(r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', '', html_string, flags=re.IGNORECASE)
        buf = BytesIO()
        result = pisa.CreatePDF(clean_html, dest=buf, link_callback=lambda uri, rel: None)
        if not result.err:
            return buf.getvalue()
    except Exception as e:
        logger.warning("xhtml2pdf failed: %s", e)
    return None


def _resolve_template_key(tpl_key):
    key = (tpl_key or '').strip()
    key = LEGACY_TEMPLATE_ALIASES.get(key, key)
    if key in FILE_TEMPLATE_MAP:
        return key
    return None


def generate_challan_pdf(challan):
    from admin.dig_portal.models import SystemSettings

    sys_settings = SystemSettings.get()

    logo_left_path = str(LOGO_LEFT) if LOGO_LEFT.exists() else None
    logo_right_path = str(LOGO_RIGHT) if LOGO_RIGHT.exists() else None
    if getattr(sys_settings, "pdf_logo", None):
        try:
            logo_right_path = sys_settings.pdf_logo.path
        except Exception:
            pass

    bc_svg, bc_url = _make_barcode(
        getattr(challan, "ticket_no", "") or str(getattr(challan, "id", ""))
    )
    evidence_summary = None
    det = getattr(challan, "detection", None)
    if det is not None and getattr(det, "evidence_checks", None):
        checks = det.evidence_checks or []
        passed = sum(1 for c in checks if c.get("passed"))
        evidence_summary = {
            "checks": checks,
            "passed": passed,
            "total": len(checks),
            "all_passed": bool(checks) and passed == len(checks),
            "hash": det.evidence_hash,
            "track_id": det.track_id,
            "track_frames": det.track_frames,
            "track_consistency": det.track_consistency,
        }

    context = {
        "challan": challan,
        "settings": sys_settings,
        "evidence_summary": evidence_summary,
        "template_config": sys_settings.template_config or getattr(
            SystemSettings, "DEFAULT_TEMPLATE_CONFIG", {}
        ),
        "branding": _branding_context(sys_settings),
        "speed": _speed_context(challan),
        "camera_meta": _camera_context(challan),
        "frame_evidence": _frame_evidence_context(challan),
        "fine_in_words": amount_in_words(getattr(challan, 'fine_amount', 0)),
        "due_days": getattr(sys_settings, 'due_date_days', 30) or 30,
        "appeal_days": 15,
        "points_deducted": 0,
        "qr_code_data_url": _make_qr_data_url(getattr(challan, 'payment_qr_payload', '')),
        "logo_left_path": logo_left_path,
        "logo_right_path": logo_right_path,
        "quadrant_images": _get_quadrant_images(challan),
        "evidence_images": _get_quadrant_images(challan),
        "barcode_svg": bc_svg,
        "barcode_data_url": bc_url,
        "needs_nadra_excise": _needs_nadra_excise_integration(challan),
    }

    officer = None
    created_by = getattr(challan, "created_by", None)
    if created_by is not None and getattr(created_by, "is_authenticated", True):
        officer = created_by
    if officer is None:
        det = getattr(challan, "detection", None) or getattr(challan, "source_detection", None)
        if det is not None:
            for attr in ("reviewed_by", "confirmed_by", "flagged_by", "auto_confirmed_by"):
                u = getattr(det, attr, None)
                if u is not None:
                    officer = u
                    break
    if officer is not None:
        context["issuing_officer"] = officer
        context["officer_signature_url"] = officer.signature.url if getattr(officer, "signature", None) else None
        context["officer_signature_name"] = (
            officer.signature_name
            or officer.get_full_name()
            or officer.first_name
            or officer.username
        )
        context["officer_signature_designation"] = (
            officer.signature_designation
            or officer.designation
            or officer.get_role_display()
        )
        context["officer_signature_stamp_url"] = officer.signature_stamp.url if getattr(officer, "signature_stamp", None) else None
        context["officer_staff_id"] = getattr(officer, "staff_id", None) or "—"
        context["officer_region"] = getattr(officer, "region", None) or "—"

    tpl_key = (
        getattr(sys_settings, "pdf_template", None)
        or (sys_settings.template_config or {}).get("pdf_template")
        or DEFAULT_TEMPLATE_KEY
    )

    html_string = None
    if isinstance(tpl_key, str) and tpl_key.startswith("db:"):
        try:
            from admin.dig_portal.models import ChallanTemplate
            tid = tpl_key[3:]
            row = ChallanTemplate.objects.filter(pk=tid, is_active=True).first()
            if row and row.html_content:
                from django.template import Template, Context
                html_string = Template(row.html_content).render(Context(context))
        except Exception as e:
            logger.warning("DB template render failed: %s", e)
    else:
        file_key = _resolve_template_key(tpl_key) or DEFAULT_TEMPLATE_KEY
        tpl_name = FILE_TEMPLATE_MAP[file_key]
        try:
            html_string = render_to_string(tpl_name, context)
        except Exception as e:
            logger.warning("Template %s failed: %s", tpl_name, e)
            html_string = None

    if html_string:
        pdf_bytes = _render_html_to_pdf(html_string)
        if pdf_bytes:
            return pdf_bytes

    try:
        return _fallback_reportlab_pdf(challan)
    except Exception as e:
        logger.warning("ReportLab fallback failed: %s", e)
        return _minimal_pdf_bytes(getattr(challan, "ticket_no", ""))


def save_challan_pdf(challan, force=False):
    if challan.pdf_file and not force:
        return challan.pdf_file
    pdf_bytes = generate_challan_pdf(challan)
    name = f"{getattr(challan, 'ticket_no', challan.pk) or challan.pk}.pdf".replace("/", "-")
    challan.pdf_file.save(name, ContentFile(pdf_bytes), save=True)
    return challan.pdf_file
