from django.urls import path
from . import views

app_name = 'realtime'
urlpatterns = [
    path('stats/', views.realtime_stats, name='stats'),
    path('cameras-status/', views.cameras_status_json, name='cameras_status'),
    path('queue-count/', views.queue_count, name='queue_count'),
    path('api/kpis/', views.api_dashboard_kpis, name='api_dashboard_kpis'),
    path('api/charts/violation-distribution/', views.api_charts_violation_distribution, name='api_charts_violation'),
    path('api/charts/revenue/', views.api_charts_revenue, name='api_charts_revenue'),
    path('api/tables/detections/', views.api_tables_detections, name='api_tables_detections'),
    path('api/live/recent-detections/', views.api_live_recent_detections, name='api_live_recent'),
    path('api/charts/activity-trend/', views.api_chart_activity_trend_shared, name='api_chart_activity_trend'),
    path('api/charts/violation-distribution-shared/', views.api_chart_violation_distribution_shared, name='api_chart_violation_distribution'),
    path('api/citizen/challans/', views.api_citizen_challans, name='api_citizen_challans'),
]

