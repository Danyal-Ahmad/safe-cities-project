import datetime
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

from accounts.decorators import officer_or_dig_required, dig_required, staff_required
from cameras.models import Camera
from detections.models import Detection
from challans.models import Challan
from appeals.models import ChallanAppeal


@officer_or_dig_required
def realtime_stats(request):
    today = timezone.localdate()
    return JsonResponse({
        'total_today': Detection.objects.filter(created_at__date=today).count(),
        'pending': Detection.objects.filter(status=Detection.PENDING).count(),
        'flagged': Detection.objects.filter(status=Detection.FLAGGED).count(),
        'online_cameras': Camera.objects.filter(health_status='online', is_active=True).count(),
        'active_cameras': Camera.objects.filter(is_active=True, is_streaming=True).count(),
        'unpaid_challans': Challan.objects.filter(payment_status=Challan.UNPAID).count(),
        'ts': timezone.now().isoformat(),
    })


@officer_or_dig_required
def cameras_status_json(request):
    qs = Camera.objects.filter(is_active=True).order_by('camera_id')
    return JsonResponse({
        'cameras': [{
            'id': c.id, 'camera_id': c.camera_id, 'location': c.location,
            'health': c.health_status, 'streaming': c.is_streaming,
            'last_frame_at': c.last_frame_at.isoformat() if c.last_frame_at else None,
        } for c in qs[:50]],
    })


@officer_or_dig_required
def queue_count(request):
    return JsonResponse({
        'count': Detection.objects.filter(status=Detection.PENDING).count(),
    })


@require_GET
@login_required
def api_dashboard_kpis(request):
    role = getattr(request.user, 'role', 'USER')
    today = timezone.localdate()
    if role == 'DIG':
        return JsonResponse({
            'role': 'DIG',
            'kpis': [
                {'label': 'Challans today', 'value': Challan.objects.filter(issue_date=today).count(), 'icon': 'bi-receipt'},
                {'label': 'Paid today', 'value': Challan.objects.filter(issue_date=today, payment_status=Challan.PAID).count(), 'icon': 'bi-check-circle', 'color': 'ok'},
                {'label': 'Revenue collected', 'value': float(Challan.objects.filter(payment_status=Challan.PAID).aggregate(t=Sum('fine_amount'))['t'] or 0), 'icon': 'bi-cash-stack', 'color': 'ok', 'prefix': 'PKR '},
                {'label': 'Revenue pending', 'value': float(Challan.objects.filter(payment_status=Challan.UNPAID).aggregate(t=Sum('fine_amount'))['t'] or 0), 'icon': 'bi-hourglass-split', 'color': 'warn', 'prefix': 'PKR '},
                {'label': 'Active cameras', 'value': Camera.objects.filter(is_active=True, is_streaming=True).count(), 'icon': 'bi-camera-video'},
                {'label': 'Online cameras', 'value': Camera.objects.filter(health_status='online').count(), 'icon': 'bi-broadcast', 'color': 'ok'},
                {'label': 'Pending detections', 'value': Detection.objects.filter(status=Detection.PENDING).count(), 'icon': 'bi-hourglass-split', 'color': 'warn'},
                {'label': 'Flagged', 'value': Detection.objects.filter(status=Detection.FLAGGED).count(), 'icon': 'bi-flag-fill', 'color': 'err'},
            ],
        })
    elif role in ('IT', 'IT_SUPPORT'):
        return JsonResponse({
            'role': 'IT',
            'kpis': [
                {'label': 'Cameras', 'value': Camera.objects.count(), 'icon': 'bi-camera-fill'},
                {'label': 'Online', 'value': Camera.objects.filter(health_status='online').count(), 'icon': 'bi-broadcast', 'color': 'ok'},
                {'label': 'Active Streams', 'value': Camera.objects.filter(is_streaming=True).count(), 'icon': 'bi-broadcast-pin', 'color': 'ok'},
                {'label': 'Detections', 'value': Detection.objects.count(), 'icon': 'bi-eye'},
                {'label': 'Pending', 'value': Detection.objects.filter(status=Detection.PENDING).count(), 'icon': 'bi-hourglass-split', 'color': 'warn'},
                {'label': 'Challans', 'value': Challan.objects.count(), 'icon': 'bi-receipt'},
            ],
        })
    elif role == 'OFFICER':
        return JsonResponse({
            'role': 'OFFICER',
            'kpis': [
                {'label': 'Queue', 'value': Detection.objects.filter(status=Detection.PENDING).count(), 'icon': 'bi-inbox', 'color': 'warn'},
                {'label': 'Confirmed by you', 'value': Detection.objects.filter(status=Detection.CONFIRMED, reviewed_by=request.user).count(), 'icon': 'bi-check2-circle', 'color': 'ok'},
                {'label': 'Flagged', 'value': Detection.objects.filter(status=Detection.FLAGGED).count(), 'icon': 'bi-flag-fill', 'color': 'err'},
                {'label': 'My appeals', 'value': ChallanAppeal.objects.filter(challan__created_by=request.user).count(), 'icon': 'bi-shield-fill'},
            ],
        })
    else:  
        return JsonResponse({'role': role, 'kpis': []})


