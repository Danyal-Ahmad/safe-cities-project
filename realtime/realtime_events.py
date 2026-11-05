"""Realtime push service for the SAFE CITIES PROJECT e-challan platform.

Thin Socket.IO layer that pushes new detections, challans and portal
notifications to the role dashboards the moment they happen, so portals no
longer need to poll JSON endpoints for updates.

    detections/pipeline.py (sync Django code)
        -> emit_detection_event(detection, action)
        -> _schedule_emit() hops onto the ASGI event loop
        -> sio.emit('detection:new', payload, room='portal:<role>')

The server is mounted by wrongway_system/asgi.py at ``/ws/socket.io`` and
must run in a SINGLE process (uvicorn --workers 1) so in-process emits
reach connected clients. See docs/REALTIME.md for the multi-worker Redis
message-queue option.

Security note: the Socket.IO handshake does not carry the Django session,
so the role string supplied by the client is used ONLY to route the socket
into a role room. Events pushed on this channel carry non-sensitive fields
only (ids, plates, statuses, coarse confidence). Full evidence packages and
personal data stay behind the authenticated portal HTTP views.
"""
from __future__ import annotations

import asyncio
import logging
import threading

import socketio
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('wrongway.realtime')


STAFF_ROOMS = (
    'portal:dig',
    'portal:ssp',
    'portal:supervisor',
    'portal:officer',
    'portal:audit',
    'portal:it',
)

CHALLAN_ROOMS = STAFF_ROOMS + ('portal:citizen',)

ROLE_ROOMS = {
    'DIG': 'portal:dig',
    'SSP': 'portal:ssp',
    'SUPERVISOR': 'portal:supervisor',
    'SUPV': 'portal:supervisor',
    'OFFICER': 'portal:officer',
    'AUDIT': 'portal:audit',
    'IT': 'portal:it',
    'IT_SUPPORT': 'portal:it',
    'CITIZEN': 'portal:citizen',
    'USER': 'portal:citizen',
}

STAFF_ROLE_KEYS = frozenset({
    'DIG', 'SSP', 'SUPERVISOR', 'SUPV', 'OFFICER', 'AUDIT', 'IT', 'IT_SUPPORT',
})

AUDIENCE_ROOMS = {
    'all': ('everyone',),
    'everyone': ('everyone',),
    'staff': ('staff',),
    'dig': ('portal:dig',),
    'ssp': ('portal:ssp',),
    'supervisor': ('portal:supervisor',),
    'supv': ('portal:supervisor',),
    'officer': ('portal:officer',),
    'audit': ('portal:audit',),
    'it': ('portal:it',),
    'citizen': ('portal:citizen',),
    'citizens': ('portal:citizen',),
}


def _cors_allowed_origins():
    """Permissive in DEBUG, strict same-origin when DEBUG=False.

    python-socketio maps ``None`` to "only the request's own origin is
    allowed" (engine.io derives the allowed origin from the Host header),
    which is the strict same-origin behaviour required in production.
    """
    if getattr(settings, 'DEBUG', False):
        return '*'
    return None


sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=_cors_allowed_origins(),
    logger=False,
    engineio_logger=False,
)


_event_loop = None
_loop_lock = threading.Lock()


def _capture_event_loop():
    """Remember the running ASGI event loop so sync code can emit."""
    global _event_loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    with _loop_lock:
        _event_loop = loop
    return loop


def _get_event_loop():
    with _loop_lock:
        return _event_loop


def on_asgi_startup():
    """ASGI lifespan hook: capture the event loop for in-process emitters.

    Wired in wrongway_system/asgi.py via ``socketio.ASGIApp(on_startup=...)``.
    """
    loop = _capture_event_loop()
    logger.info(
        'realtime push layer started (event loop %s, cors=%s)',
        'captured' if loop is not None else 'NOT captured',
        '*' if getattr(settings, 'DEBUG', False) else 'same-origin',
    )


async def _emit_to_rooms(event, payload, rooms):
    """Coroutine that performs the actual room-by-room emit."""
    for room in rooms:
        try:
            await sio.emit(event, payload, room=room)
        except Exception:
            logger.exception('realtime emit failed: %s -> %s', event, room)


def _schedule_emit(event, payload, rooms):
    """Fire-and-forget emit, callable from ANY thread (sync Django included).

    Returns True when the emit was scheduled, False when it was skipped
    (no ASGI event loop yet, e.g. plain WSGI/runserver deployments).
    Never raises.
    """
    try:
        loop = _get_event_loop()
        if loop is None or loop.is_closed():
            logger.debug(
                'realtime emit skipped, ASGI event loop not running: %s', event,
            )
            return False
        coro = _emit_to_rooms(event, payload, tuple(rooms))
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            asyncio.ensure_future(coro)
        else:
            asyncio.run_coroutine_threadsafe(coro, loop)
        return True
    except Exception:
        logger.exception('realtime emit scheduling failed: %s', event)
        return False




@sio.event
async def connect(sid, environ, auth=None):
    """Join the socket into its role room based on the auth dict.

    The Socket.IO handshake has no Django session, so the role is accepted
    as a routing hint only; pushed payloads stay non-sensitive (see the
    module docstring). Unknown or missing roles join 'everyone' only.
    """
    _capture_event_loop()

    role = ''
    if isinstance(auth, dict):
        role = str(auth.get('role') or '').strip().upper()
    elif isinstance(auth, str):
        role = auth.strip().upper()

    joined = ['everyone']
    await sio.enter_room(sid, 'everyone')

    room = ROLE_ROOMS.get(role)
    if room:
        await sio.enter_room(sid, room)
        joined.append(room)
        if role in STAFF_ROLE_KEYS:
            await sio.enter_room(sid, 'staff')
            joined.append('staff')

    logger.info(
        'socket %s connected (role=%s, rooms=%s)', sid, role or 'guest',
        ','.join(joined),
    )


