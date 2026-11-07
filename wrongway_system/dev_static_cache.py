"""Development-only static cache control.

When DEBUG is on, the staticfiles serve view can send responses without
explicit Cache-Control headers, so browsers fall back to heuristic caching
and keep serving stale CSS/JS after files change on disk. That makes every
visual iteration look "broken" until a hard refresh. This middleware stamps
`Cache-Control: no-store` on /static/ responses in DEBUG mode only, so a
normal reload always picks up the latest assets.

In production (DEBUG=False) it does nothing: WhiteNoise serves fingerprinted
static files with immutable cache headers, which is exactly what we want.
"""

class DevStaticNoCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            from django.conf import settings
            if settings.DEBUG and request.path.startswith('/static/'):
                response['Cache-Control'] = 'no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
        except Exception:
            pass
        return response
