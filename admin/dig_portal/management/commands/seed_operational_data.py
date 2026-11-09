"""Seed a realistic, professionally-presented operating dataset for the
Safe City e-Challan platform.

Creates: staff organisation (DIG/SSP/Supervisors/Officers/Audit/IT),
registered citizens, the Lahore camera network, live feeds, vehicle
registrations and a 60-day operational history (challans, payments,
appeals, shifts, alerts, banners, notifications, audit logs, login
events). All labels, locations, names and references are realistic;
AI detections are NOT seeded here - they are produced by real pipeline
runs (video upload / camera ingest).
"""
import datetime as dt
import random
from dateutil.relativedelta import relativedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import VehicleRegistration
from admin.dig_portal.models import (Alert, AuditLog, Banner, LoginEvent,
                                     Notification, Shift, SystemSettings)
from appeals.models import ChallanAppeal
from cameras.models import Camera
from challans.models import Challan
from payments.models import PaymentTransaction
from realtime.models import CameraAssignment, LiveFeed

User = get_user_model()

STAFF_PASSWORD = 'SafeCity@2026'

STAFF = [
    # role, username(email), first, last, designation, department, region, staff_id
    ('DIG', 'dig@safecity.fyp', 'Tahir', 'Nawaz', 'Deputy Inspector General', 'Traffic Police HQ', 'Lahore', 'DIG-TRF-001'),
    ('SSP', 'ssp.traffic@safecity.fyp', 'Sana', 'Raza', 'Senior Superintendent', 'Traffic Police HQ', 'Lahore', 'SSP-TRF-014'),
    ('SSP', 'ssp.ops@safecity.fyp', 'Imran', 'Haider', 'Senior Superintendent (Operations)', 'Traffic Police HQ', 'Lahore', 'SSP-TRF-021'),
    ('SUPV', 'supervisor.gulberg@safecity.fyp', 'Bilal', 'Ahmed', 'Supervisor - Gulberg Zone', 'Enforcement Division', 'Gulberg', 'SUP-ENF-102'),
    ('SUPV', 'supervisor.modeltown@safecity.fyp', 'Nadia', 'Hussain', 'Supervisor - Model Town Zone', 'Enforcement Division', 'Model Town', 'SUP-ENF-107'),
    ('SUPV', 'supervisor.cantt@safecity.fyp', 'Faisal', 'Mehmood', 'Supervisor - Cantt Zone', 'Enforcement Division', 'Cantt', 'SUP-ENF-113'),
    ('OFFICER', 'officer.khan@safecity.fyp', 'Adnan', 'Khan', 'Enforcement Officer', 'Gulberg Zone', 'Gulberg', 'OFF-GLB-231'),
    ('OFFICER', 'officer.malik@safecity.fyp', 'Rashid', 'Malik', 'Enforcement Officer', 'Gulberg Zone', 'Gulberg', 'OFF-GLB-235'),
    ('OFFICER', 'officer.butt@safecity.fyp', 'Ayesha', 'Butt', 'Enforcement Officer', 'Model Town Zone', 'Model Town', 'OFF-MDT-242'),
    ('OFFICER', 'officer.javed@safecity.fyp', 'Omar', 'Javed', 'Enforcement Officer', 'Model Town Zone', 'Model Town', 'OFF-MDT-247'),
    ('OFFICER', 'officer.chaudhry@safecity.fyp', 'Hamza', 'Chaudhry', 'Enforcement Officer', 'Cantt Zone', 'Cantt', 'OFF-CNT-253'),
    ('OFFICER', 'officer.sheikh@safecity.fyp', 'Zain', 'Sheikh', 'Enforcement Officer', 'Cantt Zone', 'Cantt', 'OFF-CNT-258'),
    ('AUDIT', 'audit.nawaz@safecity.fyp', 'Farah', 'Nawaz', 'Audit Officer', 'Internal Audit', 'Lahore', 'AUD-INT-301'),
    ('AUDIT', 'audit.tariq@safecity.fyp', 'Shahid', 'Tariq', 'Audit Officer', 'Internal Audit', 'Lahore', 'AUD-INT-305'),
    ('IT', 'itsupport@safecity.fyp', 'Hamza', 'Sheikh', 'IT Support Engineer', 'IT Services', 'Lahore', 'IT-SVC-401'),
    ('IT', 'it.network@safecity.fyp', 'Maha', 'Iqbal', 'Network Administrator', 'IT Services', 'Lahore', 'IT-SVC-406'),
]

