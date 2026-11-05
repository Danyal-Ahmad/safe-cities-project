"""Programmatic QA of rendered challan PDFs: text artifacts + pixel geometry."""
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

OUT = Path('/tmp/render')


def norm(s):
    return re.sub(r'\s+', '', s).casefold()


BANNED_TEXT = [
    'PAGE 1 OF 1', 'Page 1 of 1',
    'http://', 'https://', 'www.',
    'Computer-generated', 'System-generated', 'AUTO-GENERATED',
]
REQUIRED_TEXT = {
    'modern_a4': ['SAFE CITIES PROJECT', 'WRONG WAY', 'EVIDENCE FRAME', '94.00%'],
    'classic_a4': ['SAFE CITIES PROJECT', 'WRONG WAY', 'Evidenceframe', '94.00%'],
    'legal_notice_99a': ['SAFE CITIES PROJECT', 'WRONG WAY', 'NOTICEOFTRAFFICVIOLATION', '94.00%'],
    'digital_slip': ['SAFE CITIES PROJECT', 'WRONG WAY', 'E-CHALLAN', '94.00%'],
    'command_brief': ['SAFE CITIES PROJECT', 'WRONG WAY', 'DIRECTIONANALYSIS', 'LEGAl'.lower().upper(), 'OBSERVED DIRECTION'.replace(' ', ''), '94.00%', 'PSID'],
    'legal': [],
    'secure_instrument': ['SAFE CITIES PROJECT', 'WRONG WAY', 'ANALYZEDOFFENCE', 'PSID', 'DETACH', '94.00%'],
    'urdu_executive': ['SAFE CITIES PROJECT', 'WRONG WAY', 'ANALYZEDOFFENCE', '94.00%'],
}
REQUIRED_TEXT['command_brief'] = ['SAFE CITIES PROJECT', 'WRONG WAY', 'DIRECTIONANALYSIS',
                                  'LEGAlDIRECTION'.replace('l', 'L').replace(' ', ''), 'OBSERVEDDIRECTION',
                                  '94.00%', 'PSID']


def pdftotext(pdf):
    r = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True)
    return r.stdout


def page_image(pdf, dpi=60):
    subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-singlefile',
                    str(pdf), str(OUT / pdf.stem) + '_qa'], check=True)
    return Image.open(OUT / (pdf.stem + '_qa.png')).convert('RGB')


def count_color(img, rgb, tol=28):
    w, h = img.size
    px = img.load()
    n = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            p = px[x, y]
            if all(abs(p[i] - rgb[i]) <= tol for i in range(3)):
                n += 1
    return n


fails = []
for key in ('modern_a4', 'classic_a4', 'legal_notice_99a', 'digital_slip',
            'command_brief', 'secure_instrument', 'urdu_executive'):
    pdf = OUT / f'{key}.pdf'
    raw = pdftotext(pdf)
    txt = norm(raw)
    img = page_image(pdf)
    w, h = img.size
    nonwhite = sum(1 for p in img.getdata() if sum(p) < 720) / (w * h)

    for b in BANNED_TEXT:
        if norm(b) in txt:
            fails.append(f'{key}: banned text present: {b!r}')
    for req in REQUIRED_TEXT[key]:
        if norm(req) not in txt:
            fails.append(f'{key}: required text missing: {req!r}')
    if nonwhite < 0.04:
        fails.append(f'{key}: page nearly blank')

    if key == 'command_brief':
        green = count_color(img, (21, 128, 61))
        crimson = count_color(img, (185, 28, 28))
        amber = count_color(img, (217, 119, 6))
        navy = count_color(img, (11, 31, 58))
        print(f'command_brief: green={green} crimson={crimson} amber={amber} navy={navy}')
        if green < 30: fails.append('command_brief: direction panel green missing')
        if crimson < 30: fails.append('command_brief: observed-lane crimson/arrow missing')
        if amber < 15: fails.append('command_brief: amber corner ticks missing')
        if navy < 200: fails.append('command_brief: navy structure missing')

    if key == 'secure_instrument':
        best = (0, -1)
        for frac in [i / 400 for i in range(0, 121)]:
            y0, y1 = int(h * frac), int(h * frac) + 10
            crop = img.crop((int(w * 0.1), y0, int(w * 0.9), min(y1, h)))
            dc = len(set(crop.getdata()))
            if dc > best[1]:
                best = (frac, dc)
        print(f'secure_instrument: best hatch strip at {best[0]:.1%} distinct={best[1]}')
        if best[1] < 25:
            fails.append('secure_instrument: guilloche hatch band missing')
        dashes = count_color(img, (107, 122, 144))
        if dashes < 20:
            fails.append('secure_instrument: counterfoil perforation dashes missing')

    if key == 'urdu_executive':
        emerald = count_color(img, (6, 95, 70))
        print(f'urdu_executive: emerald={emerald}')
        if emerald < 30:
            fails.append('urdu_executive: emerald structure missing')

    status = 'OK' if not [f for f in fails if f.startswith(key + ':')] else 'FAIL'
    print(f'{key}: {status} (nonwhite={nonwhite:.3f})')

print()
if fails:
    print('FAILURES:')
    for f in fails:
        print(' -', f)
    sys.exit(1)
print('ALL PROGRAMMATIC QA CHECKS PASSED')
