from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from . import views as error_views

handler400 = error_views.custom_400
handler401 = error_views.custom_401
handler402 = error_views.custom_402
handler404 = error_views.custom_404
handler500 = error_views.custom_500
handler501 = error_views.custom_501
handler502 = error_views.custom_502
handler503 = error_views.custom_503

urlpatterns = [
    path('django-admin/', admin.site.urls),

    path('favicon.ico', RedirectView.as_view(url='/static/img/project_logo.png', permanent=True)),

    path('', include('challans.urls')),

    path('auth/', include('auth_portal.urls')),

    path('portal/dig/',          include('admin.dig_portal.urls')),
    path('portal/ssp/',          include('admin.ssp_portal.urls')),
    path('portal/supervisor/',   include('admin.supervisor_portal.urls')),
    path('portal/officer/',      include('admin.officer_portal.urls')),
    path('portal/audit/',        include('admin.audit_portal.urls')),
    path('portal/it/',           include('admin.it_support_portal.urls')),
    path('portal/citizen/',      include('citizen.citizen_portal.urls')),


    path('dig/',          RedirectView.as_view(url='/portal/dig/', permanent=False)),
    path('ssp/',          RedirectView.as_view(url='/portal/ssp/', permanent=False)),
    path('supervisor/',   RedirectView.as_view(url='/portal/supervisor/', permanent=False)),
    path('officer/',      RedirectView.as_view(url='/portal/officer/', permanent=False)),
    path('audit/',        RedirectView.as_view(url='/portal/audit/', permanent=False)),
    path('it-support/',   RedirectView.as_view(url='/portal/it/', permanent=False)),
    path('portal/',       RedirectView.as_view(url='/portal/citizen/', permanent=False)),

    path('api/',          include('cameras.urls')),
    path('api/v1/payment/', include('payments.urls')),

    path('realtime/',     include('realtime.urls')),
    path('video/',        include('video_processor.urls')),
]


def handler403(request, exception=None):
    from django.shortcuts import render

    is_ratelimited = False
    if exception is not None:
        try:
            from django_ratelimit.exceptions import Ratelimited
            is_ratelimited = isinstance(exception, Ratelimited)
        except Exception:
            is_ratelimited = type(exception).__name__ == 'Ratelimited'

    if is_ratelimited:
        return render(
            request,
            'errors/error_page.html',
            {
                'code': 403,
                'title': 'Access Forbidden',
                'message': (
                    'You do not have permission to access this page. If you '
                    'believe you should, sign in with an account that has '
                    'the required role or contact your administrator.'
                ),
                'ratelimited': True,
                'retry_minutes': 15,
                'err_title_override': 'Too Many Attempts',
                'err_msg_override': (
                    'You have made too many login attempts in a short period. '
                    'Please wait about 15 minutes and try again. This limit '
                    'protects the system against brute-force password guessing.'
                ),
            },
            status=403,
        )

    return render(
        request,
        'errors/error_page.html',
        {
            'code': 403,
            'title': 'Access Forbidden',
            'message': (
                'You do not have permission to access this page. If you '
                'believe you should, sign in with an account that has the '
                'required role or contact your administrator.'
            ),
        },
        status=403,
    )

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')