CITIZENS = [
    # username(email), first, last, phone, cnic
    ('ahmad.raza@safecity.fyp', 'Ahmad', 'Raza', '0300-8452197', '35202-7481936-4'),
    ('sara.khan@safecity.fyp', 'Sara Fatima', 'Khan', '0333-5219874', '35202-9912045-6'),
    ('usman.ghani@safecity.fyp', 'Usman', 'Ghani', '0301-8874521', '35201-7842109-2'),
    ('ayesha.siddiqui@safecity.fyp', 'Ayesha', 'Siddiqui', '0345-9987412', '35202-1122334-0'),
    ('zafar.chaudhry@safecity.fyp', 'Zafar Iqbal', 'Chaudhry', '0322-6985214', '34101-8877445-1'),
]

CAMERAS = [
    # camera_id, location, lat, lng, legal_dir, violation_side
    ('CAM-001', 'Main Boulevard Gulberg, near Liberty Roundabout', 31.5155, 74.3436, 'N', 'back'),
    ('CAM-002', 'Canal Road Bridge, Thokar Niaz Baig', 31.4697, 74.2847, 'E', 'front'),
    ('CAM-003', 'Jail Road Intersection, Shimla Pahari', 31.5494, 74.3264, 'S', 'back'),
    ('CAM-004', 'Ferozepur Road Signal, Kalma Chowk', 31.5089, 74.3357, 'W', 'front'),
    ('CAM-005', 'Liberty Market Roundabout, Gulberg III', 31.5180, 74.3410, 'N', 'back'),
    ('CAM-006', 'Model Town Link Road, Ferozepur Side', 31.4800, 74.3260, 'S', 'back'),
    ('CAM-007', 'Shahrah-e-Fatima Jinnah, Qartaba Chowk', 31.5530, 74.3180, 'E', 'front'),
    ('CAM-008', 'Railway Station Approach, Circular Road', 31.5770, 74.3130, 'W', 'front'),
    ('CAM-009', 'Barkat Market Signal, Garden Town', 31.5010, 74.3300, 'N', 'back'),
    ('CAM-010', 'DHA Phase 5 Boulevard, Ghazi Road', 31.4590, 74.3760, 'S', 'back'),
]

