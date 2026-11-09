from __future__ import annotations

import os
import shutil
import smtplib
import socket
import ssl
import time
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

SECRET_HINTS = ('PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'SALT')

CATEGORIES = [
    {
        'key': 'database',
        'title': 'PostgreSQL Database',
        'icon': 'bi-database-fill-gear',
        'keys': ['PG_DB', 'PG_USER', 'PG_PASSWORD', 'PG_HOST', 'PG_PORT'],
    },
    {
        'key': 'smtp',
        'title': 'SMTP / Email Delivery',
        'icon': 'bi-envelope-at-fill',
        'keys': [
            'EMAIL_NOTIFICATIONS_ENABLED', 'EMAIL_HOST', 'EMAIL_PORT',
            'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'EMAIL_USE_TLS',
            'DEFAULT_FROM_EMAIL',
        ],
    },
    {
        'key': 'security',
        'title': 'Security & Runtime',
        'icon': 'bi-shield-lock-fill',
        'keys': [
            'DEBUG', 'SECRET_KEY', 'ALLOWED_HOSTS', 'SSL_REDIRECT',
            'CSRF_TRUSTED_ORIGINS',
        ],
    },
    {
        'key': 'lockout',
        'title': 'Account Protection',
        'icon': 'bi-person-fill-lock',
        'keys': ['ACCOUNT_LOCKOUT_THRESHOLD', 'ACCOUNT_LOCKOUT_DURATION'],
    },
]

EFFECTIVE_FALLBACKS = {
    'PG_DB': lambda: getattr(settings, 'PG_DB', ''),
    'PG_USER': lambda: getattr(settings, 'PG_USER', ''),
    'PG_PASSWORD': lambda: getattr(settings, 'PG_PASSWORD', ''),
    'PG_HOST': lambda: getattr(settings, 'PG_HOST', ''),
    'PG_PORT': lambda: getattr(settings, 'PG_PORT', ''),
    'EMAIL_NOTIFICATIONS_ENABLED': lambda: 'True' if settings.EMAIL_NOTIFICATIONS_ENABLED else 'False',
    'EMAIL_HOST': lambda: getattr(settings, 'EMAIL_HOST', '') if settings.EMAIL_NOTIFICATIONS_ENABLED else '',
    'EMAIL_PORT': lambda: str(getattr(settings, 'EMAIL_PORT', 587)) if settings.EMAIL_NOTIFICATIONS_ENABLED else '',
    'EMAIL_HOST_USER': lambda: getattr(settings, 'EMAIL_HOST_USER', '') if settings.EMAIL_NOTIFICATIONS_ENABLED else '',
    'EMAIL_HOST_PASSWORD': lambda: getattr(settings, 'EMAIL_HOST_PASSWORD', '') if settings.EMAIL_NOTIFICATIONS_ENABLED else '',
    'EMAIL_USE_TLS': lambda: 'True' if getattr(settings, 'EMAIL_USE_TLS', True) else 'False',
    'DEFAULT_FROM_EMAIL': lambda: getattr(settings, 'DEFAULT_FROM_EMAIL', ''),
    'DEBUG': lambda: 'True' if settings.DEBUG else 'False',
    'SECRET_KEY': lambda: '***loaded***' if os.environ.get('SECRET_KEY') else '',
    'ALLOWED_HOSTS': lambda: ','.join(settings.ALLOWED_HOSTS),
    'SSL_REDIRECT': lambda: 'True' if getattr(settings, 'SECURE_SSL_REDIRECT', False) else 'False',
    'CSRF_TRUSTED_ORIGINS': lambda: ','.join(getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])),
    'ACCOUNT_LOCKOUT_THRESHOLD': lambda: str(getattr(settings, 'ACCOUNT_LOCKOUT_THRESHOLD', 5)),
    'ACCOUNT_LOCKOUT_DURATION': lambda: str(getattr(settings, 'ACCOUNT_LOCKOUT_DURATION', 900)),
}


