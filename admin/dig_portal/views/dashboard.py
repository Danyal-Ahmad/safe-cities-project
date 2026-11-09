import datetime
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.conf import settings as dj_settings

from cameras.models import Camera
from challans.models import Challan
from appeals.models import ChallanAppeal
from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from detections.models import Detection
from django.http import JsonResponse
from accounts.models import User
from accounts.decorators import dig_required
from accounts.decorators import permission_required
from django.shortcuts import render
from accounts.decorators import role_required


@dig_required
def dashboard(request):
    from datetime import timedelta
    today = timezone.localdate()
    week_start = today - timedelta(days=7)
    total_today = Challan.objects.filter(issue_date=today).count()
    total_week = Challan.objects.filter(issue_date__gte=week_start).count()
    paid_today = Challan.objects.filter(issue_date=today, payment_status=Challan.PAID).count()
    revenue_collected = Challan.objects.filter(payment_status=Challan.PAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    revenue_today = Challan.objects.filter(issue_date=today, payment_status=Challan.PAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    revenue_pending = Challan.objects.filter(payment_status=Challan.UNPAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    active_cameras = Camera.objects.filter(is_active=True, is_streaming=True).count()
    online_cameras = Camera.objects.filter(health_status='online').count()
    pending_detections = Detection.objects.filter(status=Detection.PENDING).count()
    flagged_detections = Detection.objects.filter(status=Detection.FLAGGED).count()
    pending_appeals = ChallanAppeal.objects.filter(status=ChallanAppeal.PENDING).count()
    decided_appeals = ChallanAppeal.objects.exclude(status=ChallanAppeal.PENDING).count()
    total_users = User.objects.filter(role=User.USER).count()
    total_officers = User.objects.filter(role=User.OFFICER).count()

    by_type = Challan.objects.values('violation_type').annotate(c=Count('id')).order_by('-c')
    type_labels = [t['violation_type'] for t in by_type]
    type_counts = [t['c'] for t in by_type]
    max_type_count = max(type_counts) if type_counts else 1

    by_location = (Challan.objects.exclude(location__isnull=True).exclude(location='')
                   .values('location').annotate(c=Count('id')).order_by('-c')[:10])
    loc_labels = [l['location'] for l in by_location]
    loc_counts = [l['c'] for l in by_location]
    max_loc_count = max(loc_counts) if loc_counts else 1

    officers = User.objects.filter(role=User.OFFICER)
    officer_stats = []
    for off in officers:
        confirmed = Detection.objects.filter(reviewed_by=off, status=Detection.CONFIRMED).count()
        rejected = Detection.objects.filter(reviewed_by=off, status=Detection.REJECTED).count()
        pending = Detection.objects.filter(reviewed_by=off, status=Detection.PENDING).count()
        reviewed_qs = Detection.objects.filter(reviewed_by=off, status__in=[Detection.CONFIRMED, Detection.REJECTED])
        review_count = reviewed_qs.count()
        avg_review_hrs = 0
        valid = reviewed_qs.exclude(reviewed_at__isnull=True)
        if valid.exists():
            deltas = [(d.reviewed_at - d.created_at).total_seconds() / 3600
                      for d in valid if d.reviewed_at and d.created_at]
            if deltas:
                avg_review_hrs = round(sum(deltas) / len(deltas), 1)
        appeals = ChallanAppeal.objects.filter(reviewed_by=off).count()
        accuracy = round((confirmed / review_count * 100), 1) if review_count else 0.0
        officer_stats.append({
            'user': off, 'officer': off,
            'confirmed': confirmed, 'rejected': rejected, 'pending': pending,
            'reviewed': review_count, 'appeals': appeals,
            'avg_review_hrs': avg_review_hrs, 'accuracy': accuracy,
        })

    trend_daily = []
    for d in range(6, -1, -1):
        day = timezone.now() - timedelta(days=d)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        trend_daily.append({
            'date': day_start.strftime('%b %d'),
            'detections': Detection.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count(),
            'challans': Challan.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count(),
        })

    from admin.dig_portal.models import Alert
    active_alerts = list(
        Alert.objects.filter(is_active=True).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).order_by('-created_at')[:5]
    )

    pending_appeals_recent = list(
        ChallanAppeal.objects.filter(status=ChallanAppeal.PENDING)
        .select_related('challan', 'submitted_by').order_by('-created_at')[:5]
    )
    recent_detections = list(
        Detection.objects.select_related('camera').order_by('-created_at')[:10]
    )

    return render(request, 'dashboard/dig/dashboard.html', {
        'total_today': total_today, 'total_week': total_week, 'paid_today': paid_today,
        'revenue_collected': revenue_collected, 'revenue_today': revenue_today, 'revenue_pending': revenue_pending,
        'active_cameras': active_cameras, 'online_cameras': online_cameras,
        'pending_detections': pending_detections, 'flagged_detections': flagged_detections,
        'pending_appeals': pending_appeals, 'decided_appeals': decided_appeals,
        'pending_appeals_recent': pending_appeals_recent,
        'recent_detections': recent_detections,
        'total_users': total_users, 'total_officers': total_officers,
        'type_labels': type_labels, 'type_counts': type_counts, 'max_type_count': max_type_count,
        'loc_labels': loc_labels, 'loc_counts': loc_counts, 'max_loc_count': max_loc_count,
        'officer_stats': officer_stats, 'officers': officers,
        'active_alerts': active_alerts, 'trend_daily': trend_daily,
    })


@dig_required
@require_GET
def api_dashboard_kpis(request):
    from datetime import timedelta
    today = timezone.localdate()
    week_start = today - timedelta(days=7)
    month_start = today - timedelta(days=30)
    return JsonResponse({
        'ts': int(timezone.now().timestamp()),
        'kpis': {
            'total_today': Challan.objects.filter(issue_date=today).count(),
            'total_week': Challan.objects.filter(issue_date__gte=week_start).count(),
            'total_month': Challan.objects.filter(issue_date__gte=month_start).count(),
            'paid_today': Challan.objects.filter(issue_date=today, payment_status=Challan.PAID).count(),
            'paid_month': Challan.objects.filter(issue_date__gte=month_start, payment_status=Challan.PAID).count(),
            'revenue_collected': float(
                Challan.objects.filter(payment_status=Challan.PAID)
                .aggregate(t=Sum('fine_amount'))['t'] or 0
            ),
            'revenue_today': float(
                Challan.objects.filter(issue_date=today, payment_status=Challan.PAID)
                .aggregate(t=Sum('fine_amount'))['t'] or 0
            ),
            'revenue_pending': float(
                Challan.objects.filter(payment_status=Challan.UNPAID)
                .aggregate(t=Sum('fine_amount'))['t'] or 0
            ),
            'active_cameras': Camera.objects.filter(is_active=True, is_streaming=True).count(),
            'online_cameras': Camera.objects.filter(health_status='online').count(),
            'total_cameras': Camera.objects.filter(is_active=True).count(),
            'pending_detections': Detection.objects.filter(status=Detection.PENDING).count(),
            'flagged_detections': Detection.objects.filter(status=Detection.FLAGGED).count(),
            'pending_appeals': ChallanAppeal.objects.filter(status=ChallanAppeal.PENDING).count(),
            'decided_appeals': ChallanAppeal.objects.exclude(status=ChallanAppeal.PENDING).count(),
            'total_users': User.objects.filter(role=User.USER).count(),
            'total_officers': User.objects.filter(role=User.OFFICER).count(),
            'active_alerts': Alert.objects.filter(is_active=True)
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).count(),
        },
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
@require_GET
def api_chart_violation_distribution(request):
    try:
        days = max(1, min(180, int(request.GET.get('days', 30))))
    except (TypeError, ValueError):
        days = 30
    since = timezone.now() - datetime.timedelta(days=days)
    rows = (
        Challan.objects.filter(issue_date__gte=since.date())
        .values('violation_type')
        .annotate(c=Count('id'))
        .order_by('-c')
    )
    labels = [r['violation_type'] or 'Unknown' for r in rows]
    counts = [r['c'] for r in rows]
    return JsonResponse({
        'labels': labels,
        'datasets': [{
            'label': 'Violations',
            'data': counts,
            'backgroundColor': '#0a1a3a',
            'borderColor': '#0a1a3a',
        }],
        'meta': {'days': days, 'total': sum(counts)},
    })


@dig_required
@permission_required('view_analytics')
@require_GET
def api_chart_location_distribution(request):
    rows = (
        Challan.objects.exclude(location__isnull=True).exclude(location='')
        .values('location').annotate(c=Count('id')).order_by('-c')[:10]
    )
    return JsonResponse({
        'labels': [r['location'] for r in rows],
        'datasets': [{
            'label': 'Challans',
            'data': [r['c'] for r in rows],
            'backgroundColor': '#dc2626',
        }],
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
@require_GET
def api_chart_activity_trend(request):
    from datetime import timedelta
    rows = []
    for d in range(6, -1, -1):
        day = timezone.now() - timedelta(days=d)
        ds = day.replace(hour=0, minute=0, second=0, microsecond=0)
        de = ds + timedelta(days=1)
        rows.append({
            'date': ds.strftime('%b %d'),
            'detections': Detection.objects.filter(created_at__gte=ds, created_at__lt=de).count(),
            'challans': Challan.objects.filter(created_at__gte=ds, created_at__lt=de).count(),
        })
    return JsonResponse({
        'labels': [r['date'] for r in rows],
        'datasets': [
            {'label': 'Detections', 'data': [r['detections'] for r in rows], 'borderColor': '#0a1a3a', 'backgroundColor': 'rgba(10,26,58,0.15)', 'tension': 0.3, 'fill': True},
            {'label': 'Challans',   'data': [r['challans']   for r in rows], 'borderColor': '#dc2626', 'backgroundColor': 'rgba(220,38,38,0.15)', 'tension': 0.3, 'fill': True},
        ],
    })


@dig_required
@permission_required('view_detections')
@require_GET
def api_table_recent_detections(request):
    try:
        draw   = int(request.GET.get('draw', 1))
        start  = int(request.GET.get('start', 0))
        length = max(1, min(200, int(request.GET.get('length', 25))))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid DataTables params'}, status=400)

    qs = Detection.objects.select_related('camera').order_by('-created_at')
    total = qs.count()
    qs = qs[start:start + length]
    data = [{
        'id':         d.id,
        'camera':     d.camera.camera_id if d.camera else (f'#{d.camera_id}' if d.camera_id else '-'),
        'plate':      d.effective_plate or '-',
        'confidence': round(float(d.ai_confidence or 0) * 100, 1),
        'status':     d.get_status_display(),
        'created_at': d.created_at.strftime('%Y-%m-%d %H:%M'),
    } for d in qs]
    return JsonResponse({
        'draw':            draw,
        'recordsTotal':    total,
        'recordsFiltered': total,
        'data':            data,
    })


@dig_required
@require_GET
def api_chart_officer_kpi(request):
    rows = (
        Detection.objects.filter(reviewed_by__isnull=False)
        .values('reviewed_by__username')
        .annotate(
            confirmed=Count('id', filter=Q(status=Detection.CONFIRMED)),
            rejected=Count('id', filter=Q(status=Detection.REJECTED)),
        )
        .order_by('-confirmed')[:10]
    )
    labels = [r['reviewed_by__username'] or 'Officer' for r in rows]
    return JsonResponse({
        'labels': labels,
        'datasets': [
            {'label': 'Confirmed', 'data': [r['confirmed'] for r in rows], 'backgroundColor': '#16a34a'},
            {'label': 'Rejected',  'data': [r['rejected']  for r in rows], 'backgroundColor': '#dc2626'},
        ],
    })

