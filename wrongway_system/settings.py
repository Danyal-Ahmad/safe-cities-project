import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

_env_path = BASE_DIR / ".env"
if _env_path.is_file():
    try:
        with open(_env_path, encoding="utf-8") as _f:
            for _raw in _f:
                _line = _raw.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _k, _, _v = _line.partition("=")
                _k, _v = _k.strip(), _v.strip()
                if len(_v) >= 2 and _v[0] in ("\"", "'") and _v[-1] == _v[0]:
                    _v = _v[1:-1]
                if _k and _k not in os.environ:
                    os.environ[_k] = _v
    except OSError:
        pass


def _env_bool(name, default=False):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ('1', 'true', 'yes', 'on', 'y', 't')


def _env_int(name, default=0):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_list(name, default):
    v = os.environ.get(name)
    if not v:
        return default
    return [x.strip() for x in v.split(',') if x.strip()]


SECRET_KEY = os.environ.get('SECRET_KEY', 'safe-cities-project-demo-CHANGE-THIS-IN-PRODUCTION-2026')
DEBUG = _env_bool('DEBUG', True)
ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', ['*'])

if not DEBUG and SECRET_KEY.startswith('safe-cities-project-demo'):
    raise SystemExit(
        "[SafeCity] SECURITY: Set a strong SECRET_KEY in .env before running with DEBUG=False."
    )
if not DEBUG and ALLOWED_HOSTS == ['*']:
    raise SystemExit(
        "[SafeCity] SECURITY: Set ALLOWED_HOSTS in .env (not *) when DEBUG=False."
    )

PG_DB = os.environ.get('PG_DB', 'SAFE_CITY_FYP')
PG_USER = os.environ.get('PG_USER', 'postgres')
PG_PASSWORD = os.environ.get('PG_PASSWORD', 'Admin@2026')
PG_HOST = os.environ.get('PG_HOST', '127.0.0.1')
PG_PORT = os.environ.get('PG_PORT', '5432')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'rest_framework',
    'django_ratelimit',

    'accounts', 'cameras', 'detections', 'challans', 'appeals',
    'realtime', 'video_processor',
    'integrations', 'payments',

    'auth_portal',

    'admin.dig_portal',
    'admin.ssp_portal',
    'admin.supervisor_portal',
    'admin.officer_portal',
    'admin.audit_portal',
    'admin.it_support_portal',
    'citizen.citizen_portal',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'wrongway_system.dev_static_cache.DevStaticNoCacheMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'admin.dig_portal.middleware.AuditLogMiddleware',
    'admin.dig_portal.middleware.AccountLockoutMiddleware',
    'admin.dig_portal.middleware.SecurityHeadersMiddleware',
    'admin.dig_portal.middleware.PortalIsolationMiddleware',
    'wrongway_system.security.middleware.RateLimitMiddleware',
    'wrongway_system.security.middleware.RequestSizeLimitMiddleware',
]

ROOT_URLCONF = 'wrongway_system.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
                'admin.dig_portal.context_processors.integration_mode',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'admin.dig_portal.context_processors.system_settings',
        'admin.dig_portal.context_processors.active_alerts',
        'admin.dig_portal.context_processors.ads_delivery',
        'admin.dig_portal.context_processors.sidebar_badge_counts',
        'admin.dig_portal.context_processors.user_notifications',
        'admin.dig_portal.context_processors.portal_namespace',
    ]},
}]

WSGI_APPLICATION = 'wrongway_system.wsgi.application'

def _pg_available(db_name, user, password, host, port):
    import socket
    try:
        s = socket.create_connection((host, int(port)), timeout=2)
        s.close()
        return True
    except (OSError, ValueError):
        return False


if not _pg_available(PG_DB, PG_USER, PG_PASSWORD, PG_HOST, PG_PORT):
    import sys
    print(
        f"[SafeCity] ERROR: PostgreSQL is required but not reachable at "
        f"{PG_HOST}:{PG_PORT}. "
        f"Start PostgreSQL, verify PG_HOST/PG_PORT/PG_USER/PG_PASSWORD in "
        f".env in project root (see .env.example), and try again.",
        file=sys.stderr,
    )
    raise SystemExit(1)

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': PG_DB,
    'USER': PG_USER,
    'PASSWORD': PG_PASSWORD,
    'HOST': PG_HOST,
    'PORT': PG_PORT,
    'OPTIONS': {'connect_timeout': 30},
    'CONN_MAX_AGE': 60,
    'CONN_HEALTH_CHECKS': True,
}}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

WHITENOISE_MAX_AGE = 0 if DEBUG else 60
WHITENOISE_IMMUTABLE_FILE_MAX_AGE = 31536000
WHITENOISE_IMMUTABLE_FILE_TEST = r'\.[0-9a-f]{12}\.'