# Plates seen committing violations in Lahore (all resolvable via the
# offline Excise registry or realistic owner records)
VIOLATION_RECORDS = [
    # plate, owner, cnic, address, phone, vehicle, year, color
    ('LEA-1234', 'Ahmad Raza', '35202-7481936-4', 'House 23, Street 4, DHA Phase 5, Lahore', '0300-8452197', 'Toyota Corolla GLi', '2022', 'White'),
    ('ABC-999', 'Sara Fatima Khan', '35202-9912045-6', 'House 112, Block C, Model Town, Lahore', '0333-5219874', 'Toyota Corolla Altis', '2019', 'Black'),
    ('LEB-456', 'Usman Ghani', '35201-7842109-2', 'Flat 4B, Askari 11, Lahore Cantt', '0301-8874521', 'Suzuki Cultus VXL', '2021', 'Silver'),
    ('LZA-789', 'Ayesha Siddiqui', '35202-1122334-0', 'House 7, Street 21, Bahria Town, Lahore', '0345-9987412', 'Toyota Yaris ATIV', '2023', 'Pearl White'),
    ('LEO-826', 'Kiran Shahzadi', '35202-4455667-7', 'House 89, Sector C, Bahria Orchard, Lahore', '0312-7412589', 'Suzuki Swift GL', '2020', 'Red'),
    ('LWX-552', 'Zafar Iqbal Chaudhry', '34101-8877445-1', 'House 156, Block R-3, Johar Town, Lahore', '0322-6985214', 'Mercedes-Benz C180', '2017', 'Gunmetal'),
    ('LEA-1001', 'Muhammad Bilal Khokhar', '35201-3347821-9', '34-B Gulberg III, Lahore Cantt', '0321-4478021', 'Honda Civic Oriel', '2020', 'Graphite Grey'),
    ('ACR-597', 'Tahir Mehmood Bhatti', '37405-1122334-3', 'Chak 45 GB, Jaranwala Road, Faisalabad', '0300-4127856', 'Honda City Aspire', '2018', 'Blue'),
    ('LES-305', 'Hina Aslam Malhi', '33100-5544332-8', 'House 45, Model Colony, Sargodha', '0334-8521479', 'Suzuki Alto VXL', '2019', 'White Pearl'),
    ('LHR-007', 'Sheikh Hamza Farooq', '35228-9911223-5', 'Suite 12, 2nd Floor, Hafeez Center, Gulberg III', '0300-1122334', 'Honda City 1.5 AS', '2022', 'Athletic Blue'),
    ('LEB-221', 'Rana Waqas Anwar', '35202-6677889-3', 'House 56, Block D, Gulshan-e-Ravi, Lahore', '0304-7788123', 'Suzuki Mehran VX', '2016', 'White'),
    ('LZA-043', 'Mehwish Aslam Bajwa', '35204-2233445-0', 'House 9, Street 12, Tech Society, Garden Town', '0335-6421987', 'Toyota Vitz F', '2015', 'Silver'),
    ('LWX-908', 'Naveed Akhtar Sial', '34601-3344556-7', 'House 210, Civil Lines, Sialkot', '0301-4567892', 'Kia Sportage Alpha', '2021', 'White Pearl'),
    ('LEO-517', 'Amna Bibi Tarar', '35206-7788990-2', 'Chak 220 RB, Kharianwala, Sheikhupura Road', '0347-8523691', 'Suzuki Bolan VX', '2014', 'Sky Blue'),
    ('ACR-881', 'Ghulam Mustafa Sandhu', '37406-4455667-9', 'House 34, People Colony No.1, Faisalabad', '0300-9874561', 'Toyota Hilux Revo', '2020', 'Grey'),
]

APPEAL_REASONS = [
    ('My vehicle was not at this location on the mentioned date; I was at a family wedding in Kasur and have witnesses.', 'pending'),
    ('The camera image shows a different coloured car - my car is white, the vehicle in evidence appears grey.', 'pending'),
    ('I admit the mistake and request a fine reduction; I am a daily-wage worker and cannot afford the full amount.', 'pending'),
    ('There was a medical emergency - my son had an asthma attack and we were rushing to Ittefaq Hospital.', 'pending'),
    ('The number plate in the evidence photo is not clearly readable; requesting re-verification.', 'approved'),
    ('This is the second challan for the same violation within 10 minutes at the same location - requesting waiver of the duplicate.', 'approved'),
    ('I had taken a wrong turn due to a road closure for the marathon; there was no clear diversion signboard.', 'rejected'),
    ('I was dropping a patient at Services Hospital emergency and had to take the service road against the flow.', 'escalated'),
]

AUDIT_ACTIONS = [
    ('LOGIN', 'session', 'Signed in to staff portal'),
    ('CHALLAN_VIEW', 'challan', 'Reviewed challan record'),
    ('CHALLAN_FINE', 'challan', 'Updated fine amount'),
    ('APPEAL_DECISION', 'appeal', 'Recorded appeal decision'),
    ('CAMERA_STATUS', 'camera', 'Changed camera status'),
    ('BLACKLIST_ADD', 'blacklist', 'Added plate to blacklist'),
    ('SETTINGS_UPDATE', 'settings', 'Updated system settings'),
    ('REPORT_EXPORT', 'report', 'Exported operational report'),
    ('PAYMENT_VERIFY', 'payment', 'Verified challan payment'),
]

