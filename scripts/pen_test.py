#!/usr/bin/env python3
"""SAFE CITIES PROJECT - security regression / penetration-test harness.

Double-duty script (repo root): it is both the evidence run for the 2026
hardening pass and a reusable regression suite. It uses the Django test
client against the REAL settings module with DEBUG forced off, so the
production code paths (CSP, secure cookies, rate limits, auth gates) are
exercised exactly as a browser/attacker would see them.

Proofs covered (see docs/SECURITY_AUDIT.md for the full findings matrix):

  T1  Anonymous /challan/<id>/pdf/ is blocked (IDOR) - no token, ticket_no
      as token, numeric id as token and tampered signatures all 403; only a
      valid TimestampSigner token renders the PDF.
  T2  /api/v1/ingest/ per-IP limit (300/min) trips a JSON 429 - proven with
      unauthenticated traffic so the AI pipeline never runs; heartbeat
      (120/min) and demo-checkout (30/min) limits proven the same way, and
      a VALID Bearer heartbeat still succeeds first (csrf_exempt + auth
      under the limiter are intact).
  T3  XSS payloads in the public search (plate / q / cnic) are neutralised.
  T4  Role / is_staff mass-assignment on citizen signup is rejected.
  T5  IT backup_download path traversal is blocked (basename sanitisation).
  T6  DIG dashboard renders fully (200) with the production CSP header, a
      per-request nonce that changes between requests, no 'unsafe-eval',
      DENY framing, and the ?embed=1 profile exception.
  T7  The custom 429 handler renders properly - JSON on /api/ paths, the
      shared error page elsewhere (proven via the PDF download limit).

Run:  python3 scripts/pen_test.py     (exit code 0 = all proofs passed)
"""
import os
import sys
import secrets
from pathlib import Path

# --- harness bootstrap -------------------------------------------------------
# Force the PRODUCTION code paths (DEBUG=False ⇒ production CSP, secure
# cookies) while keeping the DB/settings real. A strong random SECRET_KEY and
# an explicit ALLOWED_HOSTS satisfy the DEBUG=False guards in settings.py.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wrongway_system.settings')
os.environ['DEBUG'] = 'False'
os.environ['SECRET_KEY'] = 'pen-test-harness-' + secrets.token_hex(24)
os.environ['ALLOWED_HOSTS'] = 'testserver,127.0.0.1,localhost'

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

# Harness-only: the test client speaks plain http; SECURE_SSL_REDIRECT would
# turn every request into a 301. TLS is terminated at the edge in production.
settings.SECURE_SSL_REDIRECT = False

from django.test import Client  # noqa: E402
from django.core.signing import TimestampSigner  # noqa: E402

# --- results plumbing --------------------------------------------------------
RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(('  [PASS] ' if ok else '  [FAIL] ') + name + (f' - {detail}' if detail else ''))


def section(title):
    print(f'\n=== {title} ' + '=' * max(0, 60 - len(title)))


# --- fixture data (created + removed around the run) --------------------------
SUFFIX = secrets.token_hex(4).upper()
# 13 digits derived from the random suffix → unique CNIC / phone per run,
# so signup never collides with seeded demo accounts in the dev database.
_DIG = str(int(SUFFIX, 16)).zfill(13)[:13]
PEN_CNIC = f'{_DIG[:5]}-{_DIG[5:12]}-{_DIG[12]}'
FIXTURE = {}


def make_fixture():
    from challans.models import Challan
    from accounts.models import User
    from cameras.models import Camera
    from django.utils import timezone

    FIXTURE['challan'] = Challan.objects.create(
        ticket_no=f'PEN{SUFFIX}01', plate_number=f'PEN-{SUFFIX[:3]}',
        cnic=PEN_CNIC, owner_name='Pen Test Owner',
        phone='+923009988776', address='Pen Test Street 1',
        chassis_no='PEN-CHASSIS-1', violation_type='wrong_way',
        fine_amount=500, location='Pen Test Boulevard',
        issue_date=timezone.localdate(),
        due_date=timezone.localdate() + timezone.timedelta(days=14),
    )
    FIXTURE['dig'] = User.objects.create_user(
        username=f'pendig{SUFFIX}', password='PenTest!Passphrase#2026',
        email=f'pendig{SUFFIX}@pentest.local', first_name='Pen DIG',
        role=User.DIG,
    )
    FIXTURE['it'] = User.objects.create_user(
        username=f'penit{SUFFIX}', password='PenTest!Passphrase#2026',
        email=f'penit{SUFFIX}@pentest.local', first_name='Pen IT',
        role=User.IT_SUPPORT,
    )
    FIXTURE['camera'] = Camera.objects.create(
        camera_id=f'PENCAM-{SUFFIX}', location='Pen Test Corner', is_active=True,
    )


