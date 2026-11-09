import csv
import datetime
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.conf import settings as dj_settings

from cameras.models import Camera
from challans.models import Challan
from appeals.models import ChallanAppeal
from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from detections.models import Detection
from django.http import HttpResponse
from accounts.models import User
from accounts.decorators import dig_required
from django.shortcuts import redirect
from django.shortcuts import render
from accounts.decorators import role_required
from accounts.decorators import senior_staff_required


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
def analytics(request):
    qs = Challan.objects.all()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from: qs = qs.filter(issue_date__gte=date_from)
    if date_to: qs = qs.filter(issue_date__lte=date_to)
    vt_data = []
    vt_css_map = {
        Challan.WRONG_WAY: 'wrong-way', Challan.NO_HELMET: 'no-helmet',
        Challan.SIGNAL_BREAK: 'signal-break', Challan.OVER_SPEED: 'over-speed',
        Challan.OTHER: 'other',
    }
    vt_max = 0
    for code, label in Challan.VIOLATION_CHOICES:
        cnt = qs.filter(violation_type=code).count()
        if cnt > vt_max:
            vt_max = cnt
        vt_data.append({'code': code, 'label': label, 'count': cnt, 'css_class': vt_css_map.get(code, 'other')})
    for vt in vt_data:
        vt['pct'] = round(vt['count'] / vt_max * 100) if vt_max > 0 else 0

    today = timezone.localdate()
    trend_labels = []
    trend_data = []
    for i in range(29, -1, -1):
        d = today - datetime.timedelta(days=i)
        trend_labels.append(d.strftime('%d %b'))
        trend_data.append(qs.filter(issue_date=d).count())
    month_start = today.replace(day=1)
    top_locations = list(
        qs.exclude(location__isnull=True).exclude(location='')
        .values('location').annotate(c=Count('id')).order_by('-c')[:10]
    )
    return render(request, 'dashboard/dig/analytics.html', {
        'total': qs.count(),
        'paid': qs.filter(payment_status=Challan.PAID).count(),
        'unpaid': qs.filter(payment_status=Challan.UNPAID).count(),
        'voided': qs.filter(payment_status=Challan.VOIDED).count(),
        'total_revenue': qs.filter(payment_status=Challan.PAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0,
        'pending_revenue': qs.filter(payment_status=Challan.UNPAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0,
        'this_month': Challan.objects.filter(issue_date__gte=month_start).count(),
        'pending_review': Detection.objects.filter(status=Detection.PENDING).count(),
        'confirmed': Detection.objects.filter(status=Detection.CONFIRMED).count(),
        'trend_labels': trend_labels,
        'trend_data': trend_data,
        'type_labels': [vt['label'] for vt in vt_data],
        'type_counts': [vt['count'] for vt in vt_data],
        'top_locations': top_locations,
        'date_from': date_from, 'date_to': date_to,
        'violation_types': vt_data,
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
def revenue_dashboard(request):
    today = timezone.localdate()
    periods = {
        'Today': Challan.objects.filter(issue_date=today),
        'This Week': Challan.objects.filter(issue_date__gte=today - datetime.timedelta(days=7)),
        'This Month': Challan.objects.filter(issue_date__gte=today - datetime.timedelta(days=30)),
        'This Year': Challan.objects.filter(issue_date__gte=today - datetime.timedelta(days=365)),
        'All Time': Challan.objects.all(),
    }
    summary = []
    for label, qs in periods.items():
        collected = qs.filter(payment_status=Challan.PAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0
        pending = qs.filter(payment_status=Challan.UNPAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0
        summary.append({'period': label, 'collected': collected, 'pending': pending,
                        'total': collected + pending, 'challans': qs.count()})
    daily = []
    daily_labels = []
    daily_collected = []
    daily_pending = []
    for i in range(13, -1, -1):
        d = today - datetime.timedelta(days=i)
        qs = Challan.objects.filter(issue_date=d)
        day_collected = qs.filter(payment_status=Challan.PAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0
        day_pending = qs.filter(payment_status=Challan.UNPAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0
        daily.append({
            'date': d,
            'collected': day_collected,
            'pending': day_pending,
            'count': qs.count(),
        })
        daily_labels.append(d.strftime('%d %b'))
        daily_collected.append(day_collected)
        daily_pending.append(day_pending)
    max_daily = max([d['collected'] + d['pending'] for d in daily] or [1])
    collected_total = Challan.objects.filter(payment_status=Challan.PAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0
    pending_total = Challan.objects.filter(payment_status=Challan.UNPAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0
    overdue_total = Challan.objects.filter(payment_status=Challan.UNPAID, due_date__lt=today).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0
    month_start = today.replace(day=1)
    this_month = Challan.objects.filter(payment_status=Challan.PAID, paid_at__date__gte=month_start).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0
    status_rows = Challan.objects.values('payment_status').annotate(c=Count('id'))
    status_map = {row['payment_status']: row['c'] for row in status_rows}
    return render(request, 'dashboard/dig/revenue_dashboard.html', {
        'summary': summary, 'daily': daily, 'max_daily': max_daily,
        'collected': collected_total, 'pending': pending_total,
        'overdue': overdue_total, 'this_month': this_month,
        'daily_labels': daily_labels, 'daily_collected': daily_collected, 'daily_pending': daily_pending,
        'status_labels': ['Paid', 'Unpaid', 'Voided'],
        'status_counts': [status_map.get(Challan.PAID, 0), status_map.get(Challan.UNPAID, 0), status_map.get(Challan.VOIDED, 0)],
    })


def _report_queryset(kind, date_from=None, date_to=None, camera_id=None,
                     violation_type=None, officer_id=None):
    qs = Challan.objects.all().order_by('-issue_date')
    if kind in ('financial', 'revenue'):
        qs = qs.filter(payment_status=Challan.PAID)
    if date_from:
        try:
            qs = qs.filter(issue_date__gte=datetime.date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            qs = qs.filter(issue_date__lte=datetime.date.fromisoformat(date_to))
        except ValueError:
            pass
    if camera_id:
        qs = qs.filter(camera_id=camera_id)
    if violation_type:
        qs = qs.filter(violation_type=violation_type)
    if officer_id:
        qs = qs.filter(created_by_id=officer_id)
    return qs


def _challan_csv_response(qs):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="safecity_challan_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Ticket', 'Plate', 'Owner', 'Violation', 'Amount', 'Issue Date', 'Due Date', 'Status', 'Location'])
    for c in qs[:10000]:
        writer.writerow([
            c.ticket_no, c.plate_number, c.owner_name or '',
            c.get_violation_type_display(), c.fine_amount, c.issue_date,
            c.due_date, c.payment_status, c.location or '',
        ])
    return response


def _challan_pdf_response(qs):
    rows = []
    for c in qs[:2000]:
        rows.append(
            f"<tr><td>{c.ticket_no}</td><td>{c.plate_number}</td>"
            f"<td>{c.get_violation_type_display()}</td><td>{c.fine_amount}</td>"
            f"<td>{c.issue_date}</td><td>{c.payment_status}</td></tr>"
        )
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>SAFE CITIES PROJECT Challan Report</title>"
        "<style>body{font-family:Arial,sans-serif;font-size:11px;margin:24px}"
        "h1{font-size:18px}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ccc;padding:6px;text-align:left}"
        "th{background:#f1f5f9}@media print{body{margin:0}}</style></head><body>"
        "<h1>SAFE CITIES PROJECT | Challan Report</h1>"
        f"<p>Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')} · Rows: {len(rows)}</p>"
        "<table><thead><tr><th>Ticket</th><th>Plate</th><th>Violation</th>"
        "<th>Amount</th><th>Issued</th><th>Status</th></tr></thead><tbody>"
        + "".join(rows) +
        "</tbody></table>"
        "<script>window.onload=function(){window.print();}</script>"
        "</body></html>"
    )
    response = HttpResponse(html, content_type='text/html; charset=utf-8')
    response['Content-Disposition'] = 'inline; filename="safecity_challan_report.pdf.html"'
    return response


def _log_report_generation(request, title, kind, fmt, qs, params):
    AuditLog.write(
        request, 'report.generate', 'Challan', None,
        title=title, kind=kind, format=fmt, rows=qs.count(), **params
    )


@dig_required
def generate_report(request):
    cameras = Camera.objects.filter(is_active=True).order_by('camera_id')
    officers = User.objects.filter(role=User.OFFICER, is_active=True).order_by('first_name', 'username')

    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        kind = (request.POST.get('type') or 'violations').strip().lower()
        fmt = (request.POST.get('format') or 'csv').strip().lower()
        date_from = (request.POST.get('start_date') or '').strip()
        date_to = (request.POST.get('end_date') or '').strip()
        camera_id = (request.POST.get('camera_id') or '').strip()
        violation_type = (request.POST.get('violation_type') or '').strip()
        officer_id = (request.POST.get('officer_id') or '').strip()
        if not title:
            messages.error(request, "Report title is required.")
            return redirect('dig:generate_report')
        if not date_from or not date_to:
            messages.error(request, "Start and end dates are required.")
            return redirect('dig:generate_report')
        try:
            start = datetime.date.fromisoformat(date_from)
            end = datetime.date.fromisoformat(date_to)
        except ValueError:
            messages.error(request, "Invalid date range.")
            return redirect('dig:generate_report')
        if end < start:
            messages.error(request, "End date must be on or after the start date.")
            return redirect('dig:generate_report')
        if fmt not in ('csv', 'pdf', 'excel'):
            fmt = 'csv'
        qs = _report_queryset(kind, date_from, date_to, camera_id, violation_type, officer_id)
        _log_report_generation(request, title, kind, fmt, qs, {
            'start_date': date_from, 'end_date': date_to,
            'camera': camera_id or 'all', 'violation': violation_type or 'all',
            'officer': officer_id or 'all',
        })
        messages.success(request, f"Report '{title}' generated ({qs.count()} rows).")
        if fmt == 'pdf':
            return _challan_pdf_response(qs)
        return _challan_csv_response(qs)

    fmt = (request.GET.get('format') or '').lower()
    kind = (request.GET.get('kind') or 'all').lower()
    if fmt in ('csv', 'pdf'):
        date_from = (request.GET.get('date_from') or '').strip()
        date_to = (request.GET.get('date_to') or '').strip()
        camera_id = (request.GET.get('camera_id') or '').strip()
        violation_type = (request.GET.get('violation_type') or '').strip()
        officer_id = (request.GET.get('officer_id') or '').strip()
        qs = _report_queryset(kind, date_from, date_to, camera_id, violation_type, officer_id)
        _log_report_generation(request, f"Challan report ({kind})", kind, fmt, qs, {
            'start_date': date_from or 'all', 'end_date': date_to or 'all',
            'camera': camera_id or 'all', 'violation': violation_type or 'all',
            'officer': officer_id or 'all',
        })
        if fmt == 'csv':
            return _challan_csv_response(qs)
        return _challan_pdf_response(qs)

    return render(request, 'dashboard/dig/generate_report.html', {
        'cameras': cameras,
        'officers': officers,
        'violation_types': Challan.VIOLATION_CHOICES,
        'selected_type': request.GET.get('type') or '',
    })


@senior_staff_required
def reports(request):
    generations = (AuditLog.objects.filter(action='report.generate')
                   .select_related('actor')[:50])
    rows = []
    for g in generations:
        details = g.details if isinstance(g.details, dict) else {}
        params = {}
        if details.get('start_date') and details.get('start_date') != 'all':
            params['date_from'] = details.get('start_date')
        if details.get('end_date') and details.get('end_date') != 'all':
            params['date_to'] = details.get('end_date')
        kind = details.get('kind') or 'all'
        if kind in ('financial', 'revenue'):
            params['kind'] = 'financial'
        redownload = ''
        if params:
            from urllib.parse import urlencode
            params['format'] = 'csv'
            redownload = reverse('dig:generate_report') + '?' + urlencode(params)
        rows.append({
            'log': g,
            'title': details.get('title') or 'Challan report',
            'kind': kind,
            'format': details.get('format') or 'csv',
            'rows_count': details.get('rows'),
            'redownload': redownload,
        })
    return render(request, 'dashboard/dig/reports.html', {'reports': rows})


@dig_required
def operational_reports(request):
    today = timezone.localdate()
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)
    periods = []
    for key, label, qs in (
        ('daily', 'Today', Challan.objects.filter(issue_date=today)),
        ('weekly', 'Last 7 Days', Challan.objects.filter(issue_date__gte=week_ago)),
        ('monthly', 'Last 30 Days', Challan.objects.filter(issue_date__gte=month_ago)),
    ):
        collected = qs.filter(payment_status=Challan.PAID).aggregate(total=Sum('fine_amount'))['total'] or 0
        pending = qs.filter(payment_status=Challan.UNPAID).aggregate(total=Sum('fine_amount'))['total'] or 0
        periods.append({
            'key': key, 'label': label,
            'challans': qs.count(),
            'paid': qs.filter(payment_status=Challan.PAID).count(),
            'unpaid': qs.filter(payment_status=Challan.UNPAID).count(),
            'collected': collected, 'pending': pending,
        })
    active_type = request.GET.get('type', 'daily')
    if active_type not in ('daily', 'weekly', 'monthly'):
        active_type = 'daily'
    active = next((p for p in periods if p['key'] == active_type), periods[0])
    recent_generations = (AuditLog.objects.filter(action='report.generate')
                          .exclude(details__kind__in=['revenue', 'financial'])
                          .select_related('actor')[:20])
    return render(request, 'dashboard/dig/operational_reports.html', {
        'periods': periods, 'active': active, 'active_type': active_type,
        'daily': periods[0]['challans'], 'weekly': periods[1]['challans'], 'monthly': periods[2]['challans'],
        'detections_today': Detection.objects.filter(created_at__date=today).count(),
        'recent_generations': recent_generations,
    })


@dig_required
def financial_reports(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    collected = Challan.objects.filter(payment_status=Challan.PAID).aggregate(total=Sum('fine_amount'))['total'] or 0
    pending = Challan.objects.filter(payment_status=Challan.UNPAID).aggregate(total=Sum('fine_amount'))['total'] or 0
    overdue = Challan.objects.filter(payment_status=Challan.UNPAID, due_date__lt=today).aggregate(total=Sum('fine_amount'))['total'] or 0
    this_month = Challan.objects.filter(paid_at__date__gte=month_start, payment_status=Challan.PAID).aggregate(total=Sum('fine_amount'))['total'] or 0
    billed = collected + pending
    collection_rate = round(collected / billed * 100, 1) if billed else 0

    month_labels = []
    month_collected = []
    month_pending = []
    year, month = today.year, today.month
    for i in range(5, -1, -1):
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        start = datetime.date(y, m, 1)
        nxt = datetime.date(y + 1, 1, 1) if m == 12 else datetime.date(y, m + 1, 1)
        paid_sum = Challan.objects.filter(payment_status=Challan.PAID, paid_at__date__gte=start, paid_at__date__lt=nxt).aggregate(total=Sum('fine_amount'))['total'] or 0
        unpaid_sum = Challan.objects.filter(payment_status=Challan.UNPAID, issue_date__gte=start, issue_date__lt=nxt).aggregate(total=Sum('fine_amount'))['total'] or 0
        month_labels.append(start.strftime('%b %Y'))
        month_collected.append(paid_sum)
        month_pending.append(unpaid_sum)

    method_rows = (Challan.objects.filter(payment_status=Challan.PAID)
                   .exclude(payment_method__isnull=True).exclude(payment_method='')
                   .values('payment_method').annotate(c=Count('id'), total=Sum('fine_amount'))
                   .order_by('-total')[:8])
    return render(request, 'dashboard/dig/financial_reports.html', {
        'collected': collected, 'pending': pending, 'overdue': overdue,
        'this_month': this_month, 'collection_rate': collection_rate,
        'month_labels': month_labels, 'month_collected': month_collected, 'month_pending': month_pending,
        'method_rows': method_rows,
    })


@dig_required
def regional_command(request):
    city_names = ['Lahore', 'Rawalpindi', 'Faisalabad', 'Multan', 'Gujranwala']

    def _derive_region(value):
        value = (value or '').strip()
        if not value:
            return 'Unassigned'
        for city in city_names:
            if city.lower() in value.lower():
                return city
        return value.split(',')[0].strip() or 'Unassigned'

    region_names = []
    for loc in (Camera.objects.exclude(location__isnull=True).exclude(location='')
                .values_list('location', flat=True).distinct()):
        region = _derive_region(loc)
        if region not in region_names:
            region_names.append(region)
    for user_region in (User.objects.exclude(region__isnull=True).exclude(region='')
                        .values_list('region', flat=True).distinct()):
        region = _derive_region(user_region)
        if region not in region_names:
            region_names.append(region)

    today = timezone.localdate()
    window_start = today - datetime.timedelta(days=30)
    regions = []
    for name in region_names:
        cam_qs = Camera.objects.filter(location__icontains=name)
        challan_qs = Challan.objects.filter(location__icontains=name, issue_date__gte=window_start)
        revenue = challan_qs.filter(payment_status=Challan.PAID).aggregate(total=Sum('fine_amount'))['total'] or 0
        regions.append({
            'name': name,
            'cameras': cam_qs.filter(is_active=True).count(),
            'cameras_online': cam_qs.filter(health_status='online').count(),
            'challans_30d': challan_qs.count(),
            'revenue_30d': revenue,
            'officers': User.objects.filter(role=User.OFFICER, region__icontains=name).count(),
            'ssps': User.objects.filter(role=User.SSP, region__icontains=name).count(),
        })
    regions.sort(key=lambda r: (-r['challans_30d'], -r['cameras'], r['name']))

    all_cam = Camera.objects.filter(is_active=True).count()
    all_online = Camera.objects.filter(health_status='online').count()
    all_viol = Challan.objects.count()
    all_officers = User.objects.filter(role=User.OFFICER).count()
    return render(request, 'dashboard/dig/regional_command.html', {
        'regions': regions,
        'total_cameras': all_cam, 'total_online': all_online,
        'total_violations': all_viol, 'total_officers': all_officers,
    })


@dig_required
def compliance(request):
    pending_reviews = Detection.objects.filter(status=Detection.PENDING).count()
    total_challans = Challan.objects.count()
    total_appeals = ChallanAppeal.objects.count()
    audit_entries = AuditLog.objects.count()
    return render(request, 'dashboard/dig/compliance.html', {
        'pending_reviews': pending_reviews, 'total_challans': total_challans,
        'total_appeals': total_appeals, 'audit_entries': audit_entries,
    })


@role_required('DIG', 'AUDIT', 'IT')
def operational_audit(request):
    recent_audit = AuditLog.objects.all().order_by('-timestamp')[:50]
    officer_activity = User.objects.filter(role=User.OFFICER).annotate(
        review_count=Count('reviewed_detections', filter=Q(reviewed_detections__status__in=['confirmed', 'rejected']))
    ).order_by('-review_count')[:20]
    return render(request, 'dashboard/dig/operational_audit.html', {
        'recent_audit': recent_audit, 'officer_activity': officer_activity,
    })


@role_required('DIG', 'AUDIT', 'IT')
def financial_audit(request):
    total_collected = Challan.objects.filter(payment_status=Challan.PAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    total_pending = Challan.objects.filter(payment_status=Challan.UNPAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    total_voided = Challan.objects.filter(payment_status=Challan.VOIDED).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    recent_payments = Challan.objects.filter(payment_status=Challan.PAID).order_by('-paid_at')[:30]
    return render(request, 'dashboard/dig/financial_audit.html', {
        'total_collected': total_collected, 'total_pending': total_pending,
        'total_voided': total_voided, 'recent_payments': recent_payments,
    })


@role_required('DIG', 'SSP')
def regional_heatmap(request):
    import json
    from cameras.models import Camera

    CITY_GEO = {
        'gulberg': (31.5204, 74.3587),
        'model town': (31.4833, 74.3261),
        'johar town': (31.4697, 74.2728),
        'dha': (31.4697, 74.4100),
        'cantt': (31.5050, 74.3530),
        'mall road': (31.5590, 74.3260),
        'liberty': (31.5105, 74.3426),
        'township': (31.4500, 74.3000),
        'walton': (31.4820, 74.3550),
        'iqbal town': (31.5100, 74.2800),
        'bahria': (31.3700, 74.2000),
        'thokar': (31.4700, 74.2400),
        'faisal town': (31.4850, 74.3000),
        'garden town': (31.5000, 74.3200),
        'samanabad': (31.5300, 74.3000),
        'shadman': (31.5400, 74.3300),
        'anarkali': (31.5700, 74.3100),
    }

    def _guess_coords(location_text):
        if not location_text:
            return None
        t = location_text.lower()
        for key, coords in CITY_GEO.items():
            if key in t:
                return coords
        return (31.5204, 74.3587)  

    heat_points = []
    camera_markers = []

    cameras = Camera.objects.filter(is_active=True)
    cam_challan_counts = dict(
        Challan.objects.exclude(camera_id=None)
        .values('camera_id')
        .annotate(c=Count('id'))
        .values_list('camera_id', 'c')
    )

    for cam in cameras:
        lat, lng = cam.latitude, cam.longitude
        if lat is None or lng is None:
            guessed = _guess_coords(cam.location)
            if guessed:
                lat, lng = guessed
        if lat is None or lng is None:
            continue
        intensity = max(1, cam_challan_counts.get(cam.id, 0))
        heat_points.append([float(lat), float(lng), float(intensity)])
        camera_markers.append({
            'id': cam.camera_id,
            'location': cam.location or cam.camera_id,
            'lat': float(lat),
            'lng': float(lng),
            'challans': cam_challan_counts.get(cam.id, 0),
            'status': cam.health_status or 'unknown',
        })

    loc_counts = list(
        Challan.objects.exclude(location__isnull=True).exclude(location='')
        .values('location').annotate(c=Count('id')).order_by('-c')[:40]
    )
    for row in loc_counts:
        coords = _guess_coords(row['location'])
        if coords:
            heat_points.append([coords[0], coords[1], float(row['c'])])

    max_count = max([p[2] for p in heat_points], default=1)
    return render(request, 'dashboard/dig/heatmap.html', {
        'locations': loc_counts,
        'max_count': max_count,
        'heatmap_data_json': json.dumps(heat_points),
        'camera_markers_json': json.dumps(camera_markers),
        'total_points': len(heat_points),
    })
