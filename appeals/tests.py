from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from challans.models import Challan
from cameras.models import Camera
from admin.dig_portal.models import Notification
from .models import ChallanAppeal


def _staff(role, email):
    return User.objects.create_user(
        username=email, email=email, password='TestPass#2026',
        role=role, first_name=role.title(), last_name='Tester',
        is_staff=True,
    )


class SspOnlyAppealFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.citizen = User.objects.create_user(
            username='flowcitizen@test', email='flowcitizen@test', password='TestPass#2026',
            role=User.USER, first_name='Flow', last_name='Citizen', cnic='3520212345671',
        )
        cls.ssp = _staff(User.SSP, 'flowssp@test')
        cls.dig = _staff(User.DIG, 'flowdig@test')
        cls.officer = _staff(User.OFFICER, 'flowofficer@test')
        cls.camera = Camera.objects.create(
            camera_id='CAM-FLOW', location='Lahore', is_active=True,
            latitude=31.5, longitude=74.3,
        )
        cls.challan = Challan.objects.create(
            ticket_no='2026099001',
            plate_number='LEA-1234',
            violation_type='wrong_way',
            fine_amount=500,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            payment_status='UNPAID',
            camera=cls.camera,
            owner_name='Flow Citizen',
            cnic='3520212345671',
        )

    def test_submit_notifies_ssp_only_not_dig(self):
        self.client.force_login(self.citizen)
        self.client.post(reverse('citizen_portal:submit_appeal', args=[self.challan.id]), {
            'reason': 'This is a mistake challan. My vehicle was parked at home that day, proof attached.',
        })
        self.assertEqual(ChallanAppeal.objects.count(), 1)
        appeal = ChallanAppeal.objects.first()
        self.assertEqual(appeal.status, ChallanAppeal.PENDING)
        self.assertTrue(Notification.objects.filter(recipient=self.ssp, category='appeal_submit').exists())
        self.assertFalse(Notification.objects.filter(recipient=self.dig).exists())

    def test_ssp_approval_voids_challan_and_notifies_citizen(self):
        appeal = ChallanAppeal.objects.create(
            challan=self.challan, submitted_by=self.citizen, reason='x' * 40,
        )
        self.client.force_login(self.ssp)
        self.client.post(reverse('ssp_portal:decide_appeal', args=[appeal.id]), {
            'decision': 'APPROVED', 'reason': 'Verified evidence, the challan was issued in error.',
        })
        appeal.refresh_from_db()
        self.challan.refresh_from_db()
        self.assertEqual(appeal.status, ChallanAppeal.APPROVED)
        self.assertEqual(appeal.ssp_reviewed_by, self.ssp)
        self.assertEqual(self.challan.payment_status, Challan.VOIDED)
        self.assertTrue(Notification.objects.filter(recipient=self.citizen, category='appeal_approved').exists())

    def test_ssp_rejection_keeps_challan_active(self):
        appeal = ChallanAppeal.objects.create(
            challan=self.challan, submitted_by=self.citizen, reason='x' * 40,
        )
        self.client.force_login(self.ssp)
        self.client.post(reverse('ssp_portal:decide_appeal', args=[appeal.id]), {
            'decision': 'REJECTED', 'reason': 'Evidence clearly shows the violation, appeal refused.',
        })
        appeal.refresh_from_db()
        self.challan.refresh_from_db()
        self.assertEqual(appeal.status, ChallanAppeal.REJECTED)
        self.assertEqual(self.challan.payment_status, Challan.UNPAID)

    def test_dig_cannot_decide_appeal(self):
        appeal = ChallanAppeal.objects.create(
            challan=self.challan, submitted_by=self.citizen, reason='x' * 40,
        )
        client = Client()
        client.force_login(self.dig)
        client.post(reverse('dig:appeal_override', args=[appeal.id]), {
            'action': 'approve', 'comment': 'DIG trying to decide, should be denied by the system.',
        })
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, ChallanAppeal.PENDING)
        self.challan.refresh_from_db()
        self.assertEqual(self.challan.payment_status, Challan.UNPAID)

    def test_officer_cannot_decide_appeal(self):
        appeal = ChallanAppeal.objects.create(
            challan=self.challan, submitted_by=self.citizen, reason='x' * 40,
        )
        client = Client()
        client.force_login(self.officer)
        client.post(reverse('dig:appeal_override', args=[appeal.id]), {
            'action': 'reject', 'comment': 'Officer trying to decide, should be denied by the system.',
        })
        appeal.refresh_from_db()
        self.assertEqual(appeal.status, ChallanAppeal.PENDING)

    def test_citizen_escalation_route_removed(self):
        self.client.force_login(self.citizen)
        response = self.client.get('/portal/citizen/appeal/1/escalate/')
        self.assertEqual(response.status_code, 404)

    def test_dig_escalation_list_route_removed(self):
        client = Client()
        client.force_login(self.dig)
        response = client.get('/portal/dig/escalations/')
        self.assertEqual(response.status_code, 404)

    def test_appeals_queue_visible_to_dig_ssp_supervisor_audit(self):
        _staff(User.SUPERVISOR, 'flowsupv@test')
        _staff(User.AUDIT, 'flowaudit@test')
        _staff(User.IT_SUPPORT, 'flowit@test')
        routes = {
            'flowdig@test': ('dig:appeals_queue', 200),
            'flowssp@test': ('ssp_portal:appeal_list', 200),
            'flowsupv@test': ('supervisor_portal:appeals_queue', 200),
            'flowaudit@test': ('audit_portal:appeals_queue', 200),
            'flowit@test': ('dig:appeals_queue', 302),
        }
        for email, (route, code) in routes.items():
            client = Client()
            user = User.objects.get(email=email)
            client.force_login(user)
            response = client.get(reverse(route))
            self.assertEqual(response.status_code, code, f'{email} at {route} should get {code}')

    def test_model_has_no_escalation_fields(self):
        field_names = {f.name for f in ChallanAppeal._meta.get_fields()}
        for gone in ('current_stage', 'is_escalated', 'escalated_at', 'escalation_reason',
                     'dig_comment', 'dig_reviewed_by', 'dig_reviewed_at', 'officer_comment'):
            self.assertNotIn(gone, field_names)