USER_AGENTS = [
    ('Chrome 129 on Windows 11', 'Chrome 129', 'Windows 11', 'desktop', '', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'),
    ('Edge 128 on Windows 11', 'Edge 128', 'Windows 11', 'desktop', '', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0'),
    ('Safari 17 on macOS', 'Safari 17', 'macOS 14', 'desktop', 'Apple', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'),
    ('Chrome 128 on Android', 'Chrome Mobile 128', 'Android 14', 'mobile', 'Samsung', 'Mozilla/5.0 (Linux; Android 14; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36'),
]

OFFICE_IPS = ['119.155.{}.{}'.format(40 + i, 20 + i * 7) for i in range(4)] + ['203.99.{}.10'.format(50 + i) for i in range(3)]


class Command(BaseCommand):
    help = ('Seed the realistic staff organisation, camera network and 60-day '
            'operational history. Safe to re-run (update_or_create).')

    def add_arguments(self, parser):
        parser.add_argument('--purge', action='store_true',
                            help='Delete existing operational data before seeding')

    def handle(self, *args, **opts):
        self.rng = random.Random(20261107)
        now = timezone.now()

        if opts.get('purge'):
            self._purge()

        with transaction.atomic():
            staff = self._seed_staff()
            citizens = self._seed_citizens()
            cameras = self._seed_cameras()
            self._seed_assignments(staff, cameras)
            self._seed_registrations(citizens)
            challans = self._seed_challans(staff, cameras, now, self.rng)
            self._seed_payments(challans, self.rng)
            self._seed_appeals(challans, citizens, staff, self.rng)
            self._seed_shifts(staff, now)
            self._seed_alerts(staff)
            self._seed_banners(staff)
            self._seed_notifications(staff, citizens, challans)
            self._seed_audit_log(staff, challans, now, self.rng)
            self._seed_login_events(staff, citizens, now, self.rng)
            self._ensure_settings()

        self.stdout.write(self.style.SUCCESS('Operational dataset ready.'))

    # ------------------------------------------------------------------
    def _purge(self):
        from video_processor.models import VideoUpload
        counts = {}
        for qs in (PaymentTransaction.objects.all(), ChallanAppeal.objects.all(),
                   Challan.objects.all(), Notification.objects.all(),
                   AuditLog.objects.all(), LoginEvent.objects.all(),
                   Shift.objects.all(), Alert.objects.all(), Banner.objects.all(),
                   CameraAssignment.objects.all(), LiveFeed.objects.all(),
                   VideoUpload.objects.all()):
            name = qs.model.__name__
            counts[name] = qs.count()
            qs.delete()
        from detections.models import Detection
        counts['Detection'] = Detection.objects.count()
        Detection.objects.all().delete()
        Camera.objects.all().delete()
        keep = {row[1] for row in STAFF} | {row[0] for row in CITIZENS}
        stale = User.objects.exclude(username__in=keep)
        counts['StaleUser'] = stale.count()
        stale.delete()
        for k, v in counts.items():
            self.stdout.write(f'  purged {k}: {v}')

    # ------------------------------------------------------------------
    def _seed_staff(self):
        staff = {}
        for role, email, first, last, designation, department, region, staff_id in STAFF:
            user, created = User.objects.update_or_create(
                username=email,
                defaults=dict(
                    email=email, first_name=first, last_name=last, role=role,
                    designation=designation, department=department, region=region,
                    staff_id=staff_id, is_staff=True, is_active=True,
                    phone='04{}-{}{}'.format(self.rng.randint(2, 9), self.rng.randint(200, 999), self.rng.randint(1000, 9999)),
                ),
            )
            user.set_password(STAFF_PASSWORD)
            user.save(update_fields=['password'])
            staff.setdefault(role, []).append(user)
            self.stdout.write(f"  {'created' if created else 'updated'} {role}: {user.username}")
        dig = staff['DIG'][0]
        dig.is_superuser = True
        dig.save(update_fields=['is_superuser'])
        return staff

    def _seed_citizens(self):
        citizens = []
        for email, first, last, phone, cnic in CITIZENS:
            user, created = User.objects.update_or_create(
                username=email,
                defaults=dict(email=email, first_name=first, last_name=last,
                              role='USER', phone=phone, cnic=cnic, is_active=True),
            )
            if created:
                user.set_password(STAFF_PASSWORD)
                user.save(update_fields=['password'])
            citizens.append(user)
        self.stdout.write(f'  citizens: {len(citizens)}')
        return citizens

    def _seed_cameras(self):
        cameras = []
        for cam_id, location, lat, lng, legal, side in CAMERAS:
            cam, _ = Camera.objects.update_or_create(
                camera_id=cam_id,
                defaults=dict(location=location, latitude=lat, longitude=lng,
                              legal_direction=legal, violation_side=side,
                              is_active=True, health_status='online',
                              capture_interval=5, auto_confirm_threshold=0.70),
            )
            cameras.append(cam)
        self.stdout.write(f'  cameras: {len(cameras)} (Lahore network)')
        return cameras

    def _seed_assignments(self, staff, cameras):
        officers = staff.get('OFFICER', [])
        zones = [cameras[:4], cameras[4:7], cameras[7:]]
        made = 0
        for officer, zone in zip(officers, zones + zones + zones):
            for cam in zone:
                CameraAssignment.objects.update_or_create(
                    officer=officer, camera=cam, defaults={'is_active': True})
                made += 1
        self.stdout.write(f'  camera assignments: {made}')

    def _seed_registrations(self, citizens):
        regs = [
            (citizens[0], 'LEA-1234', 'Toyota Corolla GLi', '2022', 'White'),
            (citizens[1], 'ABC-999', 'Toyota Corolla Altis', '2019', 'Black'),
            (citizens[2], 'LEB-456', 'Suzuki Cultus VXL', '2021', 'Silver'),
            (citizens[3], 'LZA-789', 'Toyota Yaris ATIV', '2023', 'Pearl White'),
            (citizens[4], 'LWX-552', 'Mercedes-Benz C180', '2017', 'Gunmetal'),
        ]
        for owner, plate, make, year, color in regs:
            VehicleRegistration.objects.update_or_create(
                owner=owner, plate_number=plate,
                defaults=dict(vehicle_type='car', make=make, year=year,
                              color=color, is_primary=True),
            )
        self.stdout.write(f'  vehicle registrations: {len(regs)}')

    def _seed_challans(self, staff, cameras, now, rng):
        officers = staff.get('OFFICER', [])
        challans = []
        history_days = 60
        per_day = 1  # ~60 challans across the window
        day_cursor = now - dt.timedelta(days=history_days)
        seq = 0
        while day_cursor < now - dt.timedelta(days=1):
            for _ in range(rng.randint(0, 2 * per_day)):
                plate, owner, cnic, address, phone, make, year, color = \
                    VIOLATION_RECORDS[seq % len(VIOLATION_RECORDS)]
                cam = rng.choice(cameras)
                officer = rng.choice(officers)
                seq += 1
                stamp = day_cursor.replace(
                    hour=rng.randint(7, 21), minute=rng.randint(0, 59),
                    second=rng.randint(0, 59), microsecond=0)
                age = (now - stamp).days
                ticket = Challan.objects.generate_ticket_no()
                # ~55% paid within the window, none paid in the last 2 days
                paid = rng.random() < 0.55 and age >= 2
                ch = Challan.objects.create(
                    ticket_no=ticket,
                    plate_number=plate,
                    owner_name=owner, cnic=cnic, address=address, phone=phone,
                    vehicle_type='car', make_year=year, color=color,
                    violation_type=Challan.WRONG_WAY,
                    fine_amount=500,
                    location=cam.location,
                    ai_confidence=round(rng.uniform(0.90, 0.985), 3),
                    moving_direction=rng.choice(['N', 'S', 'E', 'W']),
                    legal_direction=cam.legal_direction,
                    issue_date=stamp.date(),
                    due_date=stamp.date() + dt.timedelta(days=30),
                    payment_status=Challan.PAID if paid else Challan.UNPAID,
                    paid_at=stamp + dt.timedelta(days=rng.randint(0, 6),
                                                 hours=rng.randint(0, 20)) if paid else None,
                    created_by=officer,
                    camera=cam,
                )
                # creation timestamp in the past
                Challan.objects.filter(pk=ch.pk).update(created_at=stamp, updated_at=stamp)
                ch.refresh_from_db()
                challans.append(ch)
            day_cursor += dt.timedelta(days=1)
        self.stdout.write(f'  challans: {len(challans)} across {history_days} days')
        return challans

    def _seed_payments(self, challans, rng):
        made = 0
        for ch in challans:
            if ch.payment_status != Challan.PAID or not ch.paid_at:
                continue
            provider = rng.choice(['JazzCash', 'EasyPaisa'])
            ref = '{}-{}{}'.format('JC' if provider == 'JazzCash' else 'EP',
                                   ch.paid_at.strftime('%Y%m%d'),
                                   rng.randint(100000, 999999))
            txn = PaymentTransaction.objects.update_or_create(
                txn_ref=ref,
                defaults=dict(ticket_no=ch.ticket_no, challan=ch,
                              provider=provider, amount=ch.fine_amount,
                              status=PaymentTransaction.STATUS_SUCCESS,
                              gateway_ref='GW-{}'.format(rng.randint(10 ** 9, 10 ** 10 - 1))),
            )[0]
            PaymentTransaction.objects.filter(pk=txn.pk).update(created_at=ch.paid_at)
            made += 1
        self.stdout.write(f'  payment transactions: {made}')

    def _seed_appeals(self, challans, citizens, staff, rng):
        targets = [c for c in challans if c.payment_status == Challan.UNPAID][:8]
        ssp = staff.get('SSP', [None])[0]
        made = 0
        for ch, (reason, status) in zip(targets, APPEAL_REASONS):
            citizen = next((u for u in citizens if u.cnic == ch.cnic), None)
            submitted = ch.created_at + dt.timedelta(days=rng.randint(1, 5))
            appeal = ChallanAppeal.objects.create(
                challan=ch,
                submitted_by=citizen,
                guest_cnic='' if citizen else ch.cnic,
                guest_name='' if citizen else (ch.owner_name or ''),
                reason=reason,
                status=status,
            )
            ChallanAppeal.objects.filter(pk=appeal.pk).update(created_at=submitted)
            if status == 'approved':
                ch.payment_status = Challan.VOIDED
                ch.save(update_fields=['payment_status'])
            made += 1
        self.stdout.write(f'  appeals: {made}')

    def _seed_shifts(self, staff, now):
        officers = staff.get('OFFICER', [])
        supervisors = staff.get('SUPV', [])
        made = 0
        for week_offset in (0, 7, 14):
            base = (now - dt.timedelta(days=week_offset)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            for day in range(7):
                day_start = base + dt.timedelta(days=day)
                if day_start > now:
                    break
                for shift_hours, start_hour in (((8, 14), 0), ((14, 22), 1), ((22, 6), 2)):
                    officer = officers[(day + start_hour) % len(officers)]
                    start = day_start + dt.timedelta(hours=shift_hours[0])
                    end = day_start + dt.timedelta(hours=shift_hours[1] + (24 if shift_hours[1] < shift_hours[0] else 0))
                    if end > now:
                        end = now
                    if start >= end:
                        continue
                    Shift.objects.update_or_create(
                        officer=officer, start_time=start,
                        defaults=dict(end_time=end,
                                      assigned_by=supervisors[day % len(supervisors)]))
                    made += 1
        self.stdout.write(f'  shift roster entries: {made}')

    def _seed_alerts(self, staff):
        dig = staff['DIG'][0]
        it = staff['IT'][0]
        alerts = [
            ('CAM-002 connectivity degraded', 'Canal Road Bridge camera is dropping frames. Packet loss at 12% on the last health check.', 'warning', 'staff', it),
            ('Kalma Chowk violation spike', 'Wrong-way detections at Ferozepur Road signal are 3.2x the weekly average. Field team review recommended.', 'danger', 'staff', dig),
            ('Night maintenance window', 'Scheduled database maintenance on Sunday 02:00-04:00. Portal may be briefly unavailable.', 'info', 'all', it),
            ('Monsoon advisory for field units', 'Heavy rain forecast for Lahore this week. Officers are advised to exercise caution during signal duty.', 'info', 'staff', dig),
            ('Qartaba Chowk camera back online', 'CAM-007 connectivity restored after UPS battery replacement.', 'success', 'staff', it),
        ]
        for title, message, severity, audience, author in alerts:
            Alert.objects.update_or_create(
                title=title,
                defaults=dict(message=message, severity=severity, audience=audience,
                              is_active=True, created_by=author))
        self.stdout.write(f'  alerts: {len(alerts)}')

    def _seed_banners(self, staff):
        dig = staff['DIG'][0]
        banners = [
            ('Road Safety Week 2026',
             '<strong>Obey traffic signals</strong> - one wrong turn can change everything. Punjab Traffic Police.'),
            ('Helpline 15',
             'Report traffic violations and road hazards on the Punjab Police helpline <strong>15</strong>.'),
            ('E-Challan payment reminder',
             'Unpaid e-challans can be settled online via JazzCash or EasyPaisa within 30 days of issue.'),
        ]
        for title, message in banners:
            Banner.objects.update_or_create(
                title=title,
                defaults=dict(banner_type=Banner.BANNER_TYPE_HTML, html_content=message,
                              placement=Banner.PLACEMENT_TICKER, is_active=True, created_by=dig))
        self.stdout.write(f'  banners: {len(banners)}')

    def _seed_notifications(self, staff, citizens, challans):
        made = 0
        supervisors = staff.get('SSP', [])[:1] + staff.get('SUPV', [])[:1]
        for ch in challans[-6:]:
            for u in supervisors:
                notif = Notification.objects.create(
                    recipient=u, title='New challan issued',
                    message='Challan {} for {} ({} PKR) at {}.'.format(
                        ch.ticket_no, ch.plate_number, ch.fine_amount, ch.location),
                    category='challan',
                    target_url='/portal/dig/challans/')
                Notification.objects.filter(pk=notif.pk).update(created_at=ch.created_at)
                made += 1
            owner = next((u for u in citizens if u.cnic == ch.cnic), None)
            if owner:
                notif = Notification.objects.create(
                    recipient=owner, title='E-challan issued against your vehicle',
                    message='Challan {} of {} PKR was issued for {} at {}. Pay before the due date to avoid escalation.'.format(
                        ch.ticket_no, ch.fine_amount, ch.plate_number, ch.location),
                    category='challan',
                    target_url='/portal/citizen/')
                Notification.objects.filter(pk=notif.pk).update(created_at=ch.created_at)
                made += 1
        it = staff['IT'][0]
        Notification.objects.create(
            recipient=it, title='Camera health warning',
            message='CAM-002 (Canal Road Bridge) reported degraded connectivity.',
            category='camera', target_url='/portal/it/cameras/')
        made += 1
        self.stdout.write(f'  notifications: {made}')

    def _seed_audit_log(self, staff, challans, now, rng):
        actors = (staff.get('DIG', []) + staff.get('SSP', []) +
                  staff.get('AUDIT', []) + staff.get('IT', []))
        made = 0
        for i in range(40):
            actor = rng.choice(actors)
            action, target_model, detail = AUDIT_ACTIONS[i % len(AUDIT_ACTIONS)]
            ch = rng.choice(challans) if challans else None
            stamp = now - dt.timedelta(days=rng.randint(0, 30),
                                       hours=rng.randint(0, 23),
                                       minutes=rng.randint(0, 59))
            audit = AuditLog.objects.create(
                actor=actor, action=action, target_model=target_model,
                target_id=(ch.id if ch and target_model == 'challan' else None),
                details={'summary': detail},
                ip_address=rng.choice(OFFICE_IPS),
            )
            AuditLog.objects.filter(pk=audit.pk).update(timestamp=stamp)
            made += 1
        self.stdout.write(f'  audit log entries: {made}')

    def _seed_login_events(self, staff, citizens, now, rng):
        everyone = [u for users in staff.values() for u in users] + citizens
        made = 0
        for i in range(60):
            user = rng.choice(everyone)
            ua_label, browser, os_name, dtype, brand, ua = USER_AGENTS[i % len(USER_AGENTS)]
            success = rng.random() > 0.08
            stamp = now - dt.timedelta(days=rng.randint(0, 21),
                                       hours=rng.randint(0, 23),
                                       minutes=rng.randint(0, 59))
            evt = LoginEvent.objects.create(
                user=user if success else None,
                username_attempted=user.username,
                portal='citizen' if user.role == 'USER' else 'admin',
                success=success,
                failure_reason='' if success else 'Invalid password',
                ip_address=rng.choice(OFFICE_IPS),
                user_agent=ua, browser=browser, os=os_name,
                device_type=dtype, device_brand=brand, device_summary=ua_label,
            )
            LoginEvent.objects.filter(pk=evt.pk).update(timestamp=stamp)
            made += 1
        self.stdout.write(f'  login events: {made}')

    def _ensure_settings(self):
        settings = SystemSettings.get()
        settings.due_date_days = 30
        settings.default_fines = {'wrong_way': 500, 'no_helmet': 300,
                                  'signal_break': 500, 'over_speed': 800}
        settings.save()
        self.stdout.write('  system settings ensured')
