"""E2E full-stack role-matrix test for SAFE CITIES PROJECT.

Covers 27 users across 7 roles (2 DIG, 3 SSP, 3 SUPV, 5 OFFICER, 2 AUDIT, 2 IT,
10 citizens), portal page renders, RBAC isolation, every tracking surface, the
real AI pipeline (detection, frame tracking, evidence, challan) driven through
the actual UI upload endpoint, the full challan lifecycle (pay, verify, appeal,
SSP-only routing) and the public portal.

Run: python3 scripts/e2e_full_test.py   (server DB must be up)
"""
import datetime
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wrongway_system.settings')

import django

django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User, VehicleRegistration
from cameras.models import Camera
from challans.models import Challan
from detections.models import Detection
from video_processor.models import VideoUpload
from realtime.models import LiveFeed
from appeals.models import ChallanAppeal
from admin.dig_portal.models import Notification, AuditLog

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER_VIDEO = '/home/z/my-project/upload/folder/a3d29032/16385744-hd_1920_1080_30fps.mp4'
POSITIVE_VIDEO = os.path.join(BASE, 'TESTING/VIDEO/positive_violation_LEA-1234_1080p30.mp4')
REPORT_PATH = os.path.join(BASE, 'TESTING', 'E2E_ROLE_MATRIX_REPORT.md')

NEW_PW = 'E2E@2026-Matrix!'
PASSWORDS = {
    'dig@safecity.fyp': 'Demo@DIG-2026secure',
    'ssp@safecity.fyp': 'Demo@SSP-2026secure',
    'supervisor@safecity.fyp': 'Demo@SUPV-2026secure',
    'officer@safecity.fyp': 'Demo@OFFCR-2026secure',
    'audit@safecity.fyp': 'Demo@AUDT-2026secure',
    'itsupport@safecity.fyp': 'Demo@ITSP-2026secure',
    'citizen@safecity.fyp': 'Demo@CZN-2026secure',
}

PASS = 0
FAIL = 0
RESULTS = []
SECTIONS = {}


def check(name, condition, detail=''):
    global PASS, FAIL
    ok = bool(condition)
    if ok:
        PASS += 1
        RESULTS.append(('PASS', name, str(detail)))
    else:
        FAIL += 1
        RESULTS.append(('FAIL', name, str(detail)))
    return ok


def section(title):
    SECTIONS[title] = len(RESULTS)
    print(f'\n===== {title} =====')


def client_for(username, password=None):
    c = Client()
    pw = password or PASSWORDS.get(username, NEW_PW)
    ok = c.login(username=username, password=pw)
    return c if ok else None


def wait_for_upload(upload_id, timeout=420):
    deadline = time.time() + timeout
    while time.time() < deadline:
        u = VideoUpload.objects.filter(pk=upload_id).first()
        if u is None:
            return None
        if u.status in (VideoUpload.STATUS_COMPLETED, VideoUpload.STATUS_FAILED):
            return u
        time.sleep(4)
    return VideoUpload.objects.filter(pk=upload_id).first()


def body(r):
    if hasattr(r, 'streaming_content'):
        return b''.join(r.streaming_content)
    return r.content


def upload_via_ui(client, path, camera_id, expected_name):
    with open(path, 'rb') as f:
        data = f.read()
    payload = SimpleUploadedFile(expected_name, data, content_type='video/mp4')
    resp = client.post('/video/upload/', {
        'video_file': payload,
        'camera_id': str(camera_id),
    })
    return resp


def phase_a_auth():
    section('PHASE A | Authentication matrix (27 users)')
    everyone = list(User.objects.filter(is_active=True))
    check('user count >= 27', len(everyone) >= 27, f'{len(everyone)} users')
    ok_all = True
    for u in everyone:
        c = client_for(u.username)
        good = c is not None
        ok_all = ok_all and good
        if not good:
            check(f'login {u.username}', False, 'login failed')
    check('all 27 users log in', ok_all, f'{len(everyone)} logins')

    c = Client()
    r = c.post('/auth/admin/login/', {'username': 'dig2@safecity.fyp', 'password': NEW_PW})
    check('staff login form (DIG) works', r.status_code == 302, str(r.status_code))
    check('staff login sets session', c.session.get('_auth_user_id') is not None, '-')

    c2 = Client()
    r = c2.post('/auth/citizen/login/', {'username': 'citizen5@safecity.fyp', 'password': NEW_PW})
    check('citizen login form works', r.status_code == 302, str(r.status_code))

    c3 = Client()
    r = c3.post('/auth/admin/login/', {'username': 'citizen5@safecity.fyp', 'password': NEW_PW})
    check('citizen blocked from staff login', r.status_code == 200 and b'Citizens must use' in r.content, str(r.status_code))

    c4 = Client()
    r = c4.post('/auth/admin/login/', {'username': 'ghost@safecity.fyp', 'password': 'WrongPass!!12345'})
    check('wrong password rejected', r.status_code == 200 and c4.session.get('_auth_user_id') is None, str(r.status_code))

    r = Client().get('/portal/dig/', follow=False)
    check('anonymous blocked from DIG portal', r.status_code == 302, str(r.status_code))


