from django.urls import path
from . import webhook
from . import views

urlpatterns = [
    path('webhook/', webhook.payment_webhook, name='webhook'),
    path('demo-checkout/', views.demo_checkout, name='demo_checkout'),
]