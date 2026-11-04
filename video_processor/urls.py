from django.urls import path
from . import views

app_name = 'video_processor'
urlpatterns = [
    path('upload/', views.upload_video, name='upload_video'),
    path('uploads/', views.upload_list, name='upload_list'),
    path('manual/<int:detection_id>/', views.manual_annotation, name='manual_annotation'),
    path('annotate/<int:detection_id>/', views.manual_annotation, name='annotate_alias'),
]