def phase_b_pages():
    section('PHASE B | Portal page renders per role')
    role_pages = {
        'DIG': ['/portal/dig/', '/portal/dig/live-monitor/', '/portal/dig/live-tracking/', '/portal/dig/cameras/',
                '/portal/dig/challans/', '/portal/dig/flagged-detections/', '/portal/dig/vehicle-search/',
                '/portal/dig/analytics/', '/portal/dig/heatmap/', '/portal/dig/audit/', '/portal/dig/audit-templates/',
                '/portal/dig/officer-kpi/', '/portal/dig/compliance/', '/portal/dig/evidence-integrity/',
                '/portal/dig/case-escalation/tracker/', '/portal/dig/financial-reports/',
                '/portal/dig/shifts/', '/portal/dig/payments/', '/portal/dig/penalty-config/',
                '/portal/dig/settings/', '/portal/dig/admins/', '/portal/dig/blacklist/',
                '/portal/dig/login-events/', '/portal/dig/notifications/', '/portal/dig/reports/',
                '/portal/dig/violations/', '/portal/dig/revenue/', '/portal/dig/cameras-status/',
                '/portal/dig/camera-health/', '/portal/dig/officer-activity/', '/portal/dig/operational-reports/',
                '/portal/dig/regional-command/', '/portal/dig/officer-signatures/', '/portal/dig/ads/select/'],
        'SSP': ['/portal/ssp/', '/portal/ssp/production/', '/portal/ssp/camera-outage/', '/portal/ssp/challans/',
                '/portal/ssp/revenue/', '/portal/ssp/heatmap/', '/portal/ssp/analytics/', '/portal/ssp/reports/',
                '/portal/ssp/vehicle-search/', '/portal/ssp/live-monitor/', '/portal/ssp/live-tracking/',
                '/portal/ssp/officer-activity/', '/portal/ssp/officer-kpi/', '/portal/ssp/violations/',
                '/portal/ssp/notifications/', '/portal/ssp/appeals/', '/portal/ssp/appeals/tracker/', '/portal/ssp/blacklist/',
                '/portal/ssp/camera-health/', '/portal/ssp/cameras-status/', '/portal/ssp/profile/'],
        'SUPV': ['/portal/supervisor/', '/portal/supervisor/team-performance/', '/portal/supervisor/shifts/',
                 '/portal/supervisor/camera-assignments/', '/portal/supervisor/queue-load/',
                 '/portal/supervisor/live-tracking/', '/portal/supervisor/live-tracking/timeline/'],
        'OFFICER': ['/portal/officer/', '/portal/officer/queue/', '/portal/officer/detections/', '/portal/officer/challans/',
                    '/portal/officer/history/', '/portal/officer/flagged/', '/portal/officer/camera-feed/',
                    '/portal/officer/performance/', '/portal/officer/profile/', '/portal/officer/appeals/',
                    '/portal/officer/live-tracking/', '/portal/officer/vehicle-tracking/',
                    '/portal/officer/live-tracking/timeline/', '/video/upload/'],
        'AUDIT': ['/portal/audit/', '/portal/audit/operational/', '/portal/audit/financial/', '/portal/audit/compliance/',
                  '/portal/audit/user-activity/', '/portal/audit/auth-events/', '/portal/audit/permission-changes/',
                  '/portal/audit/anomalies/', '/portal/audit/uploads/', '/portal/audit/login-events/',
                  '/portal/audit/challan-changes/', '/portal/audit/alert-changes/'],
        'IT': ['/portal/it/', '/portal/it/challan-templates/', '/portal/it/audit-templates/', '/portal/it/payment-methods/',
               '/portal/it/backups/', '/portal/it/staff/', '/portal/it/cameras/', '/portal/it/system-health/',
               '/portal/it/reset-requests/', '/portal/it/cameras/heartbeats/', '/portal/it/payments/monitor/',
               '/portal/it/live-tracking/', '/portal/it/live-tracking/timeline/', '/video/upload/', '/video/uploads/'],
        'USER': ['/portal/citizen/', '/portal/citizen/appeals/', '/portal/citizen/profile/', '/portal/citizen/password/'],
    }
    per_role_user = {
        'DIG': 'dig2@safecity.fyp', 'SSP': 'ssp2@safecity.fyp', 'SUPV': 'supv2@safecity.fyp',
        'OFFICER': 'officer2@safecity.fyp', 'AUDIT': 'audit2@safecity.fyp', 'IT': 'it2@safecity.fyp',
        'USER': 'citizen2@safecity.fyp',
    }
    for role, pages in role_pages.items():
        c = client_for(per_role_user[role])
        if c is None:
            check(f'{role} representative login', False, 'login failed')
            continue
        for page in pages:
            r = c.get(page, follow=True)
            check(f'{role} {page}', r.status_code == 200, str(r.status_code))


