from django.urls import path
from . import views
from admin.dig_portal import views as dig_views
from admin.shared import make_timeline_view

app_name = 'supervisor_portal'
urlpatterns = [
    path('live-monitor/', dig_views.live_monitor, name='live_monitor'),
    path('live-monitor/feed/', dig_views.live_monitor_feed, name='live_monitor_feed'),
    path('', views.dashboard, name='dashboard'),
    path('team-performance/', views.team_performance, name='team_performance'),
    path('queue-load/', views.team_queue_load, name='team_queue_load'),
    path('shifts/', views.shift_management, name='shift_management'),
    path('shifts/add/', views.shift_add, name='shift_add'),
    path('camera-assignments/', views.camera_assignments_view, name='camera_assignments'),

    path('officer-activity/', dig_views.officer_activity, name='officer_activity_list'),
    path('dashboard/officer/<int:officer_id>/activity/', dig_views.officer_activity, name='officer_activity'),

    path('challans/', dig_views.challan_list, name='challan_list'),
    path('vehicle-search/', dig_views.vehicle_search, name='vehicle_search'),
    path('blacklist/', dig_views.blacklist_list, name='blacklist_list'),
    path('reports/', dig_views.reports, name='reports'),
    path('appeals/', dig_views.appeals_queue, name='appeals_queue'),

    path('profile/', dig_views.self_profile, name='self_profile'),

    path('notifications/', dig_views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', dig_views.notification_read, name='notification_read'),
    path('notifications/mark-read/',           dig_views.notification_mark_read,    name='notification_mark_read'),
    path('notifications/clear-all/',           dig_views.notification_clear_all,    name='notification_clear_all'),

    path('officer-feedback/', dig_views.officer_feedback_list, name='officer_feedback_list'),
    path('officer-feedback/add/', dig_views.officer_feedback_add, name='officer_feedback_add'),

    path('alerts/hub/',                        dig_views.alerts_hub,                name='alerts_hub'),
    path('alerts/hub/add-alert/',               dig_views.alerts_hub_add_alert,      name='alerts_hub_add_alert'),
    path('alerts/hub/add-broadcast/',           dig_views.alerts_hub_add_broadcast,  name='alerts_hub_add_broadcast'),
    path('alerts/hub/alert/<int:alert_id>/toggle/',  dig_views.alerts_hub_toggle_alert,  name='alerts_hub_toggle_alert'),
    path('alerts/hub/alert/<int:alert_id>/edit/',   dig_views.alerts_hub_edit_alert,    name='alerts_hub_edit_alert'),
    path('alerts/hub/alert/<int:alert_id>/delete/',  dig_views.alerts_hub_delete_alert,  name='alerts_hub_delete_alert'),
    path('alerts/hub/banner/add/',                  dig_views.alerts_hub_add_banner,     name='alerts_hub_add_banner'),
    path('alerts/hub/banner/<int:banner_id>/edit/',   dig_views.alerts_hub_edit_banner,   name='alerts_hub_edit_banner'),
    path('alerts/hub/banner/<int:banner_id>/toggle/', dig_views.alerts_hub_toggle_banner, name='alerts_hub_toggle_banner'),
    path('alerts/hub/banner/<int:banner_id>/delete/', dig_views.alerts_hub_delete_banner, name='alerts_hub_delete_banner'),

    path('cameras/<int:camera_id>/snapshot/', dig_views.camera_snapshot, name='camera_snapshot'),
    path('live-tracking/', dig_views.live_tracking, name='live_tracking'),
    path('live-tracking/timeline/', make_timeline_view(['SUPV', 'DIG']), name='live_tracking_timeline'),
    path('officer-kpi/', dig_views.officer_kpi, name='officer_kpi'),
    path('change-password/', dig_views.staff_change_password, name='change_password'),
    path('appeals/tracker/', dig_views.appeals_queue, name='case_escalation_tracker'),
    path('reports/generate/', dig_views.generate_report, name='generate_report'),
    path('reports/operational/', dig_views.operational_reports, name='operational_reports'),
    path('reports/financial/', dig_views.financial_reports, name='financial_reports'),
    path('reports/operational-audit/', dig_views.operational_audit, name='operational_audit'),
    path('violation-stats/', dig_views.violation_stats, name='violation_stats'),
    path('heatmap/', dig_views.regional_heatmap, name='heatmap'),
]

