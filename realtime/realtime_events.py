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
    loop = _capture_event_loop()
    logger.info(
        'realtime push layer started (event loop %s, cors=%s)',
        'captured' if loop is not None else 'NOT captured',
        '*' if getattr(settings, 'DEBUG', False) else 'same-origin',
    )


async def _emit_to_rooms(event, payload, rooms):
    for room in rooms:
        try:
            await sio.emit(event, payload, room=room)
        except Exception:
            logger.exception('realtime emit failed: %s -> %s', event, room)


def _schedule_emit(event, payload, rooms):
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