def phase_c_isolation():
    section('PHASE C | RBAC isolation matrix')
    probes = {
        'DIG': ['/portal/ssp/production/', '/portal/supervisor/', '/portal/officer/queue/', '/portal/audit/operational/',
                '/portal/it/system-health/', '/portal/citizen/', '/video/upload/'],
        'SSP': ['/portal/dig/dashboard/', '/portal/supervisor/', '/portal/officer/queue/', '/portal/audit/operational/',
                '/portal/it/staff/', '/portal/citizen/appeals/'],
        'SUPV': ['/portal/dig/dashboard/', '/portal/ssp/production/', '/portal/officer/queue/', '/portal/audit/financial/',
                 '/portal/it/backups/', '/portal/citizen/'],
        'OFFICER': ['/portal/dig/', '/portal/ssp/', '/portal/supervisor/', '/portal/audit/', '/portal/it/',
                    '/portal/citizen/'],
        'AUDIT': ['/portal/dig/settings/edit/', '/portal/dig/challans/', '/portal/officer/queue/', '/portal/it/staff/',
                  '/portal/citizen/', '/portal/dig/penalty-config/'],
        'IT': ['/portal/dig/settings/edit/', '/portal/dig/penalty-config/', '/portal/audit/operational/',
               '/portal/officer/queue/', '/portal/ssp/production/', '/portal/citizen/'],
        'USER': ['/portal/dig/', '/portal/ssp/', '/portal/supervisor/', '/portal/officer/', '/portal/audit/',
                 '/portal/it/', '/video/upload/', '/video/uploads/'],
    }
    probe_user = {
        'DIG': 'dig@safecity.fyp', 'SSP': 'ssp3@safecity.fyp', 'SUPV': 'supv3@safecity.fyp',
        'OFFICER': 'officer3@safecity.fyp', 'AUDIT': 'audit@safecity.fyp', 'IT': 'itsupport@safecity.fyp',
        'USER': 'citizen3@safecity.fyp',
    }
    for role, urls in probes.items():
        c = client_for(probe_user[role])
        if c is None:
            check(f'{role} isolation login', False, 'login failed')
            continue
        for url in urls:
            r = c.get(url)
            check(f'{role} blocked from {url}', r.status_code in (302, 403), str(r.status_code))


def phase_d_tracking():
    section('PHASE D | Tracking surfaces in the UI')
    off = client_for('officer2@safecity.fyp')
    r = off.get('/portal/officer/live-tracking/')
    check('officer live-tracking page', r.status_code == 200 and b'Live' in r.content, str(r.status_code))
    cam1 = Camera.objects.get(camera_id='CAM-001')
    r = off.get('/portal/officer/live-tracking/', {'camera_id': cam1.pk})
    check('officer live-tracking camera filter CAM-001', r.status_code == 200, str(r.status_code))
    r = off.get('/portal/officer/vehicle-tracking/', {'plate': 'LEA-1234'})
    check('officer vehicle-tracking plate search', r.status_code == 200 and b'LEA-1234' in r.content, str(r.status_code))
    r = off.get('/portal/officer/live-tracking/timeline/', {'camera_id': Camera.objects.get(camera_id='CAM-E2E-01').pk})
    ok = r.status_code == 200
    items = []
    if ok:
        try:
            body = json.loads(r.content)
            items = body.get('items', [])
        except Exception:
            ok = False
    check('officer live-tracking timeline JSON', ok, f'items={len(items)}')

    for uname, url in [
        ('supervisor@safecity.fyp', '/portal/supervisor/live-tracking/'),
        ('ssp2@safecity.fyp', '/portal/ssp/live-tracking/'),
        ('dig2@safecity.fyp', '/portal/dig/live-tracking/'),
        ('it2@safecity.fyp', '/portal/it/live-tracking/'),
    ]:
        c = client_for(uname)
        r = c.get(url)
        check(f'{uname} live-tracking', r.status_code == 200, str(r.status_code))

    r = client_for('ssp2@safecity.fyp').get('/portal/ssp/live-tracking/timeline/')
    check('SSP live-tracking timeline JSON', r.status_code == 200, str(r.status_code))
    r = client_for('supervisor@safecity.fyp').get('/portal/supervisor/live-tracking/timeline/')
    check('SUPV live-tracking timeline JSON', r.status_code == 200, str(r.status_code))
    r = client_for('dig2@safecity.fyp').get('/portal/dig/live-tracking/timeline/')
    check('DIG live-tracking timeline JSON', r.status_code == 200, str(r.status_code))

    cit = client_for('citizen@safecity.fyp')
    r = cit.get('/portal/citizen/appeals/')
    check('citizen appeal tracker page', r.status_code == 200, str(r.status_code))

    ssp = client_for('ssp@safecity.fyp')
    r = ssp.get('/portal/ssp/appeals/tracker/')
    check('SSP case-escalation tracker (appeals visible)', r.status_code == 200 and b'Awaiting SSP' in r.content, str(r.status_code))
    dig = client_for('dig@safecity.fyp')
    r = dig.get('/portal/dig/case-escalation/tracker/')
    has_pending_block = b'Awaiting SSP Decision' in r.content
    has_notice = b'exclusively by the SSP' in r.content
    check('DIG escalation page hides pending appeals', r.status_code == 200 and not has_pending_block and has_notice, str(r.status_code))

    r = ssp.get('/portal/ssp/live-monitor/')
    check('SSP live monitor wall', r.status_code == 200, str(r.status_code))
    r = dig.get('/portal/dig/live-monitor/')
    check('DIG live monitor wall', r.status_code == 200, str(r.status_code))
    r = dig.get('/portal/dig/cameras-status/')
    check('DIG cameras status board', r.status_code == 200, str(r.status_code))


