from django.urls import path
from . import views
from admin.dig_portal import views as dig_views

app_name = 'officer_portal'

urlpatterns = [
    path('',                                       views.home,                name='home'),
    path('dashboard/',                             views.dashboard,           name='dashboard'),
    path('queue/',                                 views.review_queue,        name='review_queue'),
    path('detection/<int:detection_id>/',          views.detection_detail,    name='detection_detail'),
    path('detection/<int:detection_id>/reject/',   views.reject_detection,    name='reject_detection'),
    path('detection/<int:detection_id>/flag/',     views.flag_detection,      name='flag_detection'),
    path('detection/<int:detection_id>/note/',     views.add_review_note,     name='add_review_note'),

    path('detections/',                            views.detections_list,     name='detections_list'),
    path('flagged/',                               views.flagged_list,        name='flagged_list'),
    path('challans/',                              views.challans_list,       name='challans_list'),
    path('history/',                               views.review_history,      name='review_history'),

    path('appeals/',                               views.appeal_list,         name='appeal_list'),
    path('appeal/<int:appeal_id>/',                views.appeal_detail,       name='appeal_detail'),
    path('performance/',                           views.performance,         name='performance'),
    path('profile/',                               views.officer_profile,     name='self_profile'),
    path('profile/view/',                          views.officer_profile,     name='profile'),

    path('cameras/<int:camera_id>/snapshot/',      dig_views.camera_snapshot, name='camera_snapshot'),
    path('cameras/<int:camera_id>/stream-url/',    dig_views.camera_stream_url, name='camera_stream_url'),
    path('live-tracking/',                         views.live_tracking,       name='live_tracking'),

    path('notifications/',                          dig_views.notifications,             name='notifications'),
    path('notifications/<int:notification_id>/read/', dig_views.notification_read,       name='notification_read'),
    path('notifications/mark-read/',                dig_views.notification_mark_read,    name='notification_mark_read'),
    path('notifications/clear-all/',                dig_views.notification_clear_all,    name='notification_clear_all'),
]
