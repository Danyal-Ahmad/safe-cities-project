import os

os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')

from wrongway_system.settings import *

_db = DATABASES['default'].copy()
_db['NAME'] = os.environ.get('PG_TEST_DB', 'SAFE_CITIES_PROJECT_TEST')
DATABASES = {'default': _db}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

RATELIMIT_ENABLE = False
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
MEDIA_ROOT = os.path.join(BASE_DIR, 'test_media')