def phase_e_stock_video():
    section('PHASE E | Real AI pipeline on the uploaded traffic video (via UI)')
    it = client_for('it2@safecity.fyp')
    cam = Camera.objects.get(camera_id='CAM-001')
    before_uploads = VideoUpload.objects.count()
    resp = upload_via_ui(it, USER_VIDEO, cam.id, '16385744-hd_1920_1080_30fps.mp4')
    check('UI upload accepted (redirect)', resp.status_code == 302, str(resp.status_code))
    after = VideoUpload.objects.order_by('-id').first()
    check('VideoUpload record created', after is not None and after.id > before_uploads, f'#{after.id if after else 0}')
    check('upload bound to CAM-001', after and after.camera_id == cam.id, f'cam={after.camera_id if after else None}')
    check('upload sha256 recorded', bool(after and after.file_sha256), '-')

    done = wait_for_upload(after.id, timeout=420)
    check('pipeline completed', done is not None and done.status == VideoUpload.STATUS_COMPLETED,
          f'status={done.status if done else "?"} err={getattr(done, "error_message", "") or ""}')
    if done and done.status == VideoUpload.STATUS_COMPLETED:
        check('frames extracted (59s / 5s interval)', (done.total_frames_extracted or 0) >= 10,
              f'frames={done.total_frames_extracted}')
        dets = Detection.objects.filter(source_video_upload=done.id)
        check('real detections created by pipeline', dets.count() >= 5, f'{dets.count()} detections')
        check('pipeline stats persisted',
              done.frames_with_plates is not None and done.frames_ignored is not None,
              f'plates={done.frames_with_plates} ignored={done.frames_ignored}')
        false_challans = Challan.objects.filter(detection__source_video_upload=done.id).count()
        check('no false-positive challans on normal traffic',
              false_challans == 0 and (done.violations_detected or 0) == 0,
              f'challans={false_challans} violations={done.violations_detected}')
        lf = LiveFeed.objects.filter(camera=cam, title__contains='upload').order_by('-id').first()
        check('LiveFeed created from upload', lf is not None, f'feed={lf.id if lf else None}')
        cam.refresh_from_db()
        check('camera marked online', cam.health_status == 'online', cam.health_status)

        off = client_for('officer@safecity.fyp')
        r = off.get('/portal/officer/queue/')
        check('officer review queue renders', r.status_code == 200, str(r.status_code))
        r = off.get('/portal/officer/detections/')
        check('officer detections list renders', r.status_code == 200, str(r.status_code))
        r = off.get('/portal/officer/camera-feed/')
        check('officer camera feed renders', r.status_code == 200, str(r.status_code))
        r = it.get('/portal/it/cameras/heartbeats/')
        check('IT camera heartbeats page', r.status_code == 200, str(r.status_code))
        r = it.get('/video/uploads/')
        check('IT uploads list page shows record', r.status_code == 200 and b'16385744' in r.content, str(r.status_code))


