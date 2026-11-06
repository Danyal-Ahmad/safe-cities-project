"""Seed a demo-ready dataset: cameras, live feeds, registrations, one paid challan.

Run: python3 manage.py shell < scripts/seed_demo_data.py  (from repo root)
"""
import datetime
import os
import shutil

from accounts.models import User, VehicleRegistration
from cameras.models import Camera
from realtime.models import LiveFeed, CameraAssignment
from challans.models import Challan
from detections.models import Detection

TEST_VIDEO = '/home/z/my-project/upload/folder/a3d29032/16385744-hd_1920_1080_30fps.mp4'
MEDIA = 'uploads/live_feeds/demo'

# --- Cameras (CCTV wall) ---
CAMERAS = [
    ('CAM-001', 'Main Boulevard Gulberg', 'north', 'back'),
    ('CAM-002', 'Canal Road Bridge', 'east', 'front'),
    ('CAM-003', 'Jail Road Intersection', 'south', 'back'),
    ('CAM-004', 'Ferozepur Road Signal', 'west', 'front'),
    ('CAM-005', 'Liberty Market Roundabout', 'north', 'back'),
    ('CAM-006', 'Model Town Link Road', 'south', 'back'),
    ('CAM-007', 'Shahrah-e-Fatima Jinnah', 'east', 'front'),
    ('CAM-008', 'Railway Station Approach', 'west', 'front'),
]

created = []
for cam_id, location, legal, violation_side in CAMERAS:
    cam, _ = Camera.objects.update_or_create(
        camera_id=cam_id,
        defaults=dict(
            location=location,
            legal_direction=legal,
            violation_side=violation_side,
            is_active=True,
            health_status='online',
            capture_interval=5,
            auto_confirm_threshold=0.70,
        ),
    )
    created.append(cam)
print(f'cameras ready: {len(created)}')

# --- LiveFeed from the uploaded test video (loops on the CCTV wall) ---
if os.path.exists(TEST_VIDEO):
    feed_dir = os.path.join('uploads', 'live_feeds', 'demo')
    os.makedirs(feed_dir, exist_ok=True)
    dst = os.path.join(feed_dir, 'test_traffic.mp4')
    if not os.path.exists(dst):
        shutil.copy(TEST_VIDEO, dst)
    cam0 = created[0]
    LiveFeed.objects.update_or_create(
        title='CAM-001 | Demo Traffic Stream',
        defaults=dict(video_file='uploads/live_feeds/demo/test_traffic.mp4', camera=cam0, is_active=True),
    )
    # second feed for another camera so the wall shows two video tiles
    dst2 = os.path.join(feed_dir, 'test_traffic_2.mp4')
    if not os.path.exists(dst2):
        shutil.copy(TEST_VIDEO, dst2)
    LiveFeed.objects.update_or_create(
        title='CAM-003 | Demo Traffic Stream',
        defaults=dict(video_file='uploads/live_feeds/demo/test_traffic_2.mp4', camera=created[2], is_active=True),
    )
    print('live feeds ready: 2')

# --- Assign cameras to the demo officer ---
officer = User.objects.filter(email='officer@safecity.fyp').first()
if officer:
    for cam in created[:4]:
        CameraAssignment.objects.update_or_create(officer=officer, camera=cam, defaults={'is_active': True})
    CameraAssignment.objects.filter(officer=officer).exclude(camera__in=created[:4]).update(is_active=False)
    print('officer assignments: 4')

# --- Vehicle registrations (owner lookup works in demo mode) ---
citizen = User.objects.filter(email='citizen@safecity.fyp').first()
if citizen:
    VehicleRegistration.objects.update_or_create(
        owner=citizen, plate_number='LEA-1234',
        defaults=dict(vehicle_type='car', make='Toyota Corolla', year='2022', color='White', is_primary=True),
    )
    VehicleRegistration.objects.update_or_create(
        owner=citizen, plate_number='ABC-999',
        defaults=dict(vehicle_type='car', make='Honda Civic', year='2021', color='Silver'),
    )
    citizen.first_name = citizen.first_name or 'Danyal'
    citizen.save(update_fields=['first_name'])
print('vehicle registrations: 2')

print('DEMO DATA SEEDED')
