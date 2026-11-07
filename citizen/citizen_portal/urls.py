from django.urls import path
from . import views

app_name = 'citizen_portal'

urlpatterns = [
    path('',                                       views.home,             name='home'),
    path('challan/<int:challan_id>/appeal/',       views.submit_appeal,    name='submit_appeal'),
    path('challan/<int:challan_id>/pay/',           views.pay_challan,      name='pay_challan'),
    path('appeals/',                               views.appeal_tracker,    name='appeal_tracker'),
    path('profile/',                               views.profile_edit,     name='profile_edit'),
    path('password/',                              views.password_change,   name='password_change'),

    path('api/kpis/',       views.api_citizen_kpis,      name='api_citizen_kpis'),
    path('api/challans/',   views.api_citizen_challans,  name='api_citizen_challans'),
]