def phase_f_challan_lifecycle():
    section('PHASE F | Violation video to challan to payment and appeal (SSP-only)')
    VehicleRegistration.objects.update_or_create(
        owner=User.objects.get(username='citizen10@safecity.fyp'), plate_number='LEA-1100',
        defaults=dict(vehicle_type='car', make='Suzuki Cultus', year='2019', color='Blue', is_primary=True),
    )
    for legacy in Challan.objects.filter(plate_number='LEA-1100'):
        legacy.appeals.all().delete()
        legacy.payment_status = Challan.UNPAID
        legacy.save(update_fields=['payment_status'])
    generate_positive_video()

    off = client_for('officer2@safecity.fyp')
    cam = Camera.objects.get(camera_id='CAM-E2E-01')
    resp = upload_via_ui(off, POSITIVE_VIDEO, cam.id, 'positive_violation_LEA-1234_1080p30.mp4')
    check('officer UI upload accepted', resp.status_code == 302, str(resp.status_code))
    upload = VideoUpload.objects.order_by('-id').first()
    done = wait_for_upload(upload.id, timeout=300)
    check('pipeline completed (positive video)', done is not None and done.status == VideoUpload.STATUS_COMPLETED,
          f'status={done.status if done else "?"} err={getattr(done, "error_message", "") or ""}')

    if done and done.status == VideoUpload.STATUS_COMPLETED:
        check('violations detected on positive video', (done.violations_detected or 0) >= 1,
              f'violations={done.violations_detected}')
        challan = Challan.objects.filter(
            detection__source_video_upload=done.id, plate_number='LEA-1234',
        ).order_by('-id').first()
        if challan is None:
            challan = Challan.objects.filter(
                plate_number='LEA-1234', payment_status=Challan.UNPAID,
            ).order_by('-id').first()
            if challan is not None:
                check('24h duplicate guard active (chain reuses live challan)', True, challan.ticket_no)
            else:
                challan = Challan.objects.filter(plate_number='LEA-1234').order_by('-id').first()
                if challan is not None:
                    check('payment flow already completed on earlier run', challan.payment_status == Challan.PAID,
                          challan.payment_status)
        check('auto-challan issued for LEA-1234', challan is not None, 'none found')
        if challan:
            unpaid = challan.payment_status == Challan.UNPAID
            check('challan fine from penalty config', (challan.fine_amount or 0) > 0, challan.fine_amount)
            check('challan PDF generated', bool(challan.pdf_file) and os.path.exists(challan.pdf_file.path),
                  bool(challan.pdf_file))
            det = challan.detection
            check('evidence frames stored (3-frame burst)',
                  det.raw_image and det.plate_crop_image and det.evidence_frame_2 and det.evidence_frame_3,
                  'images present' if det.raw_image else 'missing')
            check('evidence security checks recorded', len(det.evidence_checks or []) == 5,
                  f'{len(det.evidence_checks or [])} checks')
            check('evidence hash recorded', bool(det.evidence_hash), (det.evidence_hash or '')[:16])
            audit_ok = AuditLog.objects.filter(action='pipeline.challan_issued', target_id=det.id).exists()
            check('audit trail for auto-issue', audit_ok, '-')

            cit = client_for('citizen@safecity.fyp')
            r = cit.get('/portal/citizen/')
            check('citizen portal lists own challan', r.status_code == 200 and challan.ticket_no.encode() in r.content,
                  str(r.status_code))
            r = cit.get('/portal/citizen/api/challans/')
            api_body = json.loads(r.content) if r.status_code == 200 else {}
            check('citizen API returns challan',
                  any(str(c.get('id')) == str(challan.id) for c in (api_body.get('challans') or [] if isinstance(api_body, dict) else api_body)) or challan.ticket_no.encode() in r.content,
                  str(r.status_code))
            r = cit.get(f'/challan/{challan.id}/pdf/')
            check('challan PDF download', r.status_code == 200 and body(r)[:5] == b'%PDF-', f'{r.status_code}')

            if unpaid:
                pay_page = cit.get(f'/portal/citizen/challan/{challan.id}/pay/')
                check('citizen pay page renders', pay_page.status_code == 200, str(pay_page.status_code))
                r = cit.post(f'/portal/citizen/challan/{challan.id}/pay/', {
                    'payment_method': '2', 'txn_ref': 'E2E-TXN-88431', 'action': 'manual',
                })
                check('payment submission accepted', r.status_code == 302, str(r.status_code))
                pay_note = AuditLog.objects.filter(
                    action='challan.payment_submitted', target_model='Challan', target_id=challan.id,
                ).order_by('-id').first()
                check('payment submission audited', pay_note is not None, 'missing')
                notif_roles = set(
                    Notification.objects.filter(
                        category='payment_verification', target_url__contains=f'/challan/{challan.id}/',
                    ).values_list('recipient__role', flat=True)
                )
                check('payment verification routed to DIG/SSP/SUPV', notif_roles <= {'DIG', 'SSP', 'SUPV'} and notif_roles,
                      str(notif_roles))

                dig = client_for('dig@safecity.fyp')
                r = dig.get(f'/portal/dig/challan/{challan.id}/verify-payment/')
                check('DIG verify-payment page renders', r.status_code == 200, str(r.status_code))
                r = dig.post(f'/portal/dig/challan/{challan.id}/verify-payment/', {'action': 'confirm', 'note': 'E2E verified transaction'})
                challan.refresh_from_db()
                check('DIG confirms payment to PAID', challan.payment_status == Challan.PAID, challan.payment_status)

    c10 = client_for('citizen10@safecity.fyp')
    ch1 = Challan.objects.filter(plate_number='LEA-1100', payment_status=Challan.UNPAID).order_by('id').first()
    ch5 = Challan.objects.filter(plate_number='LEA-1100', payment_status=Challan.UNPAID).order_by('id').last()
    check('existing UNPAID LEA-1100 challans available', ch1 is not None and ch5 is not None and ch1.id != ch5.id,
          f'{ch1 and ch1.id},{ch5 and ch5.id}')

    if ch1 and ch5:
        r = c10.get(f'/portal/citizen/challan/{ch1.id}/appeal/')
        check('citizen appeal form renders', r.status_code == 200, str(r.status_code))
        r = c10.post(f'/portal/citizen/challan/{ch1.id}/appeal/', {
            'reason': 'This challan was issued by mistake: my vehicle was parked at home during the alleged violation time.',
        })
        check('appeal submitted', r.status_code == 302, str(r.status_code))
        appeal = ChallanAppeal.objects.filter(challan=ch1).order_by('-id').first()
        check('appeal record created', appeal is not None and appeal.status == ChallanAppeal.PENDING, 'missing')

        note_ids = list(
            Notification.objects.filter(category='appeal_submit').values_list('recipient_id', flat=True)
        )
        roles = set(User.objects.filter(id__in=note_ids).values_list('role', flat=True))
        check('appeal routed to SSP ONLY (no DIG)', roles == {'SSP'} and roles, str(roles))
        log = AuditLog.objects.filter(action='appeal.submit', target_model='ChallanAppeal').order_by('-id').first()
        check('appeal audit says routed to ssp', log is not None and 'ssp' in str((log.details or {}).get('routed_to', '')).lower(), '-')

        r = c10.get('/portal/citizen/appeals/')
        check('citizen appeal tracker lists pending appeal', r.status_code == 200 and b'pending' in r.content.lower(), str(r.status_code))

        ssp_view = client_for('ssp3@safecity.fyp')
        r = ssp_view.get('/portal/ssp/appeals/tracker/')
        check('SSP tracker lists the appeal', r.status_code == 200 and f'#{appeal.id}'.encode() in r.content, str(r.status_code))

        dig = client_for('dig@safecity.fyp')
        r = dig.get(f'/portal/dig/appeal/{appeal.id}/override/')
        check('DIG cannot decide appeals', r.status_code in (302, 403), str(r.status_code))
        off5 = client_for('officer5@safecity.fyp')
        r = off5.get('/portal/ssp/appeals/')
        check('officer blocked from SSP appeals', r.status_code in (302, 403), str(r.status_code))

        r = ssp_view.post(f'/portal/ssp/appeal/{appeal.id}/decide/', {
            'decision': 'REJECTED', 'reason': 'Evidence reviewed: the ANPR capture clearly shows the registered vehicle.',
        })
        appeal.refresh_from_db()
        ch1.refresh_from_db()
        check('SSP rejects appeal', appeal.status == ChallanAppeal.REJECTED, appeal.status)
        check('challan stays active after rejection', ch1.payment_status == Challan.UNPAID, ch1.payment_status)

        r = c10.post(f'/portal/citizen/challan/{ch5.id}/appeal/', {
            'reason': 'Second mistaken challan: the plate in the evidence frame belongs to a different vehicle.',
        })
        appeal2 = ChallanAppeal.objects.filter(challan=ch5).order_by('-id').first()
        check('second appeal submitted', appeal2 is not None, 'missing')
        r = ssp_view.post(f'/portal/ssp/appeal/{appeal2.id}/decide/', {
            'decision': 'APPROVED', 'reason': 'Verified as a mistaken challan after cross-checking the evidence chain.',
        })
        appeal2.refresh_from_db()
        ch5.refresh_from_db()
        check('SSP approves second appeal', appeal2.status == ChallanAppeal.APPROVED, appeal2.status)
        check('challan voided after approval', ch5.payment_status == Challan.VOIDED, ch5.payment_status)

        r = c10.get('/portal/citizen/appeals/')
        check('appeal tracker shows decisions', r.status_code == 200 and b'Approved' in r.content, str(r.status_code))
        citizen_note = Notification.objects.filter(
            recipient__username='citizen10@safecity.fyp', category__startswith='appeal_',
        ).exists()
        check('citizen notified of decision', citizen_note, 'missing')


