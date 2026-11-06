from django.urls import path
from . import views
from admin.dig_portal import views as dig_views

app_name = 'audit_portal'

urlpatterns = [
    path('',                    views.dashboard,           name='dashboard'),
    path('anomalies/',          views.anomaly_alerts,      name='anomaly_alerts'),
    path('compliance/',         views.compliance_reports,  name='compliance_reports'),
    path('financial/',          views.financial_audit,     name='financial_audit'),
    path('operational/',        views.operational_audit,   name='operational_audit'),

    path('user-activity/',      views.user_activity,       name='user_activity'),
    path('auth-events/',        views.auth_events,         name='auth_events'),
    path('permission-changes/', views.permission_changes,  name='permission_changes'),
    path('permissions/',        views.permission_changes,  name='permissions_alias'),
    path('camera-changes/',     views.camera_changes,      name='camera_changes'),
    path('challan-changes/',    views.challan_changes,     name='challan_changes'),
    path('payment-changes/',    views.payment_changes,     name='payment_changes'),
    path('banner-changes/',     views.banner_changes,      name='banner_changes'),
    path('alert-changes/',      views.alert_changes,       name='alert_changes'),
    path('export/',              views.audit_export,         name='audit_export'),
    path('export/pdf/<str:kind>/', views.export_pdf,         name='export_pdf'),
    path('templates/',           views.templates_select,     name='templates_select'),

    path('login-events/',        views.login_events,         name='login_events'),
    path('login-events/export/', views.login_events_export,  name='login_events_export'),
    path('uploads/',             views.uploads_log,          name='uploads_log'),
    path('appeals/',             dig_views.appeals_queue,    name='appeals_queue'),

    path('cameras/<int:camera_id>/snapshot/', dig_views.camera_snapshot, name='camera_snapshot'),

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
]

