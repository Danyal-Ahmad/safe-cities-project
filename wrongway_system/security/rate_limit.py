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