def drop_fixture():
    for key in ('signup', 'signup2', 'challan', 'dig', 'it', 'camera'):
        obj = FIXTURE.get(key)
        if obj is None:
            continue
        if key == 'challan':
            try:
                if obj.pdf_file:
                    p = Path(obj.pdf_file.path)
                    if p.is_file():
                        p.unlink()
            except Exception:
                pass
        try:
            obj.delete()
        except Exception:
            pass


# --- proofs ------------------------------------------------------------------
def t1_pdf_idor():
    section('T1 - anonymous challan PDF (IDOR)')
    c = Client()
    cid = FIXTURE['challan'].pk
    url = f'/challan/{cid}/pdf/'

    r = c.get(url)
    check('no token -> 403', r.status_code == 403, f'got {r.status_code}')
    r = c.get(url, {'token': FIXTURE['challan'].ticket_no})
    check('ticket_no as token -> 403', r.status_code == 403, f'got {r.status_code}')
    r = c.get(url, {'token': str(cid)})
    check('numeric id as token -> 403', r.status_code == 403, f'got {r.status_code}')
    signer = TimestampSigner()
    tampered = signer.sign(str(cid))[:-2] + 'xy'
    r = c.get(url, {'token': tampered})
    check('tampered signature -> 403', r.status_code == 403, f'got {r.status_code}')
    r = c.get(url, {'token': signer.sign(str(cid + 1))})
    check('token for another challan -> 403', r.status_code == 403, f'got {r.status_code}')

    r = c.get(url, {'token': signer.sign(str(cid))})
    check('valid signed token -> 200 application/pdf',
          r.status_code == 200 and r['Content-Type'] == 'application/pdf',
          f'got {r.status_code} {r.get("Content-Type", "")}')


def t2_api_rate_limits():
    section('T2 - camera/payment API rate limits (429)')
    cam = FIXTURE['camera']
    c = Client()

    # Bearer + csrf_exempt proof: a heartbeat WITHOUT any CSRF token must
    # still succeed (these are machine endpoints), then the limit trips.
    r = c.post('/api/v1/heartbeat/', HTTP_AUTHORIZATION=f'Bearer {cam.api_key}')
    check('valid-Bearer heartbeat (no CSRF token) -> 200',
          r.status_code == 200, f'got {r.status_code}')
    r = c.post('/api/v1/heartbeat/', HTTP_AUTHORIZATION='Bearer not-a-uuid')
    check('garbage Bearer -> 403 (auth intact under limiter)',
          r.status_code == 403, f'got {r.status_code}')

    # ingest: 300/min per IP. Unauthenticated traffic costs no AI pipeline -
    # the limiter sits above the auth check, so flooders get 429 cheap.
    codes = [c.post('/api/v1/ingest/').status_code for _ in range(302)]
    check('ingest limit trips 429 after 300/min',
          429 in codes and codes[:300] == [403] * 300,
          f'{codes.count(403)}x403 then 429={codes.count(429)}')
    r = c.post('/api/v1/ingest/')
    check('ingest 429 is JSON with retry hint',
          r.status_code == 429 and 'rate_limited' in r.content.decode()
          and r['Content-Type'].startswith('application/json')
          and r.get('Retry-After') is not None,
          f'{r.status_code} {r.get("Content-Type", "")}')

    # heartbeat: 120/min per IP (one valid request already consumed a slot).
    codes = [c.post('/api/v1/heartbeat/').status_code for _ in range(130)]
    check('heartbeat limit trips 429 after 120/min', 429 in codes,
          f'403={codes.count(403)} 429={codes.count(429)}')

    # demo checkout: 30/min per IP on POST.
    codes = [c.post('/api/v1/payment/demo-checkout/',
                    {'ref': 'PEN-FORGED', 'status': 'paid'}).status_code
             for _ in range(32)]
    check('demo-checkout POST limit trips 429 after 30/min',
          429 in codes and 400 in codes,
          f'400={codes.count(400)} 429={codes.count(429)}')
    # forged reference never settles anything
    FIXTURE['challan'].refresh_from_db()
    check('forged demo reference never marks PAID',
          FIXTURE['challan'].payment_status == 'UNPAID')


