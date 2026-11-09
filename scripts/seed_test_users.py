"""Seed the full E2E role matrix: 27+ users across all 7 roles plus demo data.

Idempotent: safe to run repeatedly (update_or_create everywhere).
Run: python3 manage.py shell < scripts/seed_test_users.py
"""
import datetime
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wrongway_system.settings')

import django

django.setup()

from accounts.models import User, VehicleRegistration
from cameras.models import Camera
from realtime.models import LiveFeed, CameraAssignment
from challans.models import Challan

TEST_VIDEO = '/home/z/my-project/upload/folder/a3d29032/16385744-hd_1920_1080_30fps.mp4'
NEW_PASSWORD = 'E2E@2026-Matrix!'

CAMERAS = [
    ('CAM-001', 'Main Boulevard Gulberg', 'north', 'back', 5),
    ('CAM-002', 'Canal Road Bridge', 'east', 'front', 5),
    ('CAM-003', 'Jail Road Intersection', 'south', 'back', 5),
    ('CAM-004', 'Ferozepur Road Signal', 'west', 'front', 5),
    ('CAM-005', 'Liberty Market Roundabout', 'north', 'back', 5),
    ('CAM-006', 'Model Town Link Road', 'south', 'back', 5),
    ('CAM-007', 'Shahrah-e-Fatima Jinnah', 'east', 'front', 5),
    ('CAM-008', 'Railway Station Approach', 'west', 'front', 5),
    ('CAM-E2E-01', 'E2E Pipeline Avenue', 'north', 'back', 1),
    ('CAM-E2E-02', 'E2E Tracking Avenue', 'north', 'back', 2),
]


def ensure_user(username, role, first, last, password, **extra):
    defaults = dict(
        first_name=first, last_name=last, role=role,
        is_active=True, **extra,
    )
    user, created = User.objects.update_or_create(username=username, defaults=defaults)
    user.set_password(password)
    user.save()
    return user, created


