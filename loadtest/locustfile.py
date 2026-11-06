"""Load profile for the Safe Cities Project public portal.

Simulates Pakistan-wide traffic on the public e-challan flow:
anonymous home visits, public challan searches, static assets and
staff logins. Run headless against a production-style server:

    locust -f loadtest/locustfile.py --headless \\
        -u 200 -r 20 -t 2m --host http://127.0.0.1:8010 \\
        --csv loadtest/results/run
"""
import random
import re

from locust import HttpUser, between, task


PLATES = ['LEA-1001', 'ISB-4567', 'KHI-2345', 'ACR-59', 'LEA-1234', 'RWP-7788']
CNICS = ['35202-1234567-1', '61101-2233445-2', '42201-9988776-3']


class PublicVisitor(HttpUser):
    """Anonymous citizen checking an e-challan (75% of traffic)."""
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
    """Staff logging into their portal (25% of traffic)."""
    wait_time = between(3, 9)

    def on_start(self):
        page = self.client.get('/auth/admin/login/', name='GET /auth/admin/login/')
        token = ''
        m = re.search(r"name='csrfmiddlewaretoken' value='([^']+)'", page.text)
        if not m:
            m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.text)
        if m:
            token = m.group(1)
        self.client.post(
            '/auth/admin/login/',
            {'username': 'officer@safecities.project',
             'password': 'SafeCities#2026Project',
             'csrfmiddlewaretoken': token},
            name='POST /auth/admin/login/')

    @task(4)
    def portal_dashboard(self):
        self.client.get('/portal/officer/', name='GET /portal/officer/')

    @task(1)
    def notifications_feed(self):
        self.client.get('/auth/notifications/feed/', name='GET /auth/notifications/feed/')
