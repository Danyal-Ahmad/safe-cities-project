from django.urls import path
from . import views

app_name = 'video_processor'
urlpatterns = [
    path('upload/', views.upload_video, name='upload_video'),
    path('uploads/', views.upload_list, name='upload_list'),
]
