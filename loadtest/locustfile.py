"""Load profile for the Safe Cities Project public portal.

Simulates Pakistan-wide traffic on the public e-challan flow:
anonymous home visits, public challan searches, static assets and
staff logins. Run headless against a production-style server:

    locust -f loadtest/locustfile.py --headless \\
        -u 200 -r 20 -t 2m --host http://127.0.0.1:8010 \\
        --csv loadtest/results/run
"""
import os
import random
import re

from locust import HttpUser, between, task


PLATES = ['LEA-1001', 'ISB-4567', 'KHI-2345', 'ACR-59', 'LEA-1234', 'RWP-7788']
CNICS = ['35202-1234567-1', '61101-2233445-2', '42201-9988776-3']

# Staff credentials are env-overridable. Defaults match the long-lived demo
# database convention (also used by scripts/push_audit.py). The previous
# revision pointed at officer@safecities.project - an account that does not
# exist in this database - so its "staff" traffic silently exercised the
# login page only and the 302s were counted as success. The corrected profile
# fails loudly if the login POST does not redirect.
STAFF_USERNAME = os.environ.get('LOADTEST_STAFF_USERNAME', 'officer@safecity.fyp')
STAFF_PASSWORD = os.environ.get('LOADTEST_STAFF_PASSWORD', 'Test@2026')


class PublicVisitor(HttpUser):
    """Anonymous citizen checking an e-challan (75% of traffic)."""
    weight = 3
    wait_time = between(1, 4)

    @task(6)
    def open_home(self):
        self.client.get('/', name='GET / (home)')

    @task(3)
    def search_challan(self):
        plate = random.choice(PLATES)
        cnic = random.choice(CNICS)
        self.client.get(
            '/?plate=%s&cnic=%s' % (plate, cnic),
            name='GET /?plate&cnic (search)')

    @task(1)
    def static_assets(self):
        self.client.get('/static/css/public-shell.css', name='GET /static css')
        self.client.get('/static/js/pages/public-ads.js', name='GET /static js')


class StaffUser(HttpUser):
    """Officer logged into their portal (25% of traffic)."""
    weight = 1
    wait_time = between(3, 9)

    def on_start(self):
        page = self.client.get('/auth/admin/login/', name='GET /auth/admin/login/')
        token = ''
        m = re.search(r"name='csrfmiddlewaretoken' value='([^']+)'", page.text)
        if not m:
            m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.text)
        if m:
            token = m.group(1)
        with self.client.post(
            '/auth/admin/login/',
            {'username': STAFF_USERNAME,
             'password': STAFF_PASSWORD,
             'csrfmiddlewaretoken': token},
            name='POST /auth/admin/login/', catch_response=True) as r:
            # requests follows redirects by default, so a SUCCESSFUL login
            # ends on the officer dashboard (200). A REJECTED login re-renders
            # the form (200, still contains the password input). 4xx/5xx are
            # surfaced by locust itself.
            if r.status_code == 200 and 'type="password"' in r.text:
                r.failure('staff login failed (login form re-rendered)')
            elif r.status_code != 200:
                r.failure('staff login failed (HTTP %s)' % r.status_code)

    @task(4)
    def portal_dashboard(self):
        self.client.get('/portal/officer/', name='GET /portal/officer/')

    @task(1)
    def notifications_feed(self):
        self.client.get('/auth/notifications/feed/', name='GET /auth/notifications/feed/')
