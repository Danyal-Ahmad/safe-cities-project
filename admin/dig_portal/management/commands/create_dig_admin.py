from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import secrets

User = get_user_model()


class Command(BaseCommand):
    help = "Create the initial DIG super-admin account (run once after migrate)."

    def add_arguments(self, parser):
        parser.add_argument('--email', default=None)
        parser.add_argument('--password', default=None)
        parser.add_argument('--first-name', default='Safe City')

    def handle(self, *args, **options):
        email = (options.get('email') or 'dig@safecities.project').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(self.style.WARNING(f"DIG admin already exists: {email}"))
            return
        password = (options.get('password') or '').strip()
        generated = False
        if not password:
            password = secrets.token_urlsafe(16)
            generated = True
        user = User.objects.create(
            username=email,
            email=email,
            first_name=options.get('first_name') or 'Safe City',
            last_name='DIG Command',
            role=User.DIG,
            is_active=True,
        )
        user.set_password(password)
        user.save()
        from accounts.models import DigProfile
        DigProfile.objects.get_or_create(user=user)
        self.stdout.write(self.style.SUCCESS(f"DIG admin created: {email}"))
        if generated:
            self.stdout.write(self.style.NOTICE(f"Initial password (shown once): {password}"))
            self.stdout.write(self.style.NOTICE("Change it immediately after first sign-in."))
