"""Security middleware owned by the wrongway_system.security package.

RateLimitMiddleware  - coarse per-IP limits for auth + portal POST traffic
                       plus query-string malicious-pattern rejection.
RequestSizeLimitMiddleware - per-path body size caps (5 MB default, 50 MB
                       for upload/ingest paths).

Fine-grained per-endpoint API limits (cameras, payments, challan PDF) are
applied inside the views themselves via
wrongway_system.security.rate_limit.is_rate_limited - this middleware layer
never covers /api/ paths, so the two never double-limit.
"""
from django.http import HttpResponseBadRequest
from .rate_limit import is_rate_limited, rate_limit_response
from .sanitize import looks_malicious


class RateLimitMiddleware:

    LOGIN_PREFIXES = (
        '/auth/admin/login',
        '/auth/citizen/login',
        '/auth/admin/forgot-password',
        '/auth/citizen/forgot-password',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ''
        method = request.method

        if method == 'POST' and any(path.startswith(p) for p in self.LOGIN_PREFIXES):
            if is_rate_limited(request, 'login', limit=8, window=60):
                return rate_limit_response(request)

        if method == 'POST' and path.startswith('/portal/'):
            if is_rate_limited(request, 'portal_post', limit=120, window=60):
                return rate_limit_response(request)

        try:
            q = request.META.get('QUERY_STRING', '') or ''
            if q and looks_malicious(q):
                return HttpResponseBadRequest('Malformed request')
        except Exception:
            pass

        return self.get_response(request)


class RequestSizeLimitMiddleware:
    """Cap request body sizes before Django streams them into memory/files.

    /api/v1/ingest, /upload, /video/… paths are allowed 50 MB (ingest images
    are ≤10 MB and validated again inside the view; video uploads up to
    200 MB are accepted only after the middleware - see note below), every
    other path is capped at 5 MB.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            length = int(request.META.get('CONTENT_LENGTH') or 0)
        except (TypeError, ValueError):
            length = 0
        path = request.path or ''
        large_paths = ('/upload', '/cameras/', '/camera/', '/video/', '/media/', '/api/v1/ingest')
        max_bytes = 50 * 1024 * 1024 if any(p in path for p in large_paths) else 5 * 1024 * 1024
        if length > max_bytes:
            return HttpResponseBadRequest('Request body too large')
        return self.get_response(request)