def read_env_file():
    path = settings.BASE_DIR / '.env'
    if not path.is_file():
        return path, {}
    entries = {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        entries[key.strip()] = value.strip().strip('"').strip("'")
    return path, entries


def mask_value(key, value):
    if not value:
        return ''
    if any(hint in key.upper() for hint in SECRET_HINTS):
        if len(value) <= 4:
            return '****'
        return value[:2] + '*' * min(12, len(value) - 2)
    return value


def build_catalog(env_entries):
    catalog = []
    for category in CATEGORIES:
        rows = []
        for key in category['keys']:
            in_file = key in env_entries
            raw = env_entries.get(key, '')
            if not in_file:
                try:
                    effective = EFFECTIVE_FALLBACKS.get(key, lambda: '')() or ''
                except Exception:
                    effective = ''
            else:
                effective = raw
            rows.append({
                'key': key,
                'in_file': in_file,
                'masked': mask_value(key, effective),
                'empty': not effective,
            })
        catalog.append({**category, 'rows': rows})
    return catalog


def _result(name, label, status, latency_ms, detail):
    return {
        'name': name,
        'label': label,
        'status': status,
        'latency_ms': round(latency_ms, 1),
        'detail': detail,
    }


def _env_or_setting(env, env_key, setting_attr, default=''):
    if env_key in env and env[env_key]:
        return env[env_key]
    return str(getattr(settings, setting_attr, default) or default)


def test_database(env):
    import psycopg2

    db = _env_or_setting(env, 'PG_DB', 'PG_DB', 'safecity')
    user = _env_or_setting(env, 'PG_USER', 'PG_USER', 'postgres')
    password = _env_or_setting(env, 'PG_PASSWORD', 'PG_PASSWORD', '')
    host = _env_or_setting(env, 'PG_HOST', 'PG_HOST', '127.0.0.1')
    port = _env_or_setting(env, 'PG_PORT', 'PG_PORT', '5432')
    started = time.perf_counter()
    try:
        conn = psycopg2.connect(
            dbname=db, user=user, password=password,
            host=host, port=port, connect_timeout=6,
        )
        with conn.cursor() as cur:
            cur.execute('SELECT version()')
            version = (cur.fetchone()[0] or '').split(' on ')[0]
            cur.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            tables = cur.fetchone()[0]
        conn.close()
        latency = (time.perf_counter() - started) * 1000
        return _result(
            'database', 'PostgreSQL', 'ok', latency,
            f'{version} - database "{db}" @ {host}:{port}, {tables} tables in public schema',
        )
    except Exception as exc:
        latency = (time.perf_counter() - started) * 1000
        return _result(
            'database', 'PostgreSQL', 'fail', latency,
            f'Connection to {host}:{port}/{db} failed: {exc}',
        )


def test_smtp(env):
    host = env.get('EMAIL_HOST') or ''
    notifications_enabled = str(
        env.get('EMAIL_NOTIFICATIONS_ENABLED', '')
    ).strip().lower() in ('1', 'true', 'yes', 'on')
    if not host:
        if not notifications_enabled and not settings.EMAIL_NOTIFICATIONS_ENABLED:
            backend = 'console' if 'console' in settings.EMAIL_BACKEND else 'smtp'
            return _result(
                'smtp', 'SMTP', 'warn', 0,
                'SMTP is not configured in .env (no EMAIL_HOST) - email delivery currently uses the '
                f'{backend} backend. Set EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER and '
                'EMAIL_HOST_PASSWORD in .env to enable real delivery.',
            )
        host = getattr(settings, 'EMAIL_HOST', '') or 'localhost'
    try:
        port = int(env.get('EMAIL_PORT') or getattr(settings, 'EMAIL_PORT', 587) or 587)
    except (TypeError, ValueError):
        port = 587
    user = env.get('EMAIL_HOST_USER') or getattr(settings, 'EMAIL_HOST_USER', '') or ''
    password = env.get('EMAIL_HOST_PASSWORD') or getattr(settings, 'EMAIL_HOST_PASSWORD', '') or ''
    use_tls = str(env.get('EMAIL_USE_TLS', 'True')).strip().lower() not in ('0', 'false', 'no')
    started = time.perf_counter()
    steps = []
    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            code, greeting = smtp.ehlo()
            steps.append(f'EHLO {code}')
            if use_tls and smtp.has_extn('starttls'):
                context = ssl.create_default_context()
                smtp.starttls(context=context)
                smtp.ehlo()
                steps.append('STARTTLS')
            if user:
                smtp.login(user, password)
                steps.append('AUTH OK')
            else:
                steps.append('AUTH skipped (no credentials)')
            smtp.noop()
        latency = (time.perf_counter() - started) * 1000
        return _result(
            'smtp', 'SMTP', 'ok', latency,
            f'{host}:{port} live session - ' + ', '.join(steps),
        )
    except smtplib.SMTPAuthenticationError as exc:
        latency = (time.perf_counter() - started) * 1000
        return _result(
            'smtp', 'SMTP', 'fail', latency,
            f'{host}:{port} rejected credentials: {exc}',
        )
    except (smtplib.SMTPException, socket.error, OSError) as exc:
        latency = (time.perf_counter() - started) * 1000
        return _result(
            'smtp', 'SMTP', 'fail', latency,
            f'{host}:{port} connection failed: {exc}',
        )


def test_cache(_env):
    started = time.perf_counter()
    try:
        probe_key = 'it_env_probe'
        cache.set(probe_key, 'ok', 30)
        value = cache.get(probe_key)
        cache.delete(probe_key)
        latency = (time.perf_counter() - started) * 1000
        if value != 'ok':
            return _result('cache', 'Cache', 'fail', latency, 'set/get round-trip returned an unexpected value')
        backend = settings.CACHES['default']['BACKEND'].rsplit('.', 1)[-1]
        return _result('cache', 'Cache', 'ok', latency, f'{backend} set/get/delete round-trip succeeded')
    except Exception as exc:
        latency = (time.perf_counter() - started) * 1000
        return _result('cache', 'Cache', 'fail', latency, f'Cache probe failed: {exc}')


def test_staticfiles(_env):
    started = time.perf_counter()
    root = settings.STATIC_ROOT
    manifest = Path(root) / 'staticfiles.json' if root else None
    if manifest and manifest.is_file():
        import json

        try:
            entries = len(json.loads(manifest.read_text(encoding='utf-8')).get('paths', {}))
        except (ValueError, OSError):
            entries = 0
        latency = (time.perf_counter() - started) * 1000
        if entries:
            return _result(
                'staticfiles', 'Static Assets', 'ok', latency,
                f'{entries} hashed assets collected under {root.name}/ (WhiteNoise manifest present)',
            )
        return _result('staticfiles', 'Static Assets', 'warn', latency, 'Manifest exists but lists no files - run collectstatic')
    latency = (time.perf_counter() - started) * 1000
    return _result(
        'staticfiles', 'Static Assets', 'warn', latency,
        'No WhiteNoise manifest found - run: python manage.py collectstatic',
    )


def test_ai_models(_env):
    started = time.perf_counter()
    models = []
    for attr in ('PLATE_DETECTOR_MODEL', 'SIDE_CLASSIFIER_MODEL'):
        path = getattr(settings, attr, None)
        if path and Path(path).is_file():
            models.append(f'{Path(path).name} ({Path(path).stat().st_size / 1048576:.1f} MB)')
    latency = (time.perf_counter() - started) * 1000
    if len(models) == 2:
        return _result('ai_models', 'AI Models', 'ok', latency, ' + '.join(models))
    return _result(
        'ai_models', 'AI Models', 'fail', latency,
        f'{len(models)}/2 ONNX models found under ai_models/ - detection pipeline degraded',
    )


def test_storage(_env):
    started = time.perf_counter()
    usage = shutil.disk_usage(settings.BASE_DIR)
    free_gb = usage.free / (1024 ** 3)
    total_gb = usage.total / (1024 ** 3)
    used_pct = (usage.used / usage.total) * 100
    latency = (time.perf_counter() - started) * 1000
    status = 'ok' if free_gb > 5 else ('warn' if free_gb > 1 else 'fail')
    return _result(
        'storage', 'Disk Storage', status, latency,
        f'{free_gb:.1f} GB free of {total_gb:.1f} GB ({used_pct:.0f}% used)',
    )


def test_migrations(_env):
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    started = time.perf_counter()
    try:
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        latency = (time.perf_counter() - started) * 1000
        if plan:
            pending = ', '.join(f'{app}.{name}' for app, name in plan[:5])
            return _result('migrations', 'Schema Migrations', 'warn', latency, f'{len(plan)} unapplied: {pending}')
        return _result('migrations', 'Schema Migrations', 'ok', latency, 'All migrations applied - schema is up to date')
    except Exception as exc:
        latency = (time.perf_counter() - started) * 1000
        return _result('migrations', 'Schema Migrations', 'fail', latency, f'Migration state check failed: {exc}')


def run_all_tests(env_entries):
    return [
        test_database(env_entries),
        test_smtp(env_entries),
        test_cache(env_entries),
        test_staticfiles(env_entries),
        test_ai_models(env_entries),
        test_storage(env_entries),
        test_migrations(env_entries),
    ]
