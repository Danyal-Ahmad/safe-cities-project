from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'challans'

urlpatterns = [
    path('', views.home, name='home'),
    path('challan/', RedirectView.as_view(pattern_name='challans:home', permanent=False)),
    path('challan/<int:challan_id>/', views.challan_detail, name='challan_detail'),
    path('challan/<int:challan_id>/pdf/', views.challan_pdf, name='challan_pdf'),
    path('challan/<int:challan_id>/pay/', views.guest_pay, name='guest_pay'),
    path('challan/<int:challan_id>/pay/done/', views.guest_pay_done, name='guest_pay_done'),
    path('challan/view/<str:signed_token>/', views.challan_detail_signed, name='challan_detail_signed'),
]

