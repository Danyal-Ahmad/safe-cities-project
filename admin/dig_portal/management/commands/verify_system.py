from django.core.management.base import BaseCommand
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model

User = get_user_model()

CHECKS = [
    ('challans:home', 'Public home / search'),
    ('auth_portal:admin_login', 'Admin login'),
    ('auth_portal:citizen_login', 'Citizen login'),
    ('auth_portal:role_redirect', 'Role redirect'),
    ('dig:dashboard', 'DIG dashboard'),
    ('ssp_portal:dashboard', 'SSP dashboard'),
    ('supervisor_portal:dashboard', 'Supervisor dashboard'),
    ('officer_portal:review_queue', 'Officer queue'),
    ('audit_portal:dashboard', 'Audit dashboard'),
    ('it_support_portal:dashboard', 'IT dashboard'),
    ('citizen_portal:home', 'Citizen home'),
    ('dig:admin_list', 'DIG staff list'),
    ('dig:vehicle_search', 'Vehicle search'),
    ('dig:blacklist_list', 'Blacklist'),
]


class Command(BaseCommand):
    help = "Verify routes and seed data before runserver."

    def handle(self, *args, **options):
        ok = 0
        fail = 0
        self.stdout.write(self.style.MIGRATE_HEADING('=== URL checks ==='))
        for name, label in CHECKS:
            try:
                url = reverse(name)
                self.stdout.write(self.style.SUCCESS(f'  [OK] {label}: {url}'))
                ok += 1
            except NoReverseMatch as e:
                self.stdout.write(self.style.ERROR(f'  [FAIL] {label}: {e}'))
                fail += 1

        self.stdout.write(self.style.MIGRATE_HEADING('=== Data checks ==='))
        try:
            from challans.models import Challan
            from accounts.models import CitizenProfile
            n = Challan.objects.count()
            c = User.objects.filter(role=User.USER, cnic='35202-1234567-1').count()
            p = CitizenProfile.objects.count()
            roles = {r: User.objects.filter(role=r).count() for r in
                     [User.DIG, User.SSP, User.SUPERVISOR, User.OFFICER, User.AUDIT, User.IT_SUPPORT]}
            self.stdout.write(self.style.SUCCESS(f'  [OK] Challans: {n}'))
            self.stdout.write(self.style.SUCCESS(f'  [OK] Seed citizen CNIC 35202-1234567-1: {c}'))
            self.stdout.write(self.style.SUCCESS(f'  [OK] Citizen profiles: {p}'))
            for r, cnt in roles.items():
                style = self.style.SUCCESS if cnt else self.style.WARNING
                self.stdout.write(style(f'  [{"OK" if cnt else "WARN"}] Role {r}: {cnt}'))
            ok += 1
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [FAIL] data: {e}'))
            fail += 1

        self.stdout.write('')
        if fail:
            self.stdout.write(self.style.ERROR(f'Result: {ok} ok, {fail} FAILED'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Result: all {ok} checks passed'))

