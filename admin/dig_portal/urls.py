from admin.officer_portal import views as officer_views
from django.urls import path
from . import views
from . import autocomplete

app_name = 'dig'
urlpatterns = [
    path('',                              views.dashboard,               name='dashboard'),
    path('dashboard/',                    views.dashboard,               name='dashboard_alt'),

    path('violations/',                   views.violation_stats,         name='violation_stats'),
    path('flagged-detections/',           views.flagged_detections,      name='flagged_detections'),
    path('escalations/',                  views.escalation_list,         name='escalation_list'),
    path('vehicle-search/',               views.vehicle_search,          name='vehicle_search'),
    path('blacklist/',                    views.blacklist_list,          name='blacklist_list'),
    path('blacklist/add/',                views.blacklist_add,           name='blacklist_add'),
    path('challans/',                     views.challan_list,            name='challan_list'),
    path('challan/<int:challan_id>/delete/',          views.delete_challan,          name='delete_challan'),
    path('challan/<int:challan_id>/delete-confirm/',  views.challan_confirm_delete,  name='challan_confirm_delete'),
    path('challan/<int:challan_id>/fine/',            views.edit_challan_fine,       name='edit_challan_fine'),
    path('challan/<int:challan_id>/mark-paid/',       views.mark_challan_paid,       name='mark_challan_paid'),
    path('challan/<int:challan_id>/mark-unpaid/',     views.mark_challan_unpaid,     name='mark_challan_unpaid'),
    path('challan/<int:challan_id>/record-payment/',  views.record_payment,          name='record_payment'),
    path('challan/<int:challan_id>/verify-payment/',  views.verify_citizen_payment,  name='verify_citizen_payment'),
    path('challans/bulk-fine-adjust/',                views.bulk_fine_adjust,       name='bulk_fine_adjust'),

path('analytics/',                    views.analytics,               name='analytics'),
    
    path('shifts/',                       views.shift_management,        name='shift_management'),
    path('shifts/add/',                   views.shift_add,               name='shift_add'),
    
    path('penalty-config/',               views.penalty_config,          name='penalty_config'),

    path('cameras/<int:camera_id>/snapshot/', views.camera_snapshot,      name='camera_snapshot'),
    path('cameras/<int:camera_id>/stream-url/', views.camera_stream_url,  name='camera_stream_url'),
    path('cameras/<int:camera_id>/test/',     views.camera_test,          name='camera_test'),
    path('camera-health/',                views.camera_health,           name='camera_health'),

    path('audit/',                        views.audit_log,               name='audit_log'),
    path('audit/export/',                 views.audit_export,            name='audit_export'),
    path('operational-audit/',            views.operational_audit,       name='operational_audit'),
    path('financial-audit/',              views.financial_audit,         name='financial_audit'),

    path('users/',                        views.citizen_users_list,       name='citizen_users_list'),
    path('users/set-password/',            views.citizen_set_password,     name='citizen_set_password'),
    path('admins/',                       views.admin_list,              name='admin_list'),
    path('admins/add/',                   views.admin_add,               name='admin_add'),
    path('admins/<int:user_id>/',         views.admin_edit,              name='admin_edit'),
    path('admins/<int:user_id>/toggle/',  views.admin_toggle,            name='admin_toggle'),
    path('admins/<int:user_id>/toggle-active/', views.admin_toggle,   name='admin_toggle_active'),
    path('users/<int:user_id>/toggle/', views.admin_toggle,           name='citizen_toggle'),
    path('admins/set-password/',           views.staff_set_password,      name='staff_set_password'),
    path('admins/<int:user_id>/delete/',  views.admin_delete,            name='admin_delete'),

    path('reports/',                      views.reports,                 name='reports'),
    path('reports/generate/',             views.generate_report,         name='generate_report'),
    path('operational-reports/',          views.operational_reports,     name='operational_reports'),
    path('financial-reports/',            views.financial_reports,       name='financial_reports'),

    path('payments/',                     views.payment_list,            name='payment_list'),

    path('revenue/',                      views.revenue_dashboard,       name='revenue_dashboard'),
    path('dashboard/officer/<int:officer_id>/activity/', views.officer_activity, name='officer_activity'),
    path('appeal/<int:appeal_id>/override/', views.appeal_override,      name='appeal_override'),
    path('alerts/hub/',                          views.alerts_hub,              name='alerts_hub'),
    path('alerts/hub/add-alert/',                views.alerts_hub_add_alert,    name='alerts_hub_add_alert'),
    path('alerts/hub/add-banner/',               views.alerts_hub_add_banner,   name='alerts_hub_add_banner'),
    path('alerts/hub/add-broadcast/',            views.alerts_hub_add_broadcast, name='alerts_hub_add_broadcast'),
    path('alerts/hub/alert/<int:alert_id>/toggle/',  views.alerts_hub_toggle_alert,  name='alerts_hub_toggle_alert'),
    path('alerts/hub/alert/<int:alert_id>/edit/',   views.alerts_hub_edit_alert,    name='alerts_hub_edit_alert'),
    path('alerts/hub/alert/<int:alert_id>/delete/',  views.alerts_hub_delete_alert,  name='alerts_hub_delete_alert'),
    path('alerts/hub/banner/<int:banner_id>/toggle/', views.alerts_hub_toggle_banner, name='alerts_hub_toggle_banner'),
    path('alerts/hub/banner/<int:banner_id>/edit/',  views.alerts_hub_edit_banner,   name='alerts_hub_edit_banner'),
    path('alerts/hub/banner/<int:banner_id>/delete/', views.alerts_hub_delete_banner, name='alerts_hub_delete_banner'),
    path('alerts/hub/broadcast/<int:log_id>/delete/', views.alerts_hub_delete_broadcast, name='alerts_hub_delete_broadcast'),

    path('change-password/',              views.staff_change_password,   name='staff_change_password'),
    path('change-password/alt/',          views.staff_change_password,   name='change_password'),
    path('officer-signatures/',           views.officer_signatures,       name='officer_signatures'),
    path('profile/',                       views.self_profile,            name='self_profile'),

    path('notifications/mark-read/',      views.notification_mark_read,  name='notification_mark_read'),
    path('notifications/clear-all/',      views.notification_clear_all,  name='notification_clear_all'),


    path('broadcast/',                    views.broadcast_notification,  name='broadcast_notification'),
    path('compliance/',                   views.compliance,              name='compliance'),

    path('cameras-status/',               views.cameras_status,          name='cameras_status'),

    path('case-escalation/',              views.case_escalation_tracker, name='case_escalation'),
    path('case-escalation/tracker/',      views.case_escalation_tracker, name='case_escalation_tracker'),
    path('heatmap/',                      views.regional_heatmap,        name='heatmap'),

    path('officer-feedback/',             views.officer_feedback_list,   name='officer_feedback_list'),
    path('officer-feedback/add/',         views.officer_feedback_add,    name='officer_feedback_add'),
    path('officer-kpi/',                  views.officer_kpi,             name='officer_kpi'),

    path('regional-command/',             views.regional_command,        name='regional_command'),
    path('regional-access/',              views.regional_access,         name='regional_access'),


    path('detections/bulk/',              views.bulk_detections,         name='bulk_detections'),



    path('autocomplete/',                 autocomplete.autocomplete,     name='autocomplete'),
    path('check-duplicate/',              autocomplete.check_duplicate,  name='check_duplicate'),

    # --- Live monitoring & tracking ---
    path('live-monitor/',                 views.live_monitor,            name='live_monitor'),
    path('live-monitor/feed/',            views.live_monitor_feed,       name='live_monitor_feed'),
    path('live-tracking/timeline/',       officer_views.frame_timeline,  name='live_tracking_timeline'),

    # --- Banner management (views exist in dig_portal.views; routes were missing) ---
    path('banners/',                      views.banner_list,             name='banner_list'),
    path('banners/add/',                  views.banner_add,              name='banner_add'),
    path('banners/<int:banner_id>/edit/', views.banner_edit,             name='banner_edit'),
    path('banners/<int:banner_id>/delete/', views.banner_delete,         name='banner_delete'),

    # --- Camera management ---
    path('cameras/',                      views.camera_list,             name='camera_list'),
    path('cameras/list/',                 views.camera_list,             name='camera_list_alt'),
    path('cameras/add/',                  views.camera_add,              name='camera_add'),
    path('cameras/<int:camera_id>/edit/', views.camera_edit,             name='camera_edit'),
    path('cameras/<int:camera_id>/delete/', views.camera_delete,         name='camera_delete'),
    path('cameras/<int:camera_id>/toggle/', views.camera_toggle,        name='camera_toggle'),
    path('cameras/assignments/',          views.camera_assignments,      name='camera_assignments'),

    # --- Notifications inbox ---
    path('notifications/',                views.notifications,           name='notifications'),
    path('notifications/<int:notification_id>/read/', views.notification_read, name='notification_read'),

    # --- System ---
    path('settings/',                     views.settings_edit,           name='settings_edit'),
    path('system-health/',                views.system_health,           name='system_health'),
    path('payment-settings/',             views.payment_settings,        name='payment_settings'),


    path('live-tracking/', views.live_tracking, name='live_tracking'),

    path('live-tracking/ai-assist/', officer_views.ai_assist_frame, name='ai_assist_frame'),
    path('live-tracking/ocr-crop/', officer_views.ocr_plate_crop, name='ocr_plate_crop'),
    path('annotate/submit/', officer_views.submit_annotation, name='submit_annotation'),

    # --- Admin password reset (DIG-mediated flow) ---
    path('admin-resets/',                  views.admin_reset_request_list, name='admin_reset_request_list'),
    path('admin-resets/<str:token>/',      views.admin_reset_password,     name='admin_reset_password'),

    # --- JSON API endpoints (consumed by safe-city-charts.js / safe-city-tables.js) ---
    path('api/dashboard/kpis/',                views.api_dashboard_kpis,            name='api_dashboard_kpis'),
    path('api/charts/violation-distribution/', views.api_chart_violation_distribution, name='api_chart_violation_distribution'),
    path('api/charts/location-distribution/',  views.api_chart_location_distribution,  name='api_chart_location_distribution'),
    path('api/charts/activity-trend/',         views.api_chart_activity_trend,         name='api_chart_activity_trend'),
    path('api/charts/officer-kpi/',            views.api_chart_officer_kpi,            name='api_chart_officer_kpi'),
    path('api/tables/recent-detections/',      views.api_table_recent_detections,      name='api_table_recent_detections'),
]
