from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import VehicleRegistration
from challans.models import Challan
from detections.models import Detection

User = get_user_model()


def make_user(email, role, cnic=None, phone=None, password='Passw0rd!Long123'):
    u = User.objects.create(
        username=email, email=email, first_name='Test', last_name='User',
        role=role, is_active=True, cnic=cnic, phone=phone,
    )
    u.set_password(password)
    u.save()
    return u


class PortalIsolationTests(TestCase):

    PORTALS = [
        ('/portal/dig/', 'DIG'),
        ('/portal/ssp/', 'SSP'),
        ('/portal/supervisor/', 'SUPV'),
        ('/portal/officer/', 'OFFICER'),
        ('/portal/audit/', 'AUDIT'),
        ('/portal/it/', 'IT'),
        ('/portal/citizen/', 'USER'),
    ]

    def test_cross_role_access_is_redirected(self):
        users = {
            'DIG': make_user('dig1@t.fyp', 'DIG'),
            'SSP': make_user('ssp1@t.fyp', 'SSP'),
            'SUPV': make_user('supv1@t.fyp', 'SUPV'),
            'OFFICER': make_user('off1@t.fyp', 'OFFICER'),
            'AUDIT': make_user('aud1@t.fyp', 'AUDIT'),
            'IT': make_user('it1@t.fyp', 'IT'),
            'USER': make_user('usr1@t.fyp', 'USER'),
        }
        for path, owner_role in self.PORTALS:
            for role, user in users.items():
                self.client.force_login(user)
                r = self.client.get(path)
                if role == owner_role:
                    self.assertIn(r.status_code, (200, 302), f'{role} on {path}')
                else:
                    self.assertEqual(r.status_code, 302, f'{role} blocked from {path}')
                    self.assertNotEqual(r['Location'], path)

    def test_anonymous_is_redirected_to_login(self):
        for path, _ in self.PORTALS:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 302)


class PermissionMatrixTests(TestCase):
    def test_manual_annotation_permission_is_gone(self):
        from accounts.permissions import PERMISSIONS, get_role_permissions
        self.assertNotIn('manual_annotation', PERMISSIONS)
        self.assertNotIn('add_manual_challan', PERMISSIONS)
        for role in ('IT', 'OFFICER', 'DIG'):
            self.assertNotIn('manual_annotation', get_role_permissions(role))

    def test_payment_permissions_match_matrix(self):
        from accounts.permissions import get_role_permissions
        for role in ('DIG', 'IT'):
            self.assertIn('record_payment', get_role_permissions(role))
        for role in ('SSP', 'SUPV', 'OFFICER', 'AUDIT', 'USER'):
            self.assertNotIn('record_payment', get_role_permissions(role))

    def test_role_levels_rank_correctly(self):
        from accounts.permissions import get_role_level
        self.assertGreater(get_role_level('DIG'), get_role_level('SSP'))
        self.assertGreater(get_role_level('SSP'), get_role_level('SUPV'))
        self.assertGreater(get_role_level('SUPV'), get_role_level('OFFICER'))
        self.assertGreater(get_role_level('DIG'), get_role_level('USER'))


