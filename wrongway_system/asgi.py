import os

import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wrongway_system.settings')

django.setup()


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
except Exception as exc:  
    import logging

    logging.getLogger('wrongway.realtime').warning(
        'Realtime push layer disabled, serving plain Django ASGI instead '
        '(%s: %s). Install python-socketio to enable it.',
        type(exc).__name__, exc,
    )
    application = django_asgi_app
