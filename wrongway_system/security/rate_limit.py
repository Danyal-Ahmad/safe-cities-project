"""In-memory sliding-window rate limiter for SAFE CITIES PROJECT.

Shared by:
  * wrongway_system.security.middleware.RateLimitMiddleware (login + portal POST)
  * cameras/views.py        (enroll / ingest / heartbeat API limits)
  * payments/webhook.py     (gateway webhook limit)
  * payments/views.py       (demo checkout limit)

The counters live per-process (thread-safe via ``_lock``). This matches the
existing project pattern: the locmem cache used by django_ratelimit has the
same single-process scope. For a multi-worker deployment move both to Redis
(see docs/SECURITY_AUDIT.md - residual risks).
"""
from __future__ import annotations

import time
import threading
from collections import defaultdict, deque
from typing import Deque, Dict

_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = defaultdict(deque)


def _client_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()[:64]
    return (request.META.get('REMOTE_ADDR') or 'unknown')[:64]


def is_rate_limited(request, scope: str, limit: int = 30, window: int = 60) -> bool:
    """Consume one slot from the ``scope`` bucket for the client IP.

    Returns True when the request EXCEEDS ``limit`` events per ``window``
    seconds (the offending request is NOT counted - the bucket is full).
    """
    key = f'{scope}:{_client_ip(request)}'
    now = time.time()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


def rate_limit_response(request=None):
    """429 response used by every limiter in this project.

    ``request=None`` keeps the historic call signature working; when a
    request is supplied the body is content-negotiated:

    * API paths (``/api/…``) get a JSON body - cameras and gateways are
      machines, JSON is what their clients parse.
    * Everything else renders the shared error page template, so browsers
      see the standard SAFE CITIES error page instead of a bare string.

    Both variants carry a ``Retry-After: 60`` header.
    """
    from django.http import HttpResponse

    if request is not None and (request.path or '').startswith('/api/'):
        return HttpResponse(
            '{"ok": false, "error": "rate_limited", "retry_after": 60}',
            status=429,
            content_type='application/json',
            headers={'Retry-After': '60'},
        )

    if request is None:
        return HttpResponse(
            'Too many requests. Please wait and try again.',
            status=429,
            content_type='text/plain; charset=utf-8',
        )

    from django.shortcuts import render
    return render(
        request,
        'errors/error_page.html',
        {
            'code': 429,
            'title': 'Too Many Requests',
            'message': (
                'You are sending requests too quickly. Please wait about a '
                'minute and try again. This limit protects the service '
                'against abuse and overload.'
            ),
        },
        status=429,
    )
