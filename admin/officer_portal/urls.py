from django.urls import path
from . import views
from admin.dig_portal import views as dig_views

app_name = 'officer_portal'

urlpatterns = [
    path('',                                       views.home,                name='home'),
    path('dashboard/',                             views.dashboard,           name='dashboard'),
    path('queue/',                                 views.review_queue,        name='review_queue'),
    path('detection/<int:detection_id>/',          views.detection_detail,    name='detection_detail'),
    path('detection/<int:detection_id>/confirm/',  views.confirm_detection,   name='confirm_detection'),
    path('detection/<int:detection_id>/reject/',   views.reject_detection,    name='reject_detection'),
    path('detection/<int:detection_id>/flag/',     views.flag_detection,      name='flag_detection'),
    path('detection/<int:detection_id>/note/',     views.add_review_note,     name='add_review_note'),

    path('detections/<int:detection_id>/',          views.detection_detail,    name='detection_detail_alias'),
    path('detections/<int:detection_id>/confirm/',  views.confirm_detection,   name='confirm_detection_alias'),
    path('detections/<int:detection_id>/reject/',   views.reject_detection,    name='reject_detection_alias'),
    path('detections/<int:detection_id>/flag/',     views.flag_detection,      name='flag_detection_alias'),
    path('detections/<int:detection_id>/note/',     views.add_review_note,     name='add_review_note_alias'),

    path('camera-feed/',                           views.camera_feed,         name='camera_feed'),
    path('detections/',                            views.detections_list,     name='detections_list'),
    path('flagged/',                               views.flagged_list,        name='flagged_list'),
    path('challans/',                              views.challans_list,       name='challans_list'),
    path('history/',                               views.review_history,      name='review_history'),
    path('challan/add/',                           views.add_manual_challan,  name='add_manual_challan'),

    path('appeals/',                               views.appeal_list,         name='appeal_list'),
    path('appeal/<int:appeal_id>/',                views.appeal_detail,       name='appeal_detail'),
    path('performance/',                           views.performance,         name='performance'),
    path('profile/',                               views.officer_profile,     name='self_profile'),  # M12 FIX: use officer_profile not dig_views.self_profile
    path('profile/view/',                          views.officer_profile,     name='profile'),


    path('cameras/<int:camera_id>/snapshot/',      dig_views.camera_snapshot, name='camera_snapshot'),
    path('cameras/<int:camera_id>/stream-url/',    dig_views.camera_stream_url, name='camera_stream_url'),
    path('live-tracking/',                         views.live_tracking,       name='live_tracking'),
    path('live-tracking/ai-assist/',                views.ai_assist_frame,     name='ai_assist_frame'),
    path('live-tracking/ocr-crop/',                  views.ocr_plate_crop,      name='ocr_plate_crop'),
    path('vehicle-tracking/',                      views.vehicle_tracking,    name='vehicle_tracking'),
    path('timeline/',                              views.frame_timeline,      name='frame_timeline'),
    path('live-tracking/timeline/',               views.frame_timeline,      name='live_tracking_timeline'),
    path('annotate/',                              views.manual_annotation,   name='manual_annotation'),
    path('annotate/submit/',                       views.submit_annotation,   name='submit_annotation'),
    path('live-tracking/annotation-save/',      views.annotation_save,     name='annotation_save'),

    path('notifications/',                          dig_views.notifications,             name='notifications'),
    path('notifications/<int:notification_id>/read/', dig_views.notification_read,       name='notification_read'),
    path('notifications/mark-read/',                dig_views.notification_mark_read,    name='notification_mark_read'),
    path('notifications/clear-all/',                dig_views.notification_clear_all,    name='notification_clear_all'),
]

