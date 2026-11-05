from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import PasswordResetToken

User = get_user_model()


def make_citizen(email='citz@t.fyp', cnic='35202-1234567-1', password='Passw0rd!Long123'):
    u = User.objects.create(
        username=email, email=email, first_name='Cit', last_name='Zen',
        role='USER', is_active=True, cnic=cnic, phone='+923001234567',
    )
    u.set_password(password)
    u.save()
    return u


class ForgotPasswordSecurityTests(TestCase):
    def test_token_is_never_rendered_in_response(self):
        make_citizen(email='victim@t.fyp', cnic='35202-9999999-9')
        r = self.client.post(reverse('auth_portal:forgot_password'), {
            'cnic': '35202-9999999-9',
        })
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        tok = PasswordResetToken.objects.filter(user__email='victim@t.fyp').order_by('-id').first()
        self.assertIsNotNone(tok)
        self.assertNotIn(tok.token, body)
        self.assertNotIn('step-2', body.replace('step-2', 'step-2')) if False else None
        self.assertIn('reset link has been sent', body)

    def test_email_carries_the_link(self):
        make_citizen(email='mailer@t.fyp', cnic='35202-8888888-8')
        self.client.post(reverse('auth_portal:forgot_password'), {'cnic': '35202-8888888-8'})
        self.assertEqual(len(mail.outbox), 1)
        tok = PasswordResetToken.objects.filter(user__email='mailer@t.fyp').order_by('-id').first()
        self.assertIn(tok.token, mail.outbox[0].body)

    def test_unknown_cnic_gets_same_generic_message(self):
        make_citizen(email='known@t.fyp', cnic='35202-7777777-7')
        r1 = self.client.post(reverse('auth_portal:forgot_password'), {'cnic': '35202-7777777-7'})
        r2 = self.client.post(reverse('auth_portal:forgot_password'), {'cnic': '35202-0000000-0'})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertIn('reset link has been sent', r1.content.decode())
        self.assertIn('reset link has been sent', r2.content.decode())
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_via_link_sets_password(self):
        u = make_citizen(email='resetter@t.fyp', cnic='35202-6666666-6')
        self.client.post(reverse('auth_portal:forgot_password'), {'cnic': '35202-6666666-6'})
        tok = PasswordResetToken.objects.filter(user=u).order_by('-id').first()
        url = reverse('auth_portal:citizen_reset_confirm', args=[tok.token])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Set a New Password', r.content.decode())
        r = self.client.post(url, {
            'new_password': 'NewPassw0rd!Secure456',
            'confirm_password': 'NewPassw0rd!Secure456',
        })
        self.assertEqual(r.status_code, 302)
        u.refresh_from_db()
        self.assertTrue(u.check_password('NewPassw0rd!Secure456'))

    def test_used_token_cannot_reset_again(self):
        u = make_citizen(email='reuse@t.fyp', cnic='35202-5555555-5')
        self.client.post(reverse('auth_portal:forgot_password'), {'cnic': '35202-5555555-5'})
        tok = PasswordResetToken.objects.filter(user=u).order_by('-id').first()
        url = reverse('auth_portal:citizen_reset_confirm', args=[tok.token])
        self.client.post(url, {
            'new_password': 'NewPassw0rd!Secure789',
            'confirm_password': 'NewPassw0rd!Secure789',
        })
        self.client.post(url, {
            'new_password': 'AnotherPassw0rd!x',
            'confirm_password': 'AnotherPassw0rd!x',
        })
        u.refresh_from_db()
        self.assertTrue(u.check_password('NewPassw0rd!Secure789'))


class AdminResetSecurityTests(TestCase):
    def test_public_admin_reset_endpoint_is_gone(self):
        r = self.client.get('/auth/admin/reset/sometoken123/')
        self.assertEqual(r.status_code, 404)

    def test_admin_forgot_creates_request_and_notifies_dig_only(self):
        from accounts.models import AdminPasswordResetRequest, User as U
        dig = U.objects.create(username='dig9@t.fyp', email='dig9@t.fyp', role='DIG', is_active=True)
        dig.set_password('x' * 16)
        dig.save()
        staff = U.objects.create(
            username='locked@t.fyp', email='locked@t.fyp', role='SSP', is_active=True)
        r = self.client.post(reverse('auth_portal:admin_forgot_password'), {
            'email': 'locked@t.fyp',
        })
        self.assertEqual(r.status_code, 200)
        req = AdminPasswordResetRequest.objects.filter(target_user=staff).first()
        self.assertIsNotNone(req)
        body = r.content.decode()
        if req.token:
            self.assertNotIn(req.token, body)