def t3_xss_neutralised():
    section('T3 - reflected XSS in public search')
    c = Client()
    payloads = [
        '<script>alert(1)</script>',
        '"><img src=x onerror=alert(1)>',
        "javascript:alert(document.cookie)",
    ]
    for p in payloads:
        r = c.get('/', {'plate': p})
        body = r.content.decode()
        clean = ('alert(1)' not in body
                 and 'onerror=alert' not in body
                 and 'javascript:alert' not in body)
        ok = r.status_code == 200 and clean
        check(f'plate={p[:24]!r} neutralised', ok,
              f'status={r.status_code} reflected-clean={clean}')
    r = c.get('/', {'q': '<script>alert(1)</script>'})
    check('q= script tag neutralised',
          r.status_code == 200 and 'alert(1)' not in r.content.decode())
    r = c.get('/', {'cnic': "35202-1234567-8' OR '1'='1"})
    body = r.content.decode()
    check('SQLi in cnic param is harmless (ORM only)',
          r.status_code in (200, 429) and 'Pen Test Owner' not in body,
          f'status={r.status_code}')


def t4_role_injection():
    section('T4 - mass assignment on citizen signup')
    c = Client()
    phone = f'+92{_DIG[:11]}'
    r = c.post('/auth/citizen/signup/', {
        'first_name': 'Reg Probe',
        'phone': phone,
        'email': f'reg{_DIG[:6]}@pentest.local',
        'cnic': PEN_CNIC,
        'password1': 'PenTest!Passphrase#2026',
        'password2': 'PenTest!Passphrase#2026',
        'role': 'DIG',          # must be ignored
        'is_staff': 'on',       # must be ignored
        'is_superuser': 'on',   # must be ignored
    })
    from accounts.models import User
    u = User.objects.filter(username=phone).first()
    FIXTURE['signup'] = u
    check('signup succeeds and forces role=USER',
          u is not None and u.role == 'USER',
          f'role={u.role if u else None!r}')
    check('is_staff / is_superuser not injectable',
          u is not None and not u.is_staff and not u.is_superuser,
          f'staff={u.is_staff if u else None} super={u.is_superuser if u else None}')

    # Phone-only signup used to 500 (IntegrityError: email NOT NULL) - fixed
    # in auth_portal/views.citizen_signup during this hardening pass. Fresh
    # client: this session is already logged in from the first signup.
    phone2 = f'+92{_DIG[:11]}7'
    c2 = Client()
    r2 = c2.post('/auth/citizen/signup/', {
        'first_name': 'Phone Only',
        'phone': phone2,
        'password1': 'PenTest!Passphrase#2026',
        'password2': 'PenTest!Passphrase#2026',
        'role': 'DIG',
    })
    u2 = User.objects.filter(username=phone2).first()
    FIXTURE['signup2'] = u2
    check('phone-only signup no longer 500s (email NOT NULL coerced)',
          r2.status_code in (200, 302) and u2 is not None and u2.role == 'USER',
          f'status={r2.status_code} created={u2 is not None}')


def t5_backup_traversal():
    section('T5 - IT backup download path traversal')
    c = Client()
    ok_login = c.login(username=FIXTURE['it'].username, password='PenTest!Passphrase#2026')
    check('IT user can log in', ok_login)
    signatures = {
        '../../manage.py': b'execute_from_command_line',
        '../../../wrongway_system/settings.py': b'PG_PASSWORD',
        '..%2e%2e%2fmanage.py': b'execute_from_command_line',
        '/etc/passwd': b'root:x:',
        '....//manage.py': b'execute_from_command_line',
    }
    for payload, marker in signatures.items():
        r = c.get(f'/portal/it/backups/download/{payload}/')
        leaked = marker in r.content
        check(f'{payload[:28]!r} blocked (no file leak)',
              r.status_code in (301, 302, 404) and not leaked,
              f'status={r.status_code} leaked={leaked}')
    # sanity: the endpoint still works for a real .json backup name
    from pathlib import Path as _P
    backups = _P(settings.BASE_DIR) / 'backups'
    backups.mkdir(exist_ok=True)
    legit = backups / f'pentest_{SUFFIX}.json'
    legit.write_text('{"pen": true}')
    try:
        r = c.get(f'/portal/it/backups/download/{legit.name}/')
        body = b''.join(r.streaming_content) if r.status_code == 200 else b''
        check('legit .json backup still downloads',
              r.status_code == 200 and b'{"pen": true}' in body,
              f'status={r.status_code}')
    finally:
        legit.unlink(missing_ok=True)


