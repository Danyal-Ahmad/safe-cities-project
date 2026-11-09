"""Render every challan template to PDF and verify the ONE A4 page guarantee."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wrongway_system.settings')

import django
django.setup()

from pathlib import Path

from challans.models import Challan
from challans.pdf_service import (
    TEMPLATE_MAP, _build_context, _render_html_to_pdf, _pdf_page_count,
)
from django.template.loader import render_to_string

OUT = Path('/tmp/render')
OUT.mkdir(parents=True, exist_ok=True)

challan = Challan.objects.select_related('detection', 'camera').filter(
    detection__isnull=False).order_by('-id').first()
assert challan is not None, 'No challan with detection found'
print(f'Rendering with challan {challan.ticket_no} | plate {challan.plate_number} | '
      f'type {challan.violation_type} | cam {challan.camera.camera_id if challan.camera else "-"}')

context = _build_context(challan)
print('evidence_image_path:', context.get('evidence_image_path'))
print('payment_icons:', [p['label'] for p in context['payment_icons']])
print()

results = []
for key in ('modern_a4', 'classic_a4', 'legal_notice_99a', 'digital_slip',
            'command_brief', 'secure_instrument', 'urdu_executive'):
    tpl = TEMPLATE_MAP[key]
    html = render_to_string(tpl, context)
    pdf = _render_html_to_pdf(html)
    assert pdf, f'{key}: render failed (no engine output)'
    pages = _pdf_page_count(pdf)
    (OUT / f'{key}.pdf').write_bytes(pdf)
    results.append((key, pages, len(pdf)))
    print(f'{key:18s} pages={pages} bytes={len(pdf):7d} -> {OUT / (key + ".pdf")}')

bad = [r for r in results if r[1] != 1]
print()
print('ALL SINGLE PAGE OK' if not bad else f'MULTI-PAGE FAILURES: {bad}')
sys.exit(1 if bad else 0)