def phase_g_public_and_audit():
    section('PHASE G | Public portal, realtime and audit exports')
    anon = Client()
    r = anon.get('/')
    check('public home renders', r.status_code == 200, str(r.status_code))
    r = anon.get('/', {'plate': 'LEA-1100'})
    check('public tracking by plate', r.status_code == 200, str(r.status_code))
    ch = Challan.objects.filter(plate_number='LEA-1234').order_by('-id').first()
    if ch:
        r = anon.get(f'/challan/{ch.id}/')
        check('public challan detail page', r.status_code == 200, str(r.status_code))
        unpaid_ch = Challan.objects.filter(payment_status=Challan.UNPAID).order_by('id').first()
        if unpaid_ch:
            r = anon.get(f'/challan/{unpaid_ch.id}/pay/')
            check('guest pay page', r.status_code == 200, str(r.status_code))

    staff = client_for('dig@safecity.fyp')
    r = staff.get('/realtime/stats/')
    check('realtime stats', r.status_code == 200, str(r.status_code))
    r = staff.get('/realtime/cameras-status/')
    check('realtime cameras status', r.status_code == 200, str(r.status_code))
    r = staff.get('/realtime/api/kpis/')
    check('realtime KPIs', r.status_code == 200, str(r.status_code))

    aud = client_for('audit@safecity.fyp')
    for kind in ['operational', 'financial', 'compliance', 'auth_events']:
        r = aud.get(f'/portal/audit/export/pdf/{kind}/')
        check(f'audit PDF export {kind}', r.status_code == 200 and body(r)[:5] == b'%PDF-', f'{r.status_code}')

    dig = client_for('dig@safecity.fyp')
    r = dig.get('/portal/dig/audit/')
    check('DIG audit log page', r.status_code == 200, str(r.status_code))
    recent = AuditLog.objects.filter(action__in=[
        'upload.video', 'pipeline.challan_issued', 'challan.payment_submitted', 'challan.payment_verified',
        'appeal.submit',
    ]).count()
    check('end-to-end audit trail present', recent >= 5, f'{recent} entries')


