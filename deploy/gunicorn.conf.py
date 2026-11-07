import multiprocessing
import os

bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8000')
workers = int(os.environ.get('GUNICORN_WORKERS') or min(4, multiprocessing.cpu_count() * 2 + 1))
threads = int(os.environ.get('GUNICORN_THREADS') or 4)
worker_class = 'gthread'
timeout = int(os.environ.get('GUNICORN_TIMEOUT') or 60)
graceful_timeout = 30
keepalive = 5
max_requests = 1200
max_requests_jitter = 200

forwarded_allow_ips = os.environ.get('GUNICORN_FORWARDED_ALLOW_IPS', '*')
proxy_protocol = False
raw_env = [
    'DJANGO_SETTINGS_MODULE=wrongway_system.settings',
]

accesslog = os.environ.get('GUNICORN_ACCESS_LOG', 'logs/gunicorn-access.log')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', 'logs/gunicorn-error.log')
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
capture_output = True

preload_app = False
worker_tmp_dir = '/dev/shm'
