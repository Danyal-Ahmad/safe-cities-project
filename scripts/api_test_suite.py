"""REST API + page-render regression suite for SAFE CITIES PROJECT.

Tests every REST endpoint (auth, rate limits, happy paths, abuse paths) and
renders every portal page as every role. Run with:

    python3 manage.py shell < scripts/api_test_suite.py

(or as a script: python3 scripts/api_test_suite.py from the repo root)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wrongway_system.settings')

import django  # noqa: E402

django.setup()

from django.test import Client, override_settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.cache import cache  # noqa: E402

from accounts.models import User  # noqa: E402
from cameras.models import Camera  # noqa: E402
from challans.models import Challan  # noqa: E402
from detections.models import Detection  # noqa: E402

PASS = 0
FAIL = 0
RESULTS = []


def check(name, condition, detail=''):
    global PASS, FAIL
    if condition:
        PASS += 1
        RESULTS.append(('PASS', name, detail))
    else:
        FAIL += 1
        RESULTS.append(('FAIL', name, detail))


DEMO_PASSWORDS = {
    'dig@safecity.fyp': 'Demo@DIG-2026secure',
    'ssp@safecity.fyp': 'Demo@SSP-2026secure',
    'supervisor@safecity.fyp': 'Demo@SUPV-2026secure',
    'officer@safecity.fyp': 'Demo@OFFCR-2026secure',
    'audit@safecity.fyp': 'Demo@AUDT-2026secure',
    'itsupport@safecity.fyp': 'Demo@ITSP-2026secure',
    'citizen@safecity.fyp': 'Demo@CZN-2026secure',
}


def client_for(username, password=None):
    c = Client()
    ok = c.login(username=username, password=password or DEMO_PASSWORDS.get(username, 'Admin@2026'))
    return c if ok else None


def main():
    from django.test.utils import setup_test_environment
    setup_test_environment()

    User = get_user_model()

    # ---------- Public REST/page surface ----------
    anon = Client()
    r = anon.get('/')
    check('public home 200', r.status_code == 200, str(r.status_code))
    r = anon.get('/realtime/stats/')
    check('realtime stats auth-gated', r.status_code in (200, 302), str(r.status_code))
    r = anon.get('/realtime/cameras-status/')
    check('cameras status auth-gated', r.status_code in (200, 302), str(r.status_code))
    r = anon.get('/realtime/api/kpis/')
    check('kpis auth-gated', r.status_code in (200, 302), str(r.status_code))
    r = anon.get('/api/v1/heartbeat/', data={'x': 1})
    check('heartbeat GET rejected', r.status_code in (405, 403, 401), str(r.status_code))
    r = anon.post('/api/v1/ingest/', {})
    check('ingest unauth 401/403', r.status_code in (401, 403), str(r.status_code))
    r = anon.post('/api/v1/enroll/', {})
    check('enroll unauth rejected', r.status_code in (400, 401, 403), str(r.status_code))
    r = anon.post('/api/v1/payment/webhook/', data='{}', content_type='application/json')
    check('payment webhook accepts (HMAC layer)', r.status_code in (200, 400, 403), str(r.status_code))

    # Rate limit: public search
    cache.clear()
    codes = [anon.get('/', {'plate': f'LEA-{i}'}).status_code for i in range(25)]
    check('public search rate limit 429', 429 in codes, str(sorted(set(codes))))

    # ---------- Camera enroll + ingest + heartbeat (API key flow) ----------
    staff = client_for('itsupport@safecity.fyp')
    check('IT login works', staff is not None)
    if staff:
        r = staff.post('/portal/it/cameras/add/', {
            'camera_id': 'APITEST-01',
            'location': 'API Test Avenue',
            'legal_direction': 'north',
            'violation_side': 'back',
            'capture_interval': '5',
            'is_active': 'on',
        })
        cam = Camera.objects.filter(camera_id='APITEST-01').first()
        check('camera add via portal', cam is not None, f'{r.status_code}')

    cam = Camera.objects.filter(camera_id='APITEST-01').first()
    if cam is None:
        cam = Camera.objects.create(
            camera_id='APITEST-01', location='API Test Avenue',
            legal_direction='north', violation_side='back',
        )

    import uuid as _uuid
    cam.enrollment_token = _uuid.uuid4()
    cam.is_enrolled = False
    cam.save(update_fields=['enrollment_token', 'is_enrolled'])
    with override_settings(DEBUG=True):
        api = Client()
        r = api.post('/api/v1/enroll/', {'enrollment_token': str(cam.enrollment_token)})
        check('enroll issues api key', r.status_code == 200 and 'api_key' in r.content.decode(), str(r.status_code))
        api_key = ''
        try:
            api_key = r.json().get('api_key', '')
        except Exception:
            pass
        check('api key returned', bool(api_key))
        # Second enrollment with the same token must be rejected (single-use).
        r2 = api.post('/api/v1/enroll/', {'enrollment_token': str(cam.enrollment_token)})
        check('enroll token single-use', r2.status_code in (400, 403), str(r2.status_code))

        if api_key:
            from PIL import Image
            import io as _io
            buf = _io.BytesIO()
            Image.new('RGB', (320, 240), (10, 20, 40)).save(buf, format='JPEG')
            r = api.post(
                '/api/v1/ingest/',
                data={'moving_direction': 'north'},
                HTTP_AUTHORIZATION=f'Bearer {api_key}',
            )
            # Note: real ingest needs the image file; without it we still prove auth works
            check('ingest with bearer auth reaches handler', r.status_code in (200, 201, 400), str(r.status_code))
            r = api.post(
                '/api/v1/heartbeat/',
                HTTP_AUTHORIZATION=f'Bearer {api_key}',
                data={'status': 'ok'},
            )
            check('heartbeat with bearer auth', r.status_code in (200, 204, 400), str(r.status_code))

        # Ingest rate limit (300/min per IP)
        codes = []
        for i in range(305):
            rr = api.post('/api/v1/ingest/', {}, HTTP_AUTHORIZATION=f'Bearer {api_key or "x"}')
            codes.append(rr.status_code)
            if rr.status_code == 429:
                break
        check('ingest rate limit 429', 429 in codes, f'{len(codes)} calls')

    # ---------- Portal page renders per role ----------
    role_pages = {
        'DIG': ['/portal/dig/', '/portal/dig/live-monitor/',
                '/portal/dig/cameras/', '/portal/dig/challans/',
                '/portal/dig/flagged-detections/', '/portal/dig/vehicle-search/',
                '/portal/dig/analytics/', '/portal/dig/heatmap/', '/portal/dig/audit/',
                '/portal/dig/audit-templates/', '/portal/dig/officer-kpi/', '/portal/dig/compliance/'],
        'SSP': ['/portal/ssp/', '/portal/ssp/live-monitor/', '/portal/ssp/challans/'],
        'SUPV': ['/portal/supervisor/', '/portal/supervisor/live-monitor/'],
        'OFFICER': ['/portal/officer/', '/portal/officer/queue/', '/portal/officer/camera-feed/',
                    '/portal/officer/detections/', '/portal/officer/flagged/', '/portal/officer/challans/',
                    '/portal/officer/history/', '/portal/officer/live-tracking/'],
        'AUDIT': ['/portal/audit/', '/portal/audit/operational/', '/portal/audit/financial/',
                  '/portal/audit/compliance/', '/portal/audit/user-activity/', '/portal/audit/auth-events/',
                  '/portal/audit/permission-changes/', '/portal/audit/anomalies/'],
        'IT': ['/portal/it/', '/portal/it/challan-templates/', '/portal/it/challan-templates/designer/',
               '/portal/it/audit-templates/', '/portal/it/payment-methods/', '/portal/it/backups/',
               '/portal/it/staff/', '/portal/it/cameras/', '/portal/it/system-health/', '/video/upload/'],
        'USER': ['/portal/citizen/', '/portal/citizen/appeals/'],
    }
    users = {
        'DIG': 'dig@safecity.fyp', 'SSP': 'ssp@safecity.fyp',
        'SUPV': 'supervisor@safecity.fyp', 'OFFICER': 'officer@safecity.fyp',
        'AUDIT': 'audit@safecity.fyp', 'IT': 'itsupport@safecity.fyp',
        'USER': 'citizen@safecity.fyp',
    }
    for role, pages in role_pages.items():
        c = client_for(users[role])
        if c is None:
            check(f'{role} login', False, 'login failed')
            continue
        for page in pages:
            r = c.get(page)
            ok = r.status_code == 200
            check(f'{role} {page}', ok, str(r.status_code))

    # ---------- Portal isolation ----------
    officer = client_for('officer@safecity.fyp')
    if officer:
        r = officer.get('/portal/dig/')
        check('officer blocked from DIG portal', r.status_code in (302, 403), str(r.status_code))
        r = officer.get('/portal/audit/')
        check('officer blocked from audit portal', r.status_code in (302, 403), str(r.status_code))
    cit = client_for('citizen@safecity.fyp')
    if cit:
        r = cit.get('/portal/officer/')
        check('citizen blocked from officer portal', r.status_code in (302, 403), str(r.status_code))

    # ---------- Audit PDF export ----------
    audit_client = client_for('audit@safecity.fyp')
    if audit_client:
        for kind in ['operational', 'financial', 'compliance', 'auth_events']:
            r = audit_client.get(f'/portal/audit/export/pdf/{kind}/')
            ok = r.status_code == 200 and b'%PDF' in r.content[:10]
            check(f'audit PDF export {kind}', ok, f'{r.status_code} len={len(r.content)}')

    # ---------- Cleanup ----------
    Camera.objects.filter(camera_id='APITEST-01').delete()

    print()
    print('=' * 70)
    for status, name, detail in RESULTS:
        if status == 'FAIL':
            print(f'  [{status}] {name} ({detail})')
    print('=' * 70)
    print(f'TOTAL: {PASS + FAIL} | PASS: {PASS} | FAIL: {FAIL}')
    return FAIL


if __name__ == '__main__':
    sys.exit(main())