def main():
    created_count = 0

    original_passwords = {
        'dig@safecity.fyp': 'Demo@DIG-2026secure',
        'ssp@safecity.fyp': 'Demo@SSP-2026secure',
        'supervisor@safecity.fyp': 'Demo@SUPV-2026secure',
        'officer@safecity.fyp': 'Demo@OFFCR-2026secure',
        'audit@safecity.fyp': 'Demo@AUDT-2026secure',
        'itsupport@safecity.fyp': 'Demo@ITSP-2026secure',
        'citizen@safecity.fyp': 'Demo@CZN-2026secure',
    }
    for uname, pw in original_passwords.items():
        u = User.objects.filter(username=uname).first()
        if u is None:
            continue
        if not u.check_password(pw):
            u.set_password(pw)
        u.failed_login_attempts = 0
        u.locked_until = None
        u.is_active = True
        u.save()
    print('original 7 accounts: passwords normalized, lockouts cleared')

    for cam_id, location, legal, side, interval in CAMERAS:
        Camera.objects.update_or_create(
            camera_id=cam_id,
            defaults=dict(
                location=location, legal_direction=legal, violation_side=side,
                capture_interval=interval, is_active=True,
                health_status='online', auto_confirm_threshold=0.70,
            ),
        )
    print(f'cameras ready: {len(CAMERAS)}')

    if os.path.exists(TEST_VIDEO):
        feed_dir = os.path.join('uploads', 'live_feeds', 'demo')
        os.makedirs(feed_dir, exist_ok=True)
        dst = os.path.join(feed_dir, 'test_traffic.mp4')
        if not os.path.exists(dst):
            shutil.copy(TEST_VIDEO, dst)
        cam1 = Camera.objects.get(camera_id='CAM-001')
        LiveFeed.objects.update_or_create(
            title='CAM-001 | Demo Traffic Stream',
            defaults=dict(video_file='uploads/live_feeds/demo/test_traffic.mp4', camera=cam1, is_active=True),
        )
        dst2 = os.path.join(feed_dir, 'test_traffic_2.mp4')
        if not os.path.exists(dst2):
            shutil.copy(TEST_VIDEO, dst2)
        cam3 = Camera.objects.get(camera_id='CAM-003')
        LiveFeed.objects.update_or_create(
            title='CAM-003 | Demo Traffic Stream',
            defaults=dict(video_file='uploads/live_feeds/demo/test_traffic_2.mp4', camera=cam3, is_active=True),
        )
        print('live feeds ready: 2')

    staff = [
        ('dig2@safecity.fyp', 'DIG', 'Malik', 'Tariq', 'Deputy Inspector General', 'Central Region'),
        ('ssp2@safecity.fyp', 'SSP', 'Ayesha', 'Khan', 'Senior Superintendent', 'North Region'),
        ('ssp3@safecity.fyp', 'SSP', 'Bilal', 'Sheikh', 'Senior Superintendent', 'South Region'),
        ('supv2@safecity.fyp', 'SUPV', 'Farah', 'Iqbal', 'Shift Supervisor', 'Central Region'),
        ('supv3@safecity.fyp', 'SUPV', 'Usman', 'Ghani', 'Shift Supervisor', 'North Region'),
        ('officer2@safecity.fyp', 'OFFICER', 'Kamran', 'Aslam', 'Enforcement Officer', 'Central Region'),
        ('officer3@safecity.fyp', 'OFFICER', 'Nadia', 'Hussain', 'Enforcement Officer', 'Central Region'),
        ('officer4@safecity.fyp', 'OFFICER', 'Zeeshan', 'Mirza', 'Enforcement Officer', 'South Region'),
        ('officer5@safecity.fyp', 'OFFICER', 'Hira', 'Butt', 'Enforcement Officer', 'North Region'),
        ('audit2@safecity.fyp', 'AUDIT', 'Salman', 'Qureshi', 'Audit Officer', 'HQ'),
        ('it2@safecity.fyp', 'IT', 'Rabia', 'Anwar', 'IT Support Engineer', 'HQ'),
    ]
    for i, (uname, role, first, last, designation, region) in enumerate(staff, start=1):
        _, created = ensure_user(
            uname, role, first, last, NEW_PASSWORD,
            email=uname,
            phone=f'+9230045678{i:02d}',
            staff_id=f'SC-2026-{role}-{i:03d}',
            designation=designation, region=region, department='Traffic Enforcement',
        )
        created_count += int(created)

    citizens = [
        ('citizen2@safecity.fyp', 'Ahmed', 'Raza', '42201-7788123-4', 'KHI-7788', 'LEA-4455'),
        ('citizen3@safecity.fyp', 'Fatima', 'Noor', '42201-4527999-1', 'LRA-4527', None),
        ('citizen4@safecity.fyp', 'Omar', 'Farooq', '42201-1122334-4', 'RWP-2211', None),
        ('citizen5@safecity.fyp', 'Zainab', 'Ali', '42201-3344556-6', 'MNR-3344', None),
        ('citizen6@safecity.fyp', 'Hassan', 'Siddiqui', '42201-5566778-8', 'FSD-5566', None),
        ('citizen7@safecity.fyp', 'Areeba', 'Malik', '42201-7788990-0', 'GRW-7789', None),
        ('citizen8@safecity.fyp', 'Tariq', 'Javed', '42201-9900112-2', 'LHR-1122', None),
        ('citizen9@safecity.fyp', 'Sana', 'Chaudhry', '42201-1234567-7', 'ISB-3344', None),
        ('citizen10@safecity.fyp', 'Bilal', 'Ahmed', '42201-7654321-1', 'MULTAN-1188', None),
    ]
    for i, (uname, first, last, cnic, plate, plate2) in enumerate(citizens, start=20):
        _, created = ensure_user(
            uname, 'USER', first, last, NEW_PASSWORD,
            email=uname, phone=f'+9230077889{i - 19:02d}', cnic=cnic,
        )
        created_count += int(created)
        user = User.objects.get(username=uname)
        VehicleRegistration.objects.update_or_create(
            owner=user, plate_number=plate,
            defaults=dict(vehicle_type='car', make='Toyota Corolla', year='2022', color='White', is_primary=True),
        )
        if plate2:
            VehicleRegistration.objects.update_or_create(
                owner=user, plate_number=plate2,
                defaults=dict(vehicle_type='car', make='Honda Civic', year='2021', color='Silver'),
            )

    primary = User.objects.filter(email='citizen@safecity.fyp').first()
    if primary:
        primary.cnic = primary.cnic or '42201-1234567-9'
        primary.first_name = primary.first_name or 'Danyal'
        primary.save(update_fields=['cnic', 'first_name'])
        VehicleRegistration.objects.update_or_create(
            owner=primary, plate_number='LEA-1234',
            defaults=dict(vehicle_type='car', make='Toyota Corolla', year='2022', color='White', is_primary=True),
        )
        VehicleRegistration.objects.update_or_create(
            owner=primary, plate_number='ABC-999',
            defaults=dict(vehicle_type='car', make='Honda Civic', year='2021', color='Silver'),
        )
        print('primary citizen vehicle registrations: 2')

    assignments = {
        'officer@safecity.fyp': ['CAM-001'],
        'officer2@safecity.fyp': ['CAM-E2E-01'],
        'officer3@safecity.fyp': ['CAM-005'],
        'officer4@safecity.fyp': ['CAM-007'],
        'officer5@safecity.fyp': ['CAM-002'],
    }
    for uname, cam_ids in assignments.items():
        officer = User.objects.filter(username=uname).first()
        if not officer:
            continue
        for cam_id in cam_ids:
            cam = Camera.objects.filter(camera_id=cam_id).first()
            if cam:
                CameraAssignment.objects.update_or_create(
                    officer=officer, camera=cam, defaults={'is_active': True},
                )
        CameraAssignment.objects.filter(officer=officer).exclude(
            camera__camera_id__in=cam_ids,
        ).update(is_active=False)
    print('camera assignments ready')

    total = User.objects.count()
    by_role = {}
    for u in User.objects.all():
        by_role[u.role] = by_role.get(u.role, 0) + 1
    print(f'users total: {total} | by role: {by_role}')
    print(f'new users created this run: {created_count}')
    print('E2E USER MATRIX SEEDED')


if __name__ == '__main__':
    main()
else:
    main()
