from django.urls import path
from . import views
from admin.dig_portal import views as dig_views
from admin.shared import make_timeline_view

app_name = 'ssp_portal'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('challan/<int:challan_id>/approve/', views.approve_challan, name='approve_challan'),
    path('challans/<int:challan_id>/approve/', views.approve_challan, name='approve_challan_alias'),
    path('appeal/<int:appeal_id>/decide/', views.decide_appeal, name='decide_appeal'),

    path('production/', views.daily_production, name='daily_production'),
    path('production/export/', views.daily_production_export, name='daily_production_export'),
    path('camera-outage/', views.camera_outage, name='camera_outage'),

    path('challans/', dig_views.challan_list, name='challan_list'),
    path('blacklist/', dig_views.blacklist_list, name='blacklist_list'),
    path('blacklist/add/', dig_views.blacklist_add, name='blacklist_add'),


    path('appeals/', dig_views.appeals_queue, name='case_escalation'),
    path('appeals/tracker/', dig_views.appeals_queue, name='case_escalation_tracker'),
    path('appeals/queue/', dig_views.appeals_queue, name='appeal_list'),

    path('camera-health/', dig_views.camera_health, name='camera_health'),
    path('cameras-status/', dig_views.cameras_status, name='cameras_status'),
    path('officer-kpi/', dig_views.officer_kpi, name='officer_kpi'),
    path('violations/', dig_views.violation_stats, name='violation_stats'),
    path('revenue/', dig_views.revenue_dashboard, name='revenue_dashboard'),

    path('notifications/', dig_views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', dig_views.notification_read, name='notification_read'),

    path('analytics/', dig_views.analytics, name='analytics'),
    path('reports/', dig_views.reports, name='reports'),
    path('vehicle-search/', dig_views.vehicle_search, name='vehicle_search'),
    path('live-monitor/', dig_views.live_monitor, name='live_monitor'),
    path('officer-activity/', dig_views.officer_activity, name='officer_activity_list'),
    path('officer-activity/<int:officer_id>/', dig_views.officer_activity, name='officer_activity'),
    path('heatmap/', dig_views.regional_heatmap, name='heatmap'),

    path('profile/', dig_views.self_profile, name='self_profile'),

    path('notifications/mark-read/',           dig_views.notification_mark_read,    name='notification_mark_read'),
    path('notifications/clear-all/',           dig_views.notification_clear_all,    name='notification_clear_all'),

    path('alerts/hub/',                        dig_views.alerts_hub,                name='alerts_hub'),
    path('alerts/hub/add-alert/',               dig_views.alerts_hub_add_alert,      name='alerts_hub_add_alert'),
    path('alerts/hub/add-broadcast/',           dig_views.alerts_hub_add_broadcast,  name='alerts_hub_add_broadcast'),
    path('alerts/hub/alert/<int:alert_id>/toggle/',  dig_views.alerts_hub_toggle_alert,  name='alerts_hub_toggle_alert'),
    path('alerts/hub/alert/<int:alert_id>/edit/',   dig_views.alerts_hub_edit_alert,    name='alerts_hub_edit_alert'),
    path('alerts/hub/alert/<int:alert_id>/delete/',  dig_views.alerts_hub_delete_alert,  name='alerts_hub_delete_alert'),
    path('alerts/hub/banner/add/',                  dig_views.alerts_hub_add_banner,     name='alerts_hub_add_banner'),
    path('alerts/hub/banner/<int:banner_id>/edit/',   dig_views.alerts_hub_edit_banner,    name='alerts_hub_edit_banner'),
    path('alerts/hub/banner/<int:banner_id>/toggle/', dig_views.alerts_hub_toggle_banner,  name='alerts_hub_toggle_banner'),
    path('alerts/hub/banner/<int:banner_id>/delete/', dig_views.alerts_hub_delete_banner,  name='alerts_hub_delete_banner'),

    path('cameras/<int:camera_id>/snapshot/', dig_views.camera_snapshot, name='camera_snapshot'),
    path('live-tracking/', dig_views.live_tracking, name='live_tracking'),
    path('live-tracking/timeline/', make_timeline_view(['SSP', 'DIG']), name='live_tracking_timeline'),
    path('change-password/', dig_views.staff_change_password, name='change_password'),
    path('reports/generate/', dig_views.generate_report, name='generate_report'),
    path('reports/operational/', dig_views.operational_reports, name='operational_reports'),
    path('reports/financial/', dig_views.financial_reports, name='financial_reports'),
    path('reports/operational-audit/', dig_views.operational_audit, name='operational_audit'),
    path('escalations/', dig_views.appeals_queue, name='escalation_list'),
    path('notifications/feed/', dig_views.notifications, name='notifications_feed'),
]

