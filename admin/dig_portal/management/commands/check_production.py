from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Check production security and configuration readiness'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict', action='store_true',
            help='Exit with code 1 if any check fails',
        )

    def handle(self, *args, **options):
        results = []

        def ok(msg):
            results.append(('PASS', msg))
            self.stdout.write(self.style.SUCCESS(f'  PASS  {msg}'))

        def fail(msg):
            results.append(('FAIL', msg))
            self.stdout.write(self.style.ERROR(f'  FAIL  {msg}'))

        def warn(msg):
            results.append(('WARN', msg))
            self.stdout.write(self.style.WARNING(f'  WARN  {msg}'))

        self.stdout.write(self.style.MIGRATE_HEADING('\nSafeCity production readiness\n'))

        if settings.DEBUG:
            fail('DEBUG is True - set DEBUG=False in production .env')
        else:
            ok('DEBUG=False')

        sk = settings.SECRET_KEY or ''
        if sk.startswith('safe-cities-project-demo') or sk == 'test-secret-key-not-for-production-phase9':
            fail('SECRET_KEY is still the demo/test default - set a strong unique key')
        elif len(sk) < 40:
            warn('SECRET_KEY looks short (< 40 chars) - prefer 50+ random chars')
        else:
            ok('SECRET_KEY is set and not the demo default')

        hosts = list(settings.ALLOWED_HOSTS or [])
        if hosts == ['*'] or not hosts:
            fail('ALLOWED_HOSTS is * or empty - set explicit hostnames')
        else:
            ok(f'ALLOWED_HOSTS = {hosts}')

        engine = settings.DATABASES['default'].get('ENGINE', '')
        if 'postgresql' in engine or 'psycopg' in engine:
            ok('Database engine is PostgreSQL')
        else:
            warn(f'Database engine is {engine} (production expects PostgreSQL)')

        pg_pass = getattr(settings, 'PG_PASSWORD', '') or settings.DATABASES['default'].get('PASSWORD', '')
        if not pg_pass:
            warn('PG_PASSWORD / DB password is empty')
        else:
            ok('Database password is set')

        if not settings.DEBUG:
            if getattr(settings, 'SESSION_COOKIE_SECURE', False):
                ok('SESSION_COOKIE_SECURE=True')
            else:
                fail('SESSION_COOKIE_SECURE should be True when DEBUG=False')
            if getattr(settings, 'CSRF_COOKIE_SECURE', False):
                ok('CSRF_COOKIE_SECURE=True')
            else:
                fail('CSRF_COOKIE_SECURE should be True when DEBUG=False')
            if getattr(settings, 'SECURE_SSL_REDIRECT', False):
                ok('SECURE_SSL_REDIRECT=True')
            else:
                warn('SECURE_SSL_REDIRECT is False')
            hsts = getattr(settings, 'SECURE_HSTS_SECONDS', 0) or 0
            if hsts >= 31536000:
                ok(f'SECURE_HSTS_SECONDS={hsts}')
            else:
                warn(f'SECURE_HSTS_SECONDS={hsts} (prefer >= 31536000)')
        else:
            warn('Skipping HTTPS cookie checks while DEBUG=True')

        if getattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF', False):
            ok('SECURE_CONTENT_TYPE_NOSNIFF=True')
        else:
            fail('SECURE_CONTENT_TYPE_NOSNIFF should be True')
        if getattr(settings, 'X_FRAME_OPTIONS', '') == 'DENY':
            ok('X_FRAME_OPTIONS=DENY')
        else:
            warn(f'X_FRAME_OPTIONS={getattr(settings, "X_FRAME_OPTIONS", None)}')

        if getattr(settings, 'RATELIMIT_ENABLE', False):
            ok('RATELIMIT_ENABLE=True')
        else:
            warn('RATELIMIT_ENABLE is False')

        hashers = getattr(settings, 'PASSWORD_HASHERS', [])
        if hashers and 'argon2' in hashers[0].lower():
            ok('Primary password hasher is Argon2')
        else:
            warn(f'Primary hasher: {hashers[0] if hashers else "unknown"}')

        from pathlib import Path
        models_dir = Path(settings.BASE_DIR) / 'models'
        for name in ('NumberPlate_detection_model_int8.onnx', 'car_side_Classifier_model_int8.onnx'):
            if (models_dir / name).exists():
                ok(f'AI model present: {name}')
            else:
                warn(f'AI model missing: {name}')

        fails = sum(1 for s, _ in results if s == 'FAIL')
        warns = sum(1 for s, _ in results if s == 'WARN')
        passes = sum(1 for s, _ in results if s == 'PASS')
        self.stdout.write('')
        self.stdout.write(f'Summary: {passes} passed, {warns} warnings, {fails} failed')
        if fails and options['strict']:
            raise SystemExit(1)