@sio.event
async def disconnect(sid):
    logger.info('socket %s disconnected', sid)




def _detection_payload(detection, action):
    try:
        camera = detection.camera
    except Exception:
        camera = None
    camera_data = None
    if camera is not None:
        camera_data = {
            'id': getattr(camera, 'camera_id', None) or camera.pk,
            'location': getattr(camera, 'location', '') or '',
        }

    checks = getattr(detection, 'evidence_checks', None) or []
    try:
        passed = sum(1 for c in checks if isinstance(c, dict) and c.get('passed'))
    except TypeError:
        passed = 0

    confidence = getattr(detection, 'ai_confidence', None)
    created_at = getattr(detection, 'created_at', None) or timezone.now()
    return {
        'id': getattr(detection, 'pk', None),
        'plate': (getattr(detection, 'ai_plate_text', None) or '').upper(),
        'status': getattr(detection, 'status', None),
        'action': action,
        'camera': camera_data,
        'confidence': round(float(confidence), 3) if confidence is not None else None,
        'created_at': created_at.isoformat(),
        'evidence_passed': passed,
        'evidence_total': 5,
    }


def _challan_payload(challan, event):
    try:
        amount = float(getattr(challan, 'fine_amount', 0) or 0)
    except (TypeError, ValueError):
        amount = 0.0
    issue_date = getattr(challan, 'issue_date', None)
    updated_at = getattr(challan, 'updated_at', None) or timezone.now()
    return {
        'id': getattr(challan, 'pk', None),
        'ticket_no': getattr(challan, 'ticket_no', None),
        'plate': getattr(challan, 'plate_number', None) or '',
        'status': getattr(challan, 'payment_status', None),
        'event': str(event or ''),
        'amount': amount,
        'issue_date': issue_date.isoformat() if issue_date else None,
        'updated_at': updated_at.isoformat(),
    }


def _audiences_to_rooms(audiences):
    """Normalize the audiences argument to a de-duplicated room tuple."""
    if audiences is None:
        audiences = ()
    elif isinstance(audiences, str):
        audiences = (audiences,)
    rooms = []
    for audience in audiences:
        for room in AUDIENCE_ROOMS.get(str(audience).strip().lower(), ()):
            if room not in rooms:
                rooms.append(room)
    return tuple(rooms) or ('staff',)




def emit_detection_event(detection, action):
    """Push a pipeline detection outcome to the portal dashboards.

    Called by detections/pipeline.py as::

        from realtime.realtime_events import emit_detection_event
        emit_detection_event(detection, action)

    with action in {'challan_issued', 'queued_review', 'ignored'}.
    Only 'challan_issued' and 'queued_review' are pushed to the staff
    rooms; 'ignored' (auto-rejected false positives) is logged and skipped.
    Failures are swallowed: realtime problems must never break the
    enforcement pipeline.
    """
    try:
        action = str(action or '')
        if action not in ('challan_issued', 'queued_review'):
            logger.debug(
                'detection %s action=%s not pushed to portals',
                getattr(detection, 'pk', None), action or '(none)',
            )
            return False
        payload = _detection_payload(detection, action)
        scheduled = _schedule_emit('detection:new', payload, STAFF_ROOMS)
        if scheduled:
            logger.info(
                'detection:new pushed (id=%s plate=%s action=%s evidence=%s/5)',
                payload['id'], payload['plate'] or '-', action,
                payload['evidence_passed'],
            )
        return scheduled
    except Exception:
        logger.exception('emit_detection_event failed (action=%s)', action)
        return False


def emit_portal_notification(title, message, severity='info', audiences=('staff',)):
    """Push a portal notification toast to the mapped rooms.

    audiences: single string or iterable of audience names, e.g.
    'all', 'staff', 'dig', 'ssp', 'supervisor', 'officer', 'audit', 'it',
    'citizen'. Unknown names are ignored; when nothing valid remains the
    notification falls back to the 'staff' room. Defaults to 'staff'.
    """
    try:
        rooms = _audiences_to_rooms(audiences)
        payload = {
            'title': str(title or 'Notification'),
            'message': str(message or ''),
            'severity': str(severity or 'info').lower(),
            'created_at': timezone.now().isoformat(),
        }
        scheduled = _schedule_emit('portal:notification', payload, rooms)
        if scheduled:
            logger.info(
                'portal:notification pushed (severity=%s rooms=%s)',
                payload['severity'], ','.join(rooms),
            )
        return scheduled
    except Exception:
        logger.exception('emit_portal_notification failed')
        return False


def emit_challan_event(challan, event):
    """Push a challan lifecycle event (issued/paid/voided/...) to portals.

    Emitted as 'challan:updated' to every staff room plus 'portal:citizen'.
    Payload is non-sensitive (ticket number, plate, status, amount).
    """
    try:
        payload = _challan_payload(challan, event)
        scheduled = _schedule_emit('challan:updated', payload, CHALLAN_ROOMS)
        if scheduled:
            logger.info(
                'challan:updated pushed (ticket=%s event=%s status=%s)',
                payload['ticket_no'], payload['event'], payload['status'],
            )
        return scheduled
    except Exception:
        logger.exception('emit_challan_event failed')
        return False
