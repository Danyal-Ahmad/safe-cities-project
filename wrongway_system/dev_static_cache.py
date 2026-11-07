
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

