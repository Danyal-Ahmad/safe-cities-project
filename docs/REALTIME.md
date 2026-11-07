# Realtime push (Socket.IO) - SAFE CITIES PROJECT

Zero-polling portal updates: new detections, challans and alerts are pushed to connected dashboards the moment they happen.

## Architecture

```
detections/pipeline.py (sync) -> emit_detection_event(detection, action)
  -> realtime/realtime_events.py hops onto the ASGI event loop (thread-safe)
  -> socketio.ASGIApp at /ws/socket.io (wrongway_system/asgi.py)
  -> rooms: portal:dig|ssp|supervisor|officer|audit|it|citizen, staff, everyone
  -> static/js/realtime-socket.js (client) -> toasts + DOM events
```

Server: python-socketio, `async_mode='asgi'`. CORS is `*` only when DEBUG=True; with DEBUG=False engine.io allows the request's own origin only (strict same-origin).

## How to enable

```bash
python launcher.py realtime        # uvicorn ASGI server, 1 worker
REALTIME=1 python launcher.py run  # same via environment
uvicorn wrongway_system.asgi:application --host 0.0.0.0 --port 8000 --workers 1 --log-level info
```

`--workers 1` is REQUIRED: the pipeline emits events in-process, so the Socket.IO server and the emitting code must share one process. Default `launcher.py run` (runserver/WSGI) is unchanged; emits are then safely skipped (logged at DEBUG, never raise).

Client: base.html loads `static/js/realtime-socket.js` and sets `window.SAFECITY_USER = {role}` (or `<body data-user-role>`). The script injects the socket.io 4.7.5 CDN client when `window.io` is missing, connects to `/ws/socket.io` with `auth: {role}`, and exposes `window.SafeCityRealtime = {socket, connected}`.

## Server-side API (never raises)

```python
from realtime.realtime_events import (emit_detection_event,
    emit_portal_notification, emit_challan_event)
emit_detection_event(detection, 'challan_issued'|'queued_review'|'ignored')
#    -> 'detection:new' to portal:dig/ssp/supervisor/officer/audit/it
emit_portal_notification(title, message, severity, audiences)
#    -> 'portal:notification'; audiences: 'all','staff','dig','ssp',
#       'supervisor','officer','audit','it','citizen' (default: staff)
emit_challan_event(challan, event)  # -> 'challan:updated' staff + citizen
```

Client DOM events for pages: `safecity:detection` (also toasted), `safecity:notification`, `safecity:challan`, `safecity:realtime-state` (connecting / connected / reconnecting / disconnected / unavailable) for status badges. The handshake carries no Django session: the role is a routing hint only and payloads are non-sensitive (ids, plates, statuses); full evidence stays behind the authenticated portal HTTP views.

## Scaling to multiple workers (documented, NOT implemented)

With more than one worker, in-process emits only reach clients connected to the same worker. Share one Socket.IO server across all workers and processes (camera worker included) with a Redis message queue:

```python
sio = socketio.AsyncServer(
    async_mode='asgi',
    client_manager=socketio.AsyncRedisManager('redis://localhost:6379/0'),
)
```

Then run any number of workers against the same Redis and emits fan out to all connected clients.
