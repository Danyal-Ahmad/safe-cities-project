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
                return rate_limit_response()

        if method == 'POST' and path.startswith('/portal/'):
            if is_rate_limited(request, 'portal_post', limit=120, window=60):
                return rate_limit_response()

        try:
            q = request.META.get('QUERY_STRING', '') or ''
            if q and looks_malicious(q):
                return HttpResponseBadRequest('Malformed request')
        except Exception:
            pass

        return self.get_response(request)


class RequestSizeLimitMiddleware:

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

