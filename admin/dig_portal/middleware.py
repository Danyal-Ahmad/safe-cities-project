import secrets

from admin.shared.net import client_ip


class AuditLogMiddleware:
    MUTATING_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
    STAFF_ROLES = {'DIG', 'SSP', 'SUPV', 'OFFICER', 'AUDIT', 'IT'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (request.method in self.MUTATING_METHODS
                and getattr(request.user, 'is_authenticated', False)
                and getattr(request.user, 'role', None) in self.STAFF_ROLES
                and 200 <= response.status_code < 400):
            if request.path.startswith((
                '/auth/admin/login', '/auth/admin/logout', '/auth/admin/redirect',
                '/auth/admin/forgot-password', '/auth/admin/reset',
                '/auth/citizen/login', '/auth/citizen/signup',
                '/auth/citizen/forgot-password', '/auth/citizen/reset',
                '/admin/login',
            )):
                return response
            from admin.dig_portal.models import AuditLog
            import logging
            try:
                ua_str = (request.META.get('HTTP_USER_AGENT') or '')[:400]
                device, _ = AuditLog.parse_device(ua_str)
                AuditLog.objects.create(
                    actor=request.user,
                    action=f"{request.method} {request.path}",
                    target_model='', target_id=None,
                    details={'path': request.path, 'method': request.method},
                    ip_address=client_ip(request)
                              or request.META.get('REMOTE_ADDR'),
                    user_agent=ua_str,
                    device=device,
                )
            except Exception as e:
                logging.getLogger('safecity').warning(
                    'AuditLogMiddleware write failed for %s %s: %s',
                    request.method, request.path, e,
                )
        return response


class AccountLockoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (getattr(request.user, 'is_authenticated', False)
                and getattr(request.user, 'is_locked', False)):
            from django.contrib.auth import logout
            from django.contrib import messages
            logout(request)
            messages.error(request, "Your account has been locked due to multiple failed login attempts. Try again later.")
        return self.get_response(request)


class SecurityHeadersMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    EMBEDDABLE_SUFFIXES = ('/profile/',)


    _FALLBACKS = {
        'CSP_DEFAULT_SRC': ("'self'",),
        'CSP_SCRIPT_SRC': ("'self'", "'unsafe-inline'",
                            'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com',
                            'https://unpkg.com', 'https://cdn.tailwindcss.com',
                            'https://fonts.googleapis.com'),
        'CSP_STYLE_SRC': ("'self'", "'unsafe-inline'",
                           'https://fonts.googleapis.com', 'https://cdnjs.cloudflare.com',
                           'https://unpkg.com', 'https://cdn.jsdelivr.net'),
        'CSP_FONT_SRC': ("'self'", 'data:', 'https://fonts.gstatic.com',
                          'https://fonts.googleapis.com', 'https://cdnjs.cloudflare.com'),
        'CSP_IMG_SRC': ("'self'", 'data:', 'blob:', 'https:'),
        'CSP_CONNECT_SRC': ("'self'",),
        'CSP_FORM_ACTION': ("'self'", 'https:'),
        'CSP_OBJECT_SRC': ("'none'",),
        'CSP_BASE_URI': ("'self'",),
        'CSP_FRAME_ANCESTORS': ("'none'",),
        'CSP_FRAME_ANCESTORS_EMBED': ("'self'",),
    }

    @classmethod
    def _tokens(cls, settings, name):
        value = getattr(settings, name, None)
        if not value:
            value = cls._FALLBACKS[name]
        return ' '.join(value)

    def __call__(self, request):
        from django.conf import settings


        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce

        response = self.get_response(request)

        is_embed_fragment = (
            request.path.endswith(self.EMBEDDABLE_SUFFIXES)
            and request.GET.get('embed') == '1'
        )

        frame_ancestors = (
            'frame-ancestors ' + self._tokens(settings, 'CSP_FRAME_ANCESTORS_EMBED') + '; '
            if is_embed_fragment else
            'frame-ancestors ' + self._tokens(settings, 'CSP_FRAME_ANCESTORS') + '; '
        )

        csp = (
            "default-src " + self._tokens(settings, 'CSP_DEFAULT_SRC') + "; "


            "script-src 'nonce-" + nonce + "' "
            + self._tokens(settings, 'CSP_SCRIPT_SRC') + "; "


            "script-src-attr 'unsafe-inline'; "
            "style-src " + self._tokens(settings, 'CSP_STYLE_SRC') + "; "
            "font-src " + self._tokens(settings, 'CSP_FONT_SRC') + "; "
            "img-src " + self._tokens(settings, 'CSP_IMG_SRC') + "; "
            "connect-src " + self._tokens(settings, 'CSP_CONNECT_SRC') + "; "
            + frame_ancestors +
            "object-src " + self._tokens(settings, 'CSP_OBJECT_SRC') + "; "
            "base-uri " + self._tokens(settings, 'CSP_BASE_URI') + "; "


            "form-action " + self._tokens(settings, 'CSP_FORM_ACTION')
        )

        response['Content-Security-Policy'] = csp


        response['X-Frame-Options'] = 'SAMEORIGIN' if is_embed_fragment else 'DENY'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Referrer-Policy'] = 'same-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        return response


class PortalIsolationMiddleware:

    PORTAL_ROLES = {
        '/portal/dig/': 'DIG',
        '/portal/ssp/': 'SSP',
        '/portal/supervisor/': 'SUPV',
        '/portal/officer/': 'OFFICER',
        '/portal/audit/': 'AUDIT',
        '/portal/it/': 'IT',
        '/portal/citizen/': 'USER',
    }

    EXEMPT_PREFIXES = (
        '/static/',
        '/media/',
        '/django-admin/',
        '/auth/',
        '/api/',
        '/realtime/',
        '/video/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith('/portal/'):
            return self.get_response(request)

        for exempt in self.EXEMPT_PREFIXES:
            if path.startswith(exempt):
                return self.get_response(request)

        required_role = None
        for prefix, role in self.PORTAL_ROLES.items():
            if path.startswith(prefix):
                required_role = role
                break

        if required_role is None:
            return self.get_response(request)

        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            from django.shortcuts import redirect
            if required_role == 'USER':
                return redirect('auth_portal:citizen_login')
            return redirect('auth_portal:admin_login')

        user_role = getattr(user, 'role', None)
        if user_role != required_role:
            from django.contrib import messages
            from accounts.decorators import _safe_redirect
            messages.error(
                request,
                f"Access denied. Your account ({getattr(user, 'role_label', user_role)}) "
                f"cannot access the {required_role} portal. Redirecting to your assigned dashboard."
            )
            return _safe_redirect(request)

        return self.get_response(request)

