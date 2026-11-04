
from django.http import HttpResponse
from django.template import loader


def _render_error(request, template_name, status_code):
    template = loader.get_template(template_name)
    return HttpResponse(template.render({}, request), status=status_code)


def custom_400(request, exception):
    return _render_error(request, 'errors/400.html', 400)


def custom_401(request, exception):
    return _render_error(request, 'errors/401.html', 401)


def custom_402(request, exception):
    return _render_error(request, 'errors/402.html', 402)


def custom_403(request, exception):
    return _render_error(request, 'errors/403.html', 403)


def custom_404(request, exception):
    return _render_error(request, 'errors/404.html', 404)


def custom_500(request):
    return _render_error(request, 'errors/500.html', 500)


def custom_501(request, exception):
    return _render_error(request, 'errors/501.html', 501)


def custom_502(request, *args, **kwargs):
    return _render_error(request, 'errors/502.html', 502)


def custom_503(request, *args, **kwargs):
    return _render_error(request, 'errors/503.html', 503)

