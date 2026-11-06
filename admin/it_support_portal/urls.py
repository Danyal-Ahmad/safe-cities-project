from django.urls import path
from . import views
from admin.dig_portal import views as dig_views

app_name = 'it_support_portal'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('cameras/', dig_views.camera_list, name='camera_list'),
    path('cameras/heartbeats/', views.camera_heartbeats, name='camera_heartbeats'),
    path('cameras/heartbeats/run/', views.camera_heartbeat_run, name='camera_heartbeat_run'),
    path('cameras/add/', dig_views.camera_add, name='camera_add'),
    path('cameras/<int:camera_id>/', dig_views.camera_edit, name='camera_edit'),
    path('cameras/<int:camera_id>/toggle/', dig_views.camera_toggle, name='camera_toggle'),
    path('cameras/<int:camera_id>/delete/', dig_views.camera_delete, name='camera_delete'),
    path('cameras/<int:camera_id>/set-online/', dig_views.camera_set_online, name='camera_set_online'),
    path('cameras/<int:camera_id>/enrollment-token/', dig_views.regenerate_enrollment_token, name='regenerate_enrollment_token'),
    path('camera-health/', dig_views.camera_health, name='camera_health'),
    path('cameras-status/', dig_views.cameras_status, name='cameras_status'),
    path('cameras/assignments/', dig_views.camera_assignments, name='camera_assignments'),
    path('live-monitor/', dig_views.live_monitor, name='live_monitor'),
    path('live-monitor/feed/', dig_views.live_monitor_feed, name='live_monitor_feed'),
    path('live-tracking/', views.live_tracking, name='live_tracking'),
    path('live-tracking/timeline/', views.live_tracking_timeline, name='live_tracking_timeline'),
    path('cameras/<int:camera_id>/snapshot/', dig_views.camera_snapshot, name='camera_snapshot'),
    path('cameras/<int:camera_id>/stream-url/', dig_views.camera_stream_url, name='camera_stream_url'),
    path('cameras/<int:camera_id>/test/', dig_views.camera_test, name='camera_test'),

    path('system-health/', views.system_health, name='system_health'),
    path('payment-settings/', dig_views.payment_settings, name='payment_settings'),
    path('payments/monitor/', views.payment_transactions, name='payment_transactions'),
    path('payments/monitor/<int:txn_id>/', views.payment_transaction_detail, name='payment_transaction_detail'),
    path('settings/', dig_views.settings_edit, name='settings_edit'),
    path('settings/smtp-test/', views.smtp_test, name='smtp_test'),
    path('reset-requests/', views.reset_requests, name='reset_requests'),
    path('pdf-settings/', views.pdf_settings, name='pdf_settings'),
    path('challan-templates/', dig_views.challan_templates_manage, name='challan_templates'),
    path('challan-templates/designer/', dig_views.challan_template_designer, name='challan_template_designer'),
    path('audit-templates/', views.audit_templates_manage, name='audit_templates'),
    path('backups/', dig_views.backup_list, name='backup_list'),
    path('backups/download/<str:filename>/', dig_views.backup_download, name='backup_download'),
    path('alerts/', dig_views.alerts_hub, name='alerts_hub'),
    path('alerts/hub/', dig_views.alerts_hub, name='alerts_hub_alt'),
    path('alerts/hub/add-alert/',               dig_views.alerts_hub_add_alert,      name='alerts_hub_add_alert'),
    path('alerts/hub/add-broadcast/',           dig_views.alerts_hub_add_broadcast,  name='alerts_hub_add_broadcast'),
    path('alerts/hub/alert/<int:alert_id>/toggle/',  dig_views.alerts_hub_toggle_alert,  name='alerts_hub_toggle_alert'),
    path('alerts/hub/alert/<int:alert_id>/edit/',   dig_views.alerts_hub_edit_alert,    name='alerts_hub_edit_alert'),
    path('alerts/hub/alert/<int:alert_id>/delete/',  dig_views.alerts_hub_delete_alert,  name='alerts_hub_delete_alert'),
    path('alerts/hub/banner/add/',                  dig_views.alerts_hub_add_banner,     name='alerts_hub_add_banner'),
    path('alerts/hub/banner/<int:banner_id>/edit/',   dig_views.alerts_hub_edit_banner,    name='alerts_hub_edit_banner'),
    path('alerts/hub/banner/<int:banner_id>/toggle/', dig_views.alerts_hub_toggle_banner,  name='alerts_hub_toggle_banner'),
    path('alerts/hub/banner/<int:banner_id>/delete/', dig_views.alerts_hub_delete_banner,  name='alerts_hub_delete_banner'),

    path('notifications/mark-read/',           dig_views.notification_mark_read,    name='notification_mark_read'),
    path('notifications/clear-all/',           dig_views.notification_clear_all,    name='notification_clear_all'),

    path('payment-methods/', views.payment_method_list, name='payment_method_list'),
    path('payment-methods/add/', views.payment_method_add, name='payment_method_add'),
    path('payment-methods/<int:method_id>/', views.payment_method_edit, name='payment_method_edit'),
    path('payment-methods/<int:method_id>/toggle/', views.payment_method_toggle, name='payment_method_toggle'),
    path('payment-methods/<int:method_id>/delete/', views.payment_method_delete, name='payment_method_delete'),

    path('staff/', views.staff_list, name='staff_list'),
    path('officer-signatures/', dig_views.officer_signatures, name='officer_signatures'),

    path('profile/', dig_views.self_profile, name='self_profile'),
]
