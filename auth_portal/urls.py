from django.urls import path
from . import views

app_name = 'auth_portal'

urlpatterns = [
    path('admin/login/',                    views.admin_login,           name='admin_login'),
    path('admin/logout/',                   views.logout_view,           name='logout'),
    path('admin/redirect/',                 views.role_redirect,         name='role_redirect'),

    path('admin/forgot-password/',          views.admin_forgot_password, name='admin_forgot_password'),

    path('citizen/login/',                  views.citizen_login,         name='citizen_login'),
    path('citizen/signup/',                 views.citizen_signup,        name='citizen_signup'),

    path('citizen/forgot-password/',        views.forgot_password,       name='forgot_password'),
    path('citizen/reset/<str:token>/',      views.citizen_reset_confirm, name='citizen_reset_confirm'),
]

