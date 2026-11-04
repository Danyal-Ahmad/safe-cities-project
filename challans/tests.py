from django.contrib.auth import get_user_model
from django.core.signing import TimestampSigner
from django.test import TestCase
from django.utils import timezone

from challans.models import Challan

User = get_user_model()


def make_challan(ticket='70000001', plate='LEA-100', cnic='35202-1234567-1',
                 owner='Ahmed Khan', phone='+923001234567'):
    return Challan.objects.create(
        ticket_no=ticket, plate_number=plate, cnic=cnic, owner_name=owner,
        phone=phone, address='House 12, Street 5, Model Town', chassis_no='CH-98765',
        violation_type='wrong_way', fine_amount=500, location='Main Boulevard',
        issue_date=timezone.localdate(), due_date=timezone.localdate())


class PublicPiiMaskingTests(TestCase):
    def setUp(self):
        self.challan = make_challan()

    def test_guest_detail_masks_pii(self):
        r = self.client.get(f'/challan/{self.challan.pk}/')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('Ahmed', body)
        self.assertNotIn('35202-1234567-1', body)
        self.assertNotIn('+923001234567', body)
        self.assertNotIn('House 12, Street 5, Model Town', body)
        self.assertNotIn('CH-98765', body)

    def test_db_rows_not_mutated_by_masking(self):
        self.client.get(f'/challan/{self.challan.pk}/')
        self.challan.refresh_from_db()
        self.assertEqual(self.challan.cnic, '35202-1234567-1')
        self.assertEqual(self.challan.address, 'House 12, Street 5, Model Town')


class PdfTokenTests(TestCase):
    def setUp(self):
        self.challan = make_challan(ticket='70000002', plate='LEA-200')

    def test_ticket_no_is_not_a_valid_token(self):
        r = self.client.get(f'/challan/{self.challan.pk}/pdf/?token={self.challan.ticket_no}')
        self.assertEqual(r.status_code, 403)

    def test_numeric_id_is_not_a_valid_token(self):
        r = self.client.get(f'/challan/{self.challan.pk}/pdf/?token={self.challan.pk}')
        self.assertEqual(r.status_code, 403)

    def test_signed_token_grants_pdf(self):
        signer = TimestampSigner()
        token = signer.sign(str(self.challan.pk))
        r = self.client.get(f'/challan/{self.challan.pk}/pdf/?token={token}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_tampered_signature_is_rejected(self):
        signer = TimestampSigner()
        token = signer.sign(str(self.challan.pk))[:-2] + 'xy'
        r = self.client.get(f'/challan/{self.challan.pk}/pdf/?token={token}')
        self.assertEqual(r.status_code, 403)


class PaymentIntegrityTests(TestCase):
    def setUp(self):
        self.challan = make_challan(ticket='70000003', plate='LEA-300')

    def test_guest_pay_done_never_mutates_status(self):
        r = self.client.get(f'/challan/{self.challan.pk}/pay/done/')
        self.assertEqual(r.status_code, 302)
        self.challan.refresh_from_db()
        self.assertEqual(self.challan.payment_status, 'UNPAID')

    def test_guest_pay_post_does_not_mark_paid(self):
        self.client.post(f'/challan/{self.challan.pk}/pay/', {'payment_method': ''})
        self.challan.refresh_from_db()
        self.assertEqual(self.challan.payment_status, 'UNPAID')

    def test_demo_checkout_requires_valid_reference(self):
        r = self.client.post('/api/v1/payment/demo-checkout/', {
            'ref': 'SC-forged-ref',
            'status': 'paid',
        })
        self.assertIn(r.status_code, (400, 403))
        self.challan.refresh_from_db()
        self.assertEqual(self.challan.payment_status, 'UNPAID')

    def test_demo_checkout_settles_pending_transaction(self):
        from payments.models import PaymentTransaction
        from admin.it_support_portal.models import PaymentMethod
        method = PaymentMethod.objects.filter(status=PaymentMethod.STATUS_ACTIVE).first()
        if method is None:
            self.skipTest('no active payment method seeded')
        from integrations.payments import initiate_payment
        init = initiate_payment(
            self.challan, method,
            f'/challan/{self.challan.pk}/pay/done/', '/api/v1/payment/webhook/')
        txn = PaymentTransaction.objects.create(
            ticket_no=self.challan.ticket_no, challan=self.challan,
            provider=init['provider'], amount=self.challan.fine_amount,
            status=PaymentTransaction.STATUS_PENDING, txn_ref=init['reference'])
        r = self.client.post('/api/v1/payment/demo-checkout/', {
            'ref': init['reference'],
            'status': 'paid',
        })
        self.assertEqual(r.status_code, 200)
        self.challan.refresh_from_db()
        self.assertEqual(self.challan.payment_status, 'PAID')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'success')

    def test_demo_checkout_reference_is_single_use(self):
        from payments.models import PaymentTransaction
        from admin.it_support_portal.models import PaymentMethod
        method = PaymentMethod.objects.filter(status=PaymentMethod.STATUS_ACTIVE).first()
        if method is None:
            self.skipTest('no active payment method seeded')
        from integrations.payments import initiate_payment
        init = initiate_payment(
            self.challan, method,
            f'/challan/{self.challan.pk}/pay/done/', '/api/v1/payment/webhook/')
        PaymentTransaction.objects.create(
            ticket_no=self.challan.ticket_no, challan=self.challan,
            provider=init['provider'], amount=self.challan.fine_amount,
            status=PaymentTransaction.STATUS_PENDING, txn_ref=init['reference'])
        self.client.post('/api/v1/payment/demo-checkout/', {'ref': init['reference'], 'status': 'paid'})
        self.challan.refresh_from_db()
        before = self.challan.payment_status
        other = make_challan(ticket='70000009', plate='LEA-900')
        rr = self.client.post('/api/v1/payment/demo-checkout/', {'ref': init['reference'], 'status': 'paid'})
        self.assertEqual(rr.status_code, 400)
        other.refresh_from_db()
        self.assertEqual(other.payment_status, 'UNPAID')
        self.assertEqual(before, 'PAID')


