from django.urls import path
from . import webhook

urlpatterns = [
    path('webhook/', webhook.payment_webhook, name='webhook'),
]

