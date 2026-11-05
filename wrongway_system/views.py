"""Shared error handlers for Safe City.

Every handler renders the single shared template ``errors/error_page.html``
with a ``code`` / ``title`` / ``message`` context. The template is a
standalone page (own <head>, CSS via {% static %}) so it renders even when
the request context or context processors are unavailable (e.g. 500s).
"""

from django.http import HttpResponse
from django.template import loader

ERROR_TEMPLATE = 'errors/error_page.html'


def _render_error(request, status_code, title, message):
    """Render the shared error page.

    Deliberately uses ``loader`` + a plain (non-Request) context so that
    context processors never run - the 500 handler must work even when the
    database / auth machinery is the thing that is broken.
    """
    context = {
        'code': status_code,
        'title': title,
        'message': message,
    }
    template = loader.get_template(ERROR_TEMPLATE)
    return HttpResponse(template.render(context), status=status_code)


def custom_400(request, exception=None):
    return _render_error(
        request, 400, 'Bad Request',
        'The server could not understand your request - the address or the '
        'submitted data may be malformed. Please go back, check the input '
        'and try again.',
    )


def custom_401(request, exception=None):
    return _render_error(
        request, 401, 'Authentication Required',
        'You need to sign in with a valid account to view this page. '
        'Please go back, log in and try again.',
    )


def custom_402(request, exception=None):
    return _render_error(
        request, 402, 'Payment Required',
        'This request requires a payment that has not been completed. '
        'If you were paying an e-challan, please go back and retry the '
        'payment.',
    )


def custom_403(request, exception=None):
    return _render_error(
        request, 403, 'Access Forbidden',
        'You do not have permission to access this page. If you believe you '
        'should, sign in with an account that has the required role or '
        'contact your administrator.',
    )


def custom_404(request, exception=None):
    return _render_error(
        request, 404, 'Page Not Found',
        'The page you are looking for does not exist or may have been '
        'moved. Check the address for typos, or head back to the home page.',
    )


def custom_500(request):
    return _render_error(
        request, 500, 'Internal Server Error',
        'Something went wrong on our side while processing your request. '
        'The issue has been logged - please try again in a few moments.',
    )


def custom_501(request, exception=None):
    return _render_error(
        request, 501, 'Not Implemented',
        'The server does not yet support the functionality required for '
        'this request. This feature is still under development.',
    )


def custom_502(request, exception=None):
    return _render_error(
        request, 502, 'Bad Gateway',
        'The server received an invalid response from an upstream service. '
        'This is usually temporary - please go back and try again shortly.',
    )


def custom_503(request, exception=None):
    return _render_error(
        request, 503, 'Service Unavailable',
        'The service is temporarily unavailable, most likely for scheduled '
        'maintenance. Please check back soon - we are restoring it as '
        'quickly as possible.',
    )
