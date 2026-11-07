"""ASGI entrypoint for the SAFE CITIES PROJECT e-challan platform.

Combines the Django ASGI application with the Socket.IO realtime push
layer (realtime/realtime_events.py) mounted at ``/ws/socket.io``:

    application = socketio.ASGIApp(sio, django_asgi_app,
                                   socketio_path='/ws/socket.io')

Start with a SINGLE worker so in-process emits reach connected clients:

    uvicorn wrongway_system.asgi:application --host 0.0.0.0 --port 8000 \
        --workers 1 --log-level info

(or: python launcher.py realtime).

If python-socketio is unavailable or the realtime layer fails to build,
``application`` falls back to the plain Django ASGI application so the
site keeps serving exactly as before.
"""
import os

import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wrongway_system.settings')

django.setup()

# Plain Django ASGI application (HTTP). Also the WSGI-compatible fallback
# exported as `application` when the realtime layer cannot be mounted.
django_asgi_app = get_asgi_application()

try:
    import socketio

    from realtime.realtime_events import on_asgi_startup, sio

    application = socketio.ASGIApp(
        sio,
        django_asgi_app,
        socketio_path='/ws/socket.io',
        on_startup=on_asgi_startup,
    )
except Exception as exc:  # keep the site alive without realtime push
    import logging

    logging.getLogger('wrongway.realtime').warning(
        'Realtime push layer disabled, serving plain Django ASGI instead '
        '(%s: %s). Install python-socketio to enable it.',
        type(exc).__name__, exc,
    )
    application = django_asgi_app