class GuestAppealSecurityTests(TestCase):
    def setUp(self):
        self.challan = make_challan(ticket='70000004', plate='LEA-400')

    def test_guest_appeal_requires_matching_cnic(self):
        self.client.post(f'/challan/{self.challan.pk}/', {
            'action': 'submit_appeal',
            'reason': 'x' * 40,
            'review_reason': 'other',
            'guest_cnic': '35202-0000000-0',
            'guest_name': 'Attacker',
        })
        from appeals.models import ChallanAppeal
        appeals = ChallanAppeal.objects.filter(challan=self.challan)
        self.assertEqual(appeals.count(), 0)


class SearchRateLimitTests(TestCase):
    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_rate_limit_returns_429(self):
        make_challan(ticket='70000005', plate='LEA-500')
        codes = []
        for i in range(30):
            r = self.client.get('/', {'plate': f'LEA-{500 + i}'})
            codes.append(r.status_code)
        self.assertIn(429, codes)


class XssTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_search_input_is_sanitized(self):
        make_challan(ticket='70000006', plate='LEA-600')
        r = self.client.get('/', {'plate': "<script>alert(1)</script>"})
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertNotIn('<script>', body)
        self.assertNotIn('alert(1)', body)

    def test_sql_injection_is_harmless(self):
        make_challan(ticket='70000007', plate='LEA-700')
        r = self.client.get('/', {'plate': "LEA' OR '1'='1"})
        self.assertIn(r.status_code, (200, 429))
        body = r.content.decode()
        self.assertNotIn('LEA-100', body)


class CsrfTests(TestCase):
    def test_post_without_csrf_is_rejected(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        r = c.post('/challan/1/', {'action': 'submit_appeal', 'reason': 'x' * 40})
        self.assertEqual(r.status_code, 403)
