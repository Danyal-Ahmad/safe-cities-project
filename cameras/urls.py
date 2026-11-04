from django.urls import path
from . import views

app_name = 'cameras'
urlpatterns = [
    path('v1/enroll/', views.enroll_camera, name='enroll_camera'),
    path('v1/ingest/', views.ingest, name='ingest'),
    path('v1/heartbeat/', views.heartbeat, name='heartbeat'),
]