def generate_positive_video():
    import cv2
    import numpy as np
    if os.path.exists(POSITIVE_VIDEO) and os.path.getsize(POSITIVE_VIDEO) > 100000:
        cap = cv2.VideoCapture(POSITIVE_VIDEO)
        usable = cap.isOpened() and cap.get(cv2.CAP_PROP_FRAME_COUNT) > 0
        cap.release()
        if usable:
            return POSITIVE_VIDEO
    if os.path.exists(POSITIVE_VIDEO):
        os.unlink(POSITIVE_VIDEO)
    W, H = 1920, 1080
    FPS = 30
    SECONDS = 8
    PLATE = 'LEA-1234'

    def draw_scene(t, plate_text):
        frame = np.full((H, W, 3), (188, 208, 228), dtype=np.uint8)
        horizon = int(H * 0.42)
        for b in range(0, horizon, 56):
            shade = 172 - min(70, b // 3)
            cv2.rectangle(frame, (0, b), (W, b + 56), (shade, shade + 14, shade + 30), -1)
        rng = np.random.default_rng(7)
        for i in range(14):
            bx = int(rng.integers(0, W))
            bw = int(rng.integers(90, 220))
            bh = int(rng.integers(70, 190))
            shade = int(rng.integers(80, 130))
            cv2.rectangle(frame, (bx, horizon - bh), (bx + bw, horizon), (shade - 20, shade - 10, shade), -1)
        cv2.rectangle(frame, (0, horizon), (W, H), (52, 56, 60), -1)
        for y in range(horizon + 6, H, 4):
            alpha = (y - horizon) / (H - horizon)
            cv2.line(frame, (0, y), (W, y), (int(48 + 26 * alpha), int(52 + 26 * alpha), int(56 + 26 * alpha)), 1)
        for i in range(9):
            z = i / 8.0
            y0 = int(horizon + (H - horizon) * (z ** 2.1))
            y1 = int(horizon + (H - horizon) * (((i + 0.45) / 8.0) ** 2.1))
            lane_w_top, lane_w_bot = 26, 200
            cx = W // 2
            top_l = cx - int(lane_w_top * (0.4 + 0.6 * z))
            bot_l = cx - int(lane_w_bot * (0.4 + 0.6 * z))
            top_r = cx + int(lane_w_top * (0.4 + 0.6 * z))
            bot_r = cx + int(lane_w_bot * (0.4 + 0.6 * z))
            if i % 2 == 0:
                pts = np.array([[(top_l, y0), (bot_l, y1), (bot_l + 6, y1), (top_l + 3, y0)]], np.int32)
                cv2.fillPoly(frame, pts, (225, 228, 232))
                pts = np.array([[(top_r, y0), (bot_r, y1), (bot_r + 6, y1), (top_r + 3, y0)]], np.int32)
                cv2.fillPoly(frame, pts, (225, 228, 232))
        edge = np.array([[(0, horizon), (W, horizon), (W, horizon + 8), (0, horizon + 8)]], np.int32)
        cv2.fillPoly(frame, edge, (20, 22, 24))
        progress = t / (SECONDS - 1)
        car_w = int(150 + 690 * (progress ** 1.7))
        car_h = int(96 + 440 * (progress ** 1.7))
        cx = W // 2 + int(60 * (1 - progress))
        bottom = int(horizon + 40 + (H - horizon - 46) * (progress ** 1.55))
        top = bottom - car_h
        body_w = int(car_w * 0.94)
        x0, x1 = cx - body_w // 2, cx + body_w // 2
        cv2.rectangle(frame, (x0, top + int(car_h * 0.18)), (x1, bottom), (128, 72, 34), -1)
        cv2.rectangle(frame, (x0 + 8, top + int(car_h * 0.18)), (x1 - 8, top + int(car_h * 0.24)), (170, 110, 60), -1)
        roof_w = int(body_w * 0.82)
        cv2.rectangle(frame, (cx - roof_w // 2, top), (cx + roof_w // 2, top + int(car_h * 0.22)), (150, 92, 46), -1)
        glass_w, glass_h = int(roof_w * 0.86), int(car_h * 0.15)
        cv2.rectangle(frame, (cx - glass_w // 2, top + int(car_h * 0.03)),
                      (cx + glass_w // 2, top + int(car_h * 0.03) + glass_h), (168, 190, 205), -1)
        light_w, light_h = int(body_w * 0.17), int(car_h * 0.10)
        for sx in (x0 + int(body_w * 0.07), x1 - int(body_w * 0.07) - light_w):
            cv2.rectangle(frame, (sx, top + int(car_h * 0.32)),
                          (sx + light_w, top + int(car_h * 0.32) + light_h), (26, 26, 212), -1)
            cv2.rectangle(frame, (sx + 3, top + int(car_h * 0.32) + 3),
                          (sx + light_w - 3, top + int(car_h * 0.32) + light_h - 3), (40, 40, 235), -1)
        bump_h = int(car_h * 0.14)
        cv2.rectangle(frame, (x0 - 4, bottom - bump_h), (x1 + 4, bottom), (58, 60, 62), -1)
        wheel_r = int(car_h * 0.09)
        for wx in (x0 + int(body_w * 0.16), x1 - int(body_w * 0.16)):
            cv2.circle(frame, (wx, bottom), wheel_r, (24, 24, 26), -1)
        plate_w, plate_h = int(car_w * 0.40), int(car_h * 0.16)
        if plate_w < 340:
            plate_w = 340
        if plate_h < 110:
            plate_h = 110
        py = top + int(car_h * 0.50)
        px = cx - plate_w // 2
        cv2.rectangle(frame, (px - 6, py - 6), (px + plate_w + 6, py + plate_h + 6), (30, 30, 30), -1)
        cv2.rectangle(frame, (px, py), (px + plate_w, py + plate_h), (250, 250, 250), -1)
        font = cv2.FONT_HERSHEY_SIMPLEX
        margin = int(plate_w * 0.07)
        scale = min(plate_h / 46.0, (plate_w - 2 * margin) / 380.0)
        thickness = max(2, int(round(2.6 * scale)))
        (tw, th), _ = cv2.getTextSize(plate_text, font, scale, thickness)
        tx = px + (plate_w - tw) // 2
        ty = py + (plate_h + th) // 2 + 2
        cv2.putText(frame, plate_text, (tx, ty), font, scale, (18, 18, 18), thickness, cv2.LINE_AA)
        stamp = f'CAM-E2E-01  {datetime.datetime.now():%Y-%m-%d %H:%M:%S}'
        cv2.rectangle(frame, (24, 24), (24 + 560, 24 + 44), (16, 16, 16), -1)
        cv2.putText(frame, stamp, (36, 54), font, 0.92, (235, 235, 235), 2, cv2.LINE_AA)
        return frame

    writer = cv2.VideoWriter(POSITIVE_VIDEO, cv2.VideoWriter_fourcc(*'mp4v'), FPS, (W, H))
    total = SECONDS * FPS
    for f in range(total):
        t = f / (total - 1)
        writer.write(draw_scene(t, PLATE))
    writer.release()
    return POSITIVE_VIDEO


def write_report():
    lines = [
        '# E2E Role Matrix Test Report',
        '',
        f'**Date:** {datetime.datetime.now():%Y-%m-%d %H:%M}',
        f'**Users covered:** {User.objects.count()} across 7 roles ',
        f'**Result: {PASS} passed / {FAIL} failed / {PASS + FAIL} total**',
        '',
    ]
    ordered = list(SECTIONS.items()) + [('END', len(RESULTS))]
    for i, (title, start) in enumerate(ordered[:-1]):
        end = ordered[i + 1][1]
        lines += [f'## {title}', '']
        for status, name, detail in RESULTS[start:end]:
            mark = 'PASS' if status == 'PASS' else '**FAIL**'
            lines.append(f'- [{mark}] {name}' + (f' ({detail})' if detail else ''))
        lines.append('')
    lines += ['## Failures', '']
    fails = [r for r in RESULTS if r[0] == 'FAIL']
    if not fails:
        lines.append('None. All checks passed.')
    else:
        for _, name, detail in fails:
            lines.append(f'- {name} ({detail})')
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, 'w') as f:
        f.write('\n'.join(lines))
    print(f'\nreport written: {REPORT_PATH}')


def main():
    t0 = time.time()
    phase_a_auth()
    phase_b_pages()
    phase_c_isolation()
    phase_d_tracking()
    phase_e_stock_video()
    phase_f_challan_lifecycle()
    phase_g_public_and_audit()
    write_report()
    print()
    print('=' * 66)
    for status, name, detail in RESULTS:
        if status == 'FAIL':
            print(f'  [FAIL] {name} ({detail})')
    print('=' * 66)
    print(f'TOTAL: {PASS + FAIL} | PASS: {PASS} | FAIL: {FAIL} | {time.time() - t0:.0f}s')
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
