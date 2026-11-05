from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()

DEMO_ACCOUNTS = [
    ('role', 'email', 'first', 'last', 'password'),
    ('SSP', 'ssp@safecities.project', 'Sana', 'Raza', 'Demo@SSP-2026secure'),
    ('SUPV', 'supervisor@safecities.project', 'Bilal', 'Ahmed', 'Demo@SUPV-2026secure'),
    ('OFFICER', 'officer@safecities.project', 'Adnan', 'Khan', 'Demo@OFFCR-2026secure'),
    ('AUDIT', 'audit@safecities.project', 'Farah', 'Nawaz', 'Demo@AUDT-2026secure'),
    ('IT', 'itsupport@safecities.project', 'Hamza', 'Sheikh', 'Demo@ITSP-2026secure'),
    ('USER', 'citizen@safecities.project', 'Danyal', 'Ahmad', 'Demo@CZN-2026secure'),
]


class Command(BaseCommand):
    help = (
        "Seed one demo account per role for development/demo runs. "
        "DEMO ONLY - never run in production."
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true',
                            help='Required confirmation flag')

    def handle(self, *args, **options):
        if not options.get('yes'):
            self.stdout.write(self.style.WARNING(
                "Refusing to run without --yes. Demo accounts use fixed passwords - "
                "development/demo only."))
            return
        created = []
        with transaction.atomic():
            for role, email, first, last, password in DEMO_ACCOUNTS[1:]:
                if User.objects.filter(email__iexact=email).exists():
                    continue
                user = User.objects.create(
                    username=email, email=email,
                    first_name=first, last_name=last,
                    role=role, is_active=True,
                )
                user.set_password(password)
                user.save()
                created.append(f"{role:8s} {email} / {password}")
        if created:
            for line in created:
                self.stdout.write(self.style.SUCCESS(line))
            self.stdout.write(self.style.WARNING(
                "Demo accounts with fixed passwords - development use only."))
        else:
            self.stdout.write("All demo accounts already exist.")
