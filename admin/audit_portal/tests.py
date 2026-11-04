import datetime

from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from admin.dig_portal.models import (
    AuditLog, LoginEvent, ChallanTemplate, AuditTemplate, AuditDocument, SystemSettings,
)
from challans.pdf_service import FILE_TEMPLATE_MAP as CHALLAN_MAP, generate_challan_pdf
from admin.audit_portal.pdf_service import (
    FILE_TEMPLATE_MAP as AUDIT_MAP, generate_audit_pdf, build_audit_context,
)
from detections.ai import normalize_pk_plate, is_valid_pk_plate, is_known_pk_series

User = get_user_model()

IT_PW = 'SafeCity#2026FYP'


class PkPlateFormatTests(TestCase):
    def test_valid_plates(self):
        for raw, norm in [('LEA-1234', 'LEA-1234'), ('lea1234', 'LEA-1234'),
                          ('ISB 456', 'ISB-456'), ('LE-12', 'LE-12'), ('ABC-9999', 'ABC-9999')]:
            self.assertEqual(normalize_pk_plate(raw), norm)
            self.assertTrue(is_valid_pk_plate(norm))

    def test_invalid_plates(self):
        for raw in ['A-123', 'ABCD-123', 'XY-99999', '1234', 'AB-12-34-56', '']:
            self.assertFalse(is_valid_pk_plate(normalize_pk_plate(raw)),
                             f"{raw} should be rejected")

    def test_known_series(self):
        self.assertTrue(is_known_pk_series('LEA-1234'))
        self.assertTrue(is_known_pk_series('ISB-456'))
        self.assertFalse(is_known_pk_series('ZZQ-111'))


class LoginEventTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        from wrongway_system.security import rate_limit as _rl
        _rl._hits.clear()

    @classmethod
    def setUpTestData(cls):
        cls.it = User.objects.create_user(
            username='it_studio@safecity.fyp', email='it_studio@safecity.fyp',
            password=IT_PW, role='IT')
        cls.audit = User.objects.create_user(
            username='aud@safecity.fyp', email='aud@safecity.fyp',
            password=IT_PW, role='AUDIT')
        cls.dig = User.objects.create_user(
            username='dg@safecity.fyp', email='dg@safecity.fyp',
            password=IT_PW, role='DIG')

    def test_failed_login_records_device_and_ip(self):
        c = Client(HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0')
        c.post('/auth/admin/login/', {'username': 'it_studio@safecity.fyp', 'password': 'nope'})
        ev = LoginEvent.objects.filter(username_attempted='it_studio@safecity.fyp').first()
        self.assertIsNotNone(ev)
        self.assertFalse(ev.success)
        self.assertEqual(ev.failure_reason, 'invalid_credentials')
        self.assertEqual(ev.ip_address, '127.0.0.1')
        self.assertIn('Chrome', ev.browser)
        self.assertEqual(ev.device_type, 'Desktop')

    def test_successful_login_records_user(self):
        c = Client(HTTP_USER_AGENT='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1')
        c.post('/auth/admin/login/', {'username': 'it_studio@safecity.fyp', 'password': IT_PW})
        ev = LoginEvent.objects.filter(username_attempted='it_studio@safecity.fyp', success=True).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.user, self.it)
        self.assertEqual(ev.portal, 'admin')
        self.assertEqual(ev.device_type, 'Mobile')

    def test_audit_portal_can_view_login_events(self):
        c = Client()
        c.login(username='aud@safecity.fyp', password=IT_PW)
        r = c.get('/portal/audit/login-events/')
        self.assertEqual(r.status_code, 200)
        r2 = c.get('/portal/audit/login-events/export/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2['Content-Type'], 'text/csv')


class StudioPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.it = User.objects.create_user(
            username='studio_it@safecity.fyp', email='studio_it@safecity.fyp',
            password=IT_PW, role='IT')
        cls.dig = User.objects.create_user(
            username='studio_dig@safecity.fyp', email='studio_dig@safecity.fyp',
            password=IT_PW, role='DIG')
        cls.officer = User.objects.create_user(
            username='studio_off@safecity.fyp', email='studio_off@safecity.fyp',
            password=IT_PW, role='OFFICER')

    def test_it_can_access_challan_studio(self):
        c = Client()
        c.login(username='studio_it@safecity.fyp', password=IT_PW)
        self.assertEqual(c.get('/portal/it/challan-studio/').status_code, 200)
        self.assertEqual(c.get('/portal/it/audit-studio/').status_code, 200)

    def test_dig_select_only_pages(self):
        c = Client()
        c.login(username='studio_dig@safecity.fyp', password=IT_PW)
        r = c.get('/portal/dig/challan-template-select/')
        self.assertEqual(r.status_code, 200)
        r2 = c.get('/portal/dig/audit-template-select/')
        self.assertEqual(r2.status_code, 200)
        # DIG cannot enter the studios
        r3 = c.get('/portal/it/challan-studio/')
        self.assertEqual(r3.status_code, 302)

    def test_officer_blocked_from_studios(self):
        c = Client()
        c.login(username='studio_off@safecity.fyp', password=IT_PW)
        self.assertEqual(c.get('/portal/it/challan-studio/').status_code, 302)
        self.assertEqual(c.get('/portal/it/audit-studio/').status_code, 302)
        self.assertEqual(c.get('/portal/audit/generate-document/').status_code, 302)

    def test_studio_save_and_activate(self):
        c = Client()
        c.login(username='studio_it@safecity.fyp', password=IT_PW)
        html = ('<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
                '<div>Challan {{ challan.ticket_no }} {{ challan.plate_number }}</div></body></html>')
        r = c.post('/portal/it/challan-studio/', {
            'action': 'save', 'template_id': '', 'name': 'CI Test Design',
            'html_content': html, 'design_json': '{"blocks":[]}', 'activate': '1'})
        self.assertEqual(r.status_code, 302)
        obj = ChallanTemplate.objects.filter(name='CI Test Design').first()
        self.assertIsNotNone(obj)
        self.assertTrue(obj.is_active)
        self.assertEqual(SystemSettings.get().pdf_template, f'db:{obj.id}')
        audit_entry = AuditLog.objects.filter(action='challan_studio.activate').first()
        self.assertIsNotNone(audit_entry)


class AuditDocumentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.audit = User.objects.create_user(
            username='auditor@safecity.fyp', email='auditor@safecity.fyp',
            password=IT_PW, role='AUDIT')

    def test_all_five_audit_templates_render(self):
        for key in AUDIT_MAP:
            pdf = generate_audit_pdf(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31),
                                     self.audit, template_key=key)
            self.assertGreater(len(pdf), 10000, f'{key} rendered too small')
            self.assertTrue(pdf.startswith(b'%PDF'))

    def test_audit_document_saved_with_hash(self):
        from admin.audit_portal.pdf_service import save_audit_document
        doc = save_audit_document(datetime.date(2026, 2, 1), datetime.date(2026, 2, 28),
                                  self.audit, template_key='compliance_certificate')
        self.assertEqual(len(doc.sha256), 64)
        self.assertTrue(doc.pdf_file)
        self.assertTrue(AuditLog.objects.filter(action='audit.document_generate').exists())

    def test_auditor_generate_page_flow(self):
        c = Client()
        c.login(username='auditor@safecity.fyp', password=IT_PW)
        r = c.post('/portal/audit/generate-document/', {
            'period_from': '2026-03-01', 'period_to': '2026-03-31',
            'title': 'March Audit', 'template_key': 'financial_audit_statement'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(AuditDocument.objects.filter(title='March Audit').exists())


class ChallanTemplateRenderTests(TestCase):
    def test_all_five_challan_templates_render(self):
        from challans.models import Challan
        challan = Challan.objects.create(
            ticket_no='20999001', plate_number='LEA-1234', violation_type='wrong_way',
            fine_amount=2000, location='Test Road', issue_date=datetime.date.today(),
            due_date=datetime.date.today() + datetime.timedelta(days=30))
        for key in CHALLAN_MAP:
            pdf = generate_challan_pdf(challan)
            self.assertTrue(pdf.startswith(b'%PDF'), f'{key} did not produce a PDF')
        challan.delete()