@require_GET
@dig_required
def api_charts_violation_distribution(request):
    days = int(request.GET.get('days', 30))
    since = timezone.now() - datetime.timedelta(days=days)
    qs = (Detection.objects
          .filter(created_at__gte=since, status=Detection.CONFIRMED)[:1000])
    counts = {}
    for d in qs:
        v = d.effective_violation_type or 'other'
        counts[v] = counts.get(v, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    return JsonResponse({
        'labels': [v for v, _ in ordered],
        'counts': [c for _, c in ordered],
    })


@require_GET
@dig_required
def api_charts_revenue(request):
    days = int(request.GET.get('days', 14))
    out = []
    for d in range(days - 1, -1, -1):
        day = timezone.localdate() - datetime.timedelta(days=d)
        amount = Challan.objects.filter(issue_date=day, payment_status=Challan.PAID).aggregate(t=Sum('fine_amount'))['t'] or 0
        out.append({'date': day.isoformat(), 'amount': float(amount)})
    return JsonResponse({
        'series': out,
        'labels': [x['date'] for x in out],
        'revenues': [x['amount'] for x in out],
    })


@require_GET
@dig_required
def api_tables_detections(request):
    qs = Detection.objects.select_related('camera').order_by('-created_at')
    plate = request.GET.get('plate', '').strip().upper()
    status = request.GET.get('status', '').strip()
    if plate:
        qs = qs.filter(ai_plate_text__icontains=plate)
    if status:
        qs = qs.filter(status=status)
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))
    total = qs.count()
    rows = qs[start:start + length]
    return JsonResponse({
        'draw': int(request.GET.get('draw', 1)),
        'recordsTotal': Detection.objects.count(),
        'recordsFiltered': total,
        'data': [{
            'id': d.id,
            'plate': d.effective_plate or '',
            'camera': d.camera.camera_id if d.camera else '',
            'status': d.get_status_display(),
            'violation': d.effective_violation_type or '',
            'confidence': round(d.ai_confidence or 0, 2),
            'created_at': d.created_at.isoformat(),
        } for d in rows],
    })


@require_GET
@staff_required
def api_live_recent_detections(request):
    camera_id = request.GET.get('camera_id', '').strip()
    limit = int(request.GET.get('limit', 30))
    qs = Detection.objects.order_by('-created_at')
    if camera_id:
        qs = qs.filter(camera__camera_id=camera_id)
    qs = qs[:limit]
    return JsonResponse({
        'items': [{
            'id': d.id,
            'plate': d.effective_plate or '',
            'camera': d.camera.camera_id if d.camera else '',
            'status': d.status,
            'confidence': round(d.ai_confidence or 0, 2),
            'bbox': None,
            'created_at': d.created_at.isoformat(),
            'thumb_url': d.raw_image.url if d.raw_image else None,
        } for d in qs],
        'ts': timezone.now().isoformat(),
    })


@require_GET
@login_required
def api_citizen_challans(request):
    from django.db.models import Q
    user = request.user
    qs = Challan.objects.filter(
        Q(cnic=user.cnic) | Q(phone=user.phone)
    ).order_by('-issue_date')
    return JsonResponse({
        'items': [{
            'id': c.id,
            'ticket_no': c.ticket_no,
            'plate': c.plate_number,
            'fine': float(c.fine_amount or 0),
            'status': c.get_payment_status_display(),
            'paid': c.payment_status == Challan.PAID,
            'issue_date': c.issue_date.isoformat(),
            'due_date': c.due_date.isoformat(),
        } for c in qs],
    })


@require_GET
@staff_required
def api_chart_activity_trend_shared(request):
    from datetime import timedelta as _td
    from challans.models import Challan
    rows = []
    for d in range(6, -1, -1):
        day = timezone.now() - _td(days=d)
        ds = day.replace(hour=0, minute=0, second=0, microsecond=0)
        de = ds + _td(days=1)
        rows.append({
            'date': ds.strftime('%b %d'),
            'detections': Detection.objects.filter(created_at__gte=ds, created_at__lt=de).count(),
            'challans': Challan.objects.filter(created_at__gte=ds, created_at__lt=de).count(),
        })
    return JsonResponse({
        'labels': [r['date'] for r in rows],
        'datasets': [
            {'label': 'Detections', 'data': [r['detections'] for r in rows], 'borderColor': '#0a1a3a', 'backgroundColor': 'rgba(10,26,58,0.15)', 'tension': 0.3, 'fill': True},
            {'label': 'Challans', 'data': [r['challans'] for r in rows], 'borderColor': '#dc2626', 'backgroundColor': 'rgba(220,38,38,0.15)', 'tension': 0.3, 'fill': True},
        ],
    })


@require_GET
@staff_required
def api_chart_violation_distribution_shared(request):
    from django.db.models import Count as _Count
    from challans.models import Challan
    try:
        days = max(1, min(180, int(request.GET.get('days', 30))))
    except (TypeError, ValueError):
        days = 30
    since = timezone.now() - datetime.timedelta(days=days)
    rows = (
        Challan.objects.filter(issue_date__gte=since.date())
        .values('violation_type').annotate(c=_Count('id')).order_by('-c')
    )
    labels = [dict(Challan.VIOLATION_CHOICES).get(r['violation_type'], r['violation_type']) for r in rows]
    return JsonResponse({
        'labels': labels,
        'datasets': [{
            'label': 'Challans',
            'data': [r['c'] for r in rows],
            'backgroundColor': '#dc2626',
        }],
    })