def t6_dig_dashboard_csp():
    section('T6 - DIG dashboard renders with production CSP + nonce')
    c = Client()
    ok_login = c.login(username=FIXTURE['dig'].username, password='PenTest!Passphrase#2026')
    check('DIG user can log in', ok_login)
    r1 = c.get('/portal/dig/')
    check('dashboard GET -> 200 and fully rendered',
          r1.status_code == 200 and len(r1.content) > 3000,
          f'status={r1.status_code} bytes={len(r1.content)}')
    csp1 = r1.get('Content-Security-Policy', '')
    nonce1 = getattr(r1.wsgi_request, 'csp_nonce', None)
    check('CSP header present with nonce',
          csp1.startswith("default-src 'self'") and "'nonce-" in csp1 and bool(nonce1),
          'nonce=' + str(nonce1)[:12] + '…')
    check('script nonce attribute rendered in body',
          f'nonce="{nonce1}"' in r1.content.decode())
    check("no 'unsafe-eval' in production CSP", 'unsafe-eval' not in csp1)
    for token in ("form-action 'self' https:", "object-src 'none'",
                  "base-uri 'self'", "frame-ancestors 'none'",
                  "connect-src 'self'", "img-src 'self' data: blob: https:"):
        check(f'CSP contains {token!r}', token in csp1)
    check('X-Frame-Options DENY on normal pages',
          r1.get('X-Frame-Options') == 'DENY')
    r2 = c.get('/portal/dig/')
    nonce2 = getattr(r2.wsgi_request, 'csp_nonce', None)
    check('nonce is per-request (changes between requests)',
          bool(nonce2) and nonce2 != nonce1)
    re = c.get('/portal/dig/profile/', {'embed': '1'})
    check('?embed=1 profile keeps frame-ancestors self exception',
          "frame-ancestors 'self'" in re.get('Content-Security-Policy', '')
          and re.get('X-Frame-Options') == 'SAMEORIGIN',
          f'status={re.status_code}')


def t7_429_rendering():
    section('T7 - custom 429 handler rendering')
    c = Client()
    signer = TimestampSigner()
    token = signer.sign(str(FIXTURE['challan'].pk))
    url = f'/challan/{FIXTURE["challan"].pk}/pdf/?token={token}'
    saw429 = False
    last = None
    for _ in range(30):
        last = c.get(url)
        if last.status_code == 429:
            saw429 = True
            break
    check('PDF download limit (20/min user-or-IP) trips 429', saw429,
          f'last={last.status_code if last is not None else None}')
    if saw429:
        body = last.content.decode()
        check('non-API 429 renders the shared error page (HTML)',
              last['Content-Type'].startswith('text/html')
              and 'Too Many Requests' in body,
              f'{last["Content-Type"]}')


def main():
    print('SAFE CITIES PROJECT | pen-test / security regression harness')
    print(f'DEBUG={settings.DEBUG}  ALLOWED_HOSTS={settings.ALLOWED_HOSTS}')
    try:
        make_fixture()
        t1_pdf_idor()
        t2_api_rate_limits()
        t3_xss_neutralised()
        t4_role_injection()
        t5_backup_traversal()
        t6_dig_dashboard_csp()
        t7_429_rendering()
    finally:
        drop_fixture()

    failed = [r for r in RESULTS if not r[1]]
    print('\n' + '=' * 72)
    print(f'RESULT: {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed'
          + (f' - {len(failed)} FAILED' if failed else ' - ALL GREEN'))
    for name, _, detail in failed:
        print(f'  FAILED: {name} ({detail})')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