class AnnotationRemovalTests(TestCase):
    def test_annotation_urls_are_gone(self):
        officer = make_user('off2@t.fyp', 'OFFICER')
        self.client.force_login(officer)
        for url in ('/portal/officer/annotate/', '/portal/officer/annotate/submit/',
                    '/portal/officer/live-tracking/annotation-save/',
                    '/portal/officer/challan/add/',
                    '/portal/officer/detection/1/confirm/',
                    '/video/manual/1/', '/video/annotate/1/'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 404, f'{url} must not exist')

    def test_sidebar_has_no_annotation_links(self):
        officer = make_user('off3@t.fyp', 'OFFICER')
        self.client.force_login(officer)
        r = self.client.get('/portal/officer/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b'Manual Annotation', r.content)
        self.assertNotIn(b'Add Manual Challan', r.content)


class OfficerScopingTests(TestCase):
    def setUp(self):
        from cameras.models import Camera
        from realtime.models import CameraAssignment
        self.officer = make_user('scoped@t.fyp', 'OFFICER')
        self.camera_a = Camera.objects.create(
            camera_id='CAM-A', location='A', is_active=True, is_enrolled=True)
        self.camera_b = Camera.objects.create(
            camera_id='CAM-B', location='B', is_active=True, is_enrolled=True)
        CameraAssignment.objects.create(camera=self.camera_a, officer=self.officer, is_active=True)
        Detection.objects.create(
            camera=self.camera_a, ai_plate_text='AAA-111', status=Detection.CONFIRMED)
        Detection.objects.create(
            camera=self.camera_b, ai_plate_text='BBB-222', status=Detection.CONFIRMED)

    def test_officer_queue_only_shows_assigned_camera(self):
        self.client.force_login(self.officer)
        r = self.client.get('/portal/officer/queue/')
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertNotIn('BBB-222', content)

    def test_officer_cannot_snapshot_unassigned_camera(self):
        self.client.force_login(self.officer)
        r = self.client.get(f'/portal/officer/cameras/{self.camera_b.pk}/snapshot/')
        self.assertEqual(r.status_code, 404)

    def test_officer_cannot_stream_unassigned_camera(self):
        self.client.force_login(self.officer)
        r = self.client.get(f'/portal/officer/cameras/{self.camera_b.pk}/stream-url/')
        self.assertEqual(r.status_code, 404)


class CitizenIsolationTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        self.citizen_a = make_user('citz_a@t.fyp', 'USER', cnic='35202-1111111-1', phone='+923001111111')
        self.citizen_b = make_user('citz_b@t.fyp', 'USER', cnic='35202-2222222-2', phone='+923002222222')
        VehicleRegistration.objects.create(owner=self.citizen_a, plate_number='LEA-100')
        self.challan_a = Challan.objects.create(
            ticket_no='90000001', plate_number='LEA-100', cnic='35202-1111111-1',
            phone='+923001111111', violation_type='wrong_way', fine_amount=500,
            location='X', issue_date=timezone.localdate(),
            due_date=timezone.localdate())
        self.challan_b = Challan.objects.create(
            ticket_no='90000002', plate_number='LEA-200', cnic='35202-2222222-2',
            phone='+923002222222', violation_type='wrong_way', fine_amount=500,
            location='Y', issue_date=timezone.localdate(),
            due_date=timezone.localdate())

    def test_citizen_home_only_shows_own_challans(self):
        self.client.force_login(self.citizen_b)
        r = self.client.get('/portal/citizen/')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertNotIn('35202-1111111-1', body)
        self.assertNotIn('90000001', body)

    def test_citizen_cannot_open_foreign_pay_page(self):
        self.client.force_login(self.citizen_b)
        r = self.client.get(f'/portal/citizen/challan/{self.challan_a.pk}/pay/')
        self.assertEqual(r.status_code, 302)

    def test_citizen_cannot_appeal_foreign_challan(self):
        self.client.force_login(self.citizen_b)
        r = self.client.post(f'/portal/citizen/challan/{self.challan_a.pk}/appeal/', {
            'reason': 'x' * 30, 'review_reason': 'other',
        })
        self.assertEqual(r.status_code, 302)
        from appeals.models import ChallanAppeal
        self.assertEqual(
            ChallanAppeal.objects.filter(challan=self.challan_a, submitted_by=self.citizen_b).count(), 0)


class CitizenAccountIsolationTests(TestCase):

    def test_live_recent_detections_blocked_for_citizens(self):
        citizen = make_user('citz_feed@t.fyp', 'USER')
        self.client.force_login(citizen)
        r = self.client.get('/realtime/api/live/recent-detections/')
        self.assertEqual(r.status_code, 302)