try:
    from whitenoise.storage import CompressedManifestStaticFilesStorage as _WNBase

    class _GracefulManifestStaticFilesStorage(_WNBase):

        manifest_strict = False

    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "wrongway_system.settings._GracefulManifestStaticFilesStorage",
        },
    }
    del _WNBase
except ImportError:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'uploads'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

HANDLER400 = 'wrongway_system.views.custom_400'
HANDLER401 = 'wrongway_system.views.custom_401'
HANDLER402 = 'wrongway_system.views.custom_402'
HANDLER403 = 'wrongway_system.views.custom_403'
HANDLER404 = 'wrongway_system.views.custom_404'
HANDLER500 = 'wrongway_system.views.custom_500'
HANDLER501 = 'wrongway_system.views.custom_501'
HANDLER502 = 'wrongway_system.views.custom_502'
HANDLER503 = 'wrongway_system.views.custom_503'

AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/auth/admin/login/'
LOGIN_REDIRECT_URL = '/portal/'
LOGOUT_REDIRECT_URL = '/'

AUTHENTICATION_BACKENDS = [
    'accounts.backends.PhoneOrEmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

SESSION_COOKIE_AGE = 8 * 3600
SESSION_COOKIE_NAME = 'safecity_sessionid'
CSRF_COOKIE_NAME = 'safecity_csrftoken'
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_FAILURE_VIEW = 'admin.dig_portal.views.csrf_failure'

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    SECURE_SSL_REDIRECT = _env_bool('SSL_REDIRECT', True)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


if DEBUG:
    CSP_DEFAULT_SRC = ("'self'", "*")
    CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", "*")
    CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "*")
    CSP_FONT_SRC = ("'self'", "*", "data:")
    CSP_IMG_SRC = ("'self'", "*", "data:", "blob:")
    CSP_CONNECT_SRC = ("'self'", "*")
    CSP_FORM_ACTION = ("'self'", "http:", "https:")
else:
    CSP_DEFAULT_SRC = ("'self'",)
    CSP_SCRIPT_SRC = (
        "'self'", "'unsafe-inline'",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
        "https://unpkg.com",
        "https://cdn.tailwindcss.com",
        "https://fonts.googleapis.com",
    )
    CSP_STYLE_SRC = (
        "'self'", "'unsafe-inline'",
        "https://fonts.googleapis.com",
        "https://cdnjs.cloudflare.com",
        "https://unpkg.com",
        "https://cdn.jsdelivr.net",
    )
    CSP_FONT_SRC = (
        "'self'", "data:",
        "https://fonts.gstatic.com",
        "https://fonts.googleapis.com",
        "https://cdnjs.cloudflare.com",
    )
    CSP_IMG_SRC = ("'self'", "data:", "blob:", "https:")
    CSP_CONNECT_SRC = ("'self'",)
    CSP_FORM_ACTION = ("'self'", "https:")

CSP_OBJECT_SRC = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_FRAME_ANCESTORS_EMBED = ("'self'",)

EMAIL_NOTIFICATIONS_ENABLED = _env_bool('EMAIL_NOTIFICATIONS_ENABLED', False)
_EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
if EMAIL_NOTIFICATIONS_ENABLED and _EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = _EMAIL_HOST
    EMAIL_PORT = _env_int('EMAIL_PORT', 587)
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = _env_bool('EMAIL_USE_TLS', True)
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@safecities.project')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'noreply@wrongway.fyp'

MODELS_DIR = BASE_DIR / 'ai_models'
PLATE_DETECTOR_MODEL = MODELS_DIR / 'NumberPlate_detection_model_int8.onnx'
SIDE_CLASSIFIER_MODEL = MODELS_DIR / 'car_side_Classifier_model_int8.onnx'

RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = True
SILENCED_SYSTEM_CHECKS = ['django_ratelimit.E003', 'django_ratelimit.W001']

CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'safecity-cache',
    'OPTIONS': {'MAX_ENTRIES': 50000},
}}

ACCOUNT_LOCKOUT_THRESHOLD = _env_int('ACCOUNT_LOCKOUT_THRESHOLD', 5)
ACCOUNT_LOCKOUT_DURATION = _env_int('ACCOUNT_LOCKOUT_DURATION', 900)

LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{asctime}] {levelname} {name}:{lineno} {message}', 'style': '{'},
        'simple': {'format': '{levelname} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_DIR / 'safecity.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'safecity': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
        'django': {'handlers': ['console', 'file'], 'level': 'WARNING', 'propagate': False},
        'django.request': {'handlers': ['console', 'file'], 'level': 'ERROR', 'propagate': False},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
}

FILE_UPLOAD_MAX_MEMORY_SIZE = 200 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 200 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o644

