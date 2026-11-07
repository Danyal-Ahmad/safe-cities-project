import datetime
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.decorators import role_required
from accounts.models import User
from appeals.models import ChallanAppeal
from detections.models import Detection
from challans.models import Challan
from admin.dig_portal.models import Shift
from realtime.models import CameraAssignment

SHIFT_BUCKET_ORDER = {'Morning': 0, 'Evening': 1, 'Night': 2}


def _shift_bucket_label(dt):
    hour = timezone.localtime(dt).hour
    if 6 <= hour < 14:
        return 'Morning'
    if 14 <= hour < 22:
        return 'Evening'
    return 'Night'


def _active_shift_summary():
    now = timezone.now()
    active = Shift.objects.filter(
        start_time__lte=now, end_time__gt=now
    ).select_related('officer')
    buckets = {}
    for shift in active:
        label = _shift_bucket_label(shift.start_time)
        buckets.setdefault(label, []).append(shift.officer.display_name)
    summary = []
    for label in sorted(buckets, key=lambda name: SHIFT_BUCKET_ORDER.get(name, 99)):
        names = buckets[label]
        summary.append({
            'label': label,
            'count': len(names),
            'officers': names[:3],
            'extra': max(0, len(names) - 3),
        })
    return summary


def _parse_shift_dt(val):
    if not val:
        return None
    val = str(val).strip().replace(' ', 'T')
    dt = parse_datetime(val)
    if dt is None:
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
            try:
                dt = datetime.datetime.strptime(val[:19], fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if timezone.is_naive(dt):
        try:
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        except Exception:
            pass
    return dt


def _age_label(delta):
    total_minutes = int(delta.total_seconds() // 60)
    days, rem = divmod(total_minutes, 1440)
    hours, minutes = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


@role_required('DIG', 'SSP', 'SUPV')
def dashboard(request):
    now = timezone.now()
    today = now.date()

    officers = User.objects.filter(role='OFFICER')
    total_officers = officers.count()
    active_officers = officers.filter(last_login__date=today).count()
    pending_appeals = ChallanAppeal.objects.filter(status=ChallanAppeal.PENDING).count()
    pending_reviews = Detection.objects.filter(status=Detection.PENDING).count()
    flagged_count = Detection.objects.filter(status=Detection.FLAGGED).count()
    challans_issued = Challan.objects.count()
    challans_paid = Challan.objects.filter(payment_status='PAID').count()
    shift_summary = _active_shift_summary()

    stats = []
    for o in officers:
        reviewed = Detection.objects.filter(reviewed_by=o).count()
        confirmed = Detection.objects.filter(reviewed_by=o, status=Detection.CONFIRMED).count()
        rejected = Detection.objects.filter(reviewed_by=o, status=Detection.REJECTED).count()
        flagged = Detection.objects.filter(reviewed_by=o, status=Detection.FLAGGED).count()
        appeals = ChallanAppeal.objects.filter(reviewed_by=o).count()
        accuracy = (confirmed / reviewed * 100) if reviewed else 0
        stats.append({
            'officer': o,
            'reviewed': reviewed,
            'confirmed': confirmed,
            'rejected': rejected,
            'flagged': flagged,
            'appeals': appeals,
            'accuracy': accuracy,
        })
    stats.sort(key=lambda s: s['reviewed'], reverse=True)

    days_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_start = datetime.datetime.combine(day, datetime.time.min).replace(tzinfo=timezone.get_current_timezone())
        day_end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time.min).replace(tzinfo=timezone.get_current_timezone())
        reviewed = Detection.objects.filter(reviewed_at__gte=day_start, reviewed_at__lt=day_end).count()
        days_data.append({'label': day.strftime('%a'), 'count': reviewed})

    return render(request, 'dashboard/supervisor/dashboard.html', {
        'officers': officers,
        'total_officers': total_officers,
        'active_officers': active_officers,
        'pending_appeals': pending_appeals,
        'pending_reviews': pending_reviews,
        'flagged_count': flagged_count,
        'challans_issued': challans_issued,
        'challans_paid': challans_paid,
        'shift_summary': shift_summary,
        'stats': stats,
        'days_data': days_data,
    })


@role_required('DIG', 'SSP', 'SUPV')
def team_performance(request):
    officers = User.objects.filter(role='OFFICER')
    stats = []
    for o in officers:
        reviewed = Detection.objects.filter(reviewed_by=o).count()
        confirmed = Detection.objects.filter(reviewed_by=o, status=Detection.CONFIRMED).count()
        rejected = Detection.objects.filter(reviewed_by=o, status=Detection.REJECTED).count()
        flagged = Detection.objects.filter(reviewed_by=o, status=Detection.FLAGGED).count()
        appeals = ChallanAppeal.objects.filter(reviewed_by=o).count()
        accuracy = (confirmed / reviewed * 100) if reviewed else 0
        stats.append({
            'officer': o,
            'reviewed': reviewed,
            'confirmed': confirmed,
            'rejected': rejected,
            'flagged': flagged,
            'appeals': appeals,
            'accuracy': accuracy,
        })
    stats.sort(key=lambda s: s['reviewed'], reverse=True)
    return render(request, 'dashboard/supervisor/team_performance.html', {'stats': stats})


@role_required('SUPV', 'SSP', 'DIG')
def team_queue_load(request):
    now = timezone.now()
    today = now.date()
    officers = User.objects.filter(role=User.OFFICER, is_active=True).order_by('first_name', 'username')
    rows = []
    for o in officers:
        camera_ids = list(
            CameraAssignment.objects.filter(officer=o, is_active=True)
            .values_list('camera_id', flat=True)
        )
        pending_qs = (
            Detection.objects.filter(status=Detection.PENDING, camera_id__in=camera_ids)
            if camera_ids else Detection.objects.none()
        )
        pending = pending_qs.count()
        oldest = pending_qs.order_by('created_at').values_list('created_at', flat=True).first()
        oldest_age = None
        oldest_age_label = None
        if oldest:
            oldest_age = (now - oldest).total_seconds() / 3600
            oldest_age_label = _age_label(now - oldest)
        reviewed_today = Detection.objects.filter(
            reviewed_by=o, reviewed_at__date=today).count()
        flagged = Detection.objects.filter(
            reviewed_by=o, status=Detection.FLAGGED).count()
        confirmed = Detection.objects.filter(
            reviewed_by=o, status=Detection.CONFIRMED).count()
        rejected = Detection.objects.filter(
            reviewed_by=o, status=Detection.REJECTED).count()
        decided = confirmed + rejected
        accuracy = (confirmed / decided * 100) if decided else 0
        rows.append({
            'officer': o,
            'pending': pending,
            'reviewed_today': reviewed_today,
            'flagged': flagged,
            'confirmed': confirmed,
            'rejected': rejected,
            'oldest_age': oldest_age,
            'oldest_age_label': oldest_age_label,
            'accuracy': accuracy,
        })
    rows.sort(key=lambda r: r['pending'], reverse=True)
    team_pending = sum(r['pending'] for r in rows)
    avg_load = (team_pending / len(rows)) if rows else 0
    oldest_overall = None
    oldest_overall_label = None
    for r in rows:
        if r['oldest_age'] is not None and (oldest_overall is None or r['oldest_age'] > oldest_overall):
            oldest_overall = r['oldest_age']
            oldest_overall_label = r['oldest_age_label']
    most_loaded = rows[0] if rows else None
    return render(request, 'dashboard/supervisor/team_queue_load.html', {
        'rows': rows,
        'team_pending': team_pending,
        'avg_load': avg_load,
        'most_loaded': most_loaded,
        'oldest_pending_label': oldest_overall_label,
        'officer_count': len(rows),
    })


@role_required('DIG', 'SSP', 'SUPV')
def shift_management(request):
    officers = User.objects.filter(role=User.OFFICER).order_by('first_name')
    shifts = Shift.objects.select_related('officer', 'assigned_by').order_by('-start_time')[:100]
    return render(request, 'dashboard/supervisor/shift_management.html', {
        'officers': officers,
        'shifts': shifts,
    })


@role_required('DIG', 'SSP', 'SUPV')
def shift_add(request):
    if request.method != 'POST':
        return redirect('supervisor_portal:shift_management')
    start = request.POST.get('start_time')
    end = request.POST.get('end_time')
    officer_id = request.POST.get('officer_id')
    if not start or not end:
        messages.error(request, "Start and end time are required.")
        return redirect('supervisor_portal:shift_management')
    start_dt = _parse_shift_dt(start)
    end_dt = _parse_shift_dt(end)
    if not start_dt or not end_dt or end_dt <= start_dt:
        messages.error(request, "Invalid shift window.")
        return redirect('supervisor_portal:shift_management')
    officer = None
    if officer_id:
        officer = User.objects.filter(pk=officer_id, role=User.OFFICER, is_active=True).first()
    if officer is None:
        officer = Shift.auto_assign_officer(start_dt, end_dt)
    if officer is None:
        messages.error(request, "No eligible officer available for this slot.")
        return redirect('supervisor_portal:shift_management')
    Shift.objects.create(
        officer=officer,
        start_time=start_dt,
        end_time=end_dt,
        assigned_by=request.user,
    )
    messages.success(request, f"Shift assigned to {officer.get_full_name() or officer.username}.")
    return redirect('supervisor_portal:shift_management')


@role_required('SUPV', 'SSP', 'DIG')
def camera_assignments_view(request):
    assignments = list(
        CameraAssignment.objects.select_related('camera', 'officer', 'assigned_by')
        .order_by('-assigned_at')
    )
    officer_counts = {}
    camera_ids = set()
    for a in assignments:
        camera_ids.add(a.camera_id)
        entry = officer_counts.setdefault(a.officer_id, {'officer': a.officer, 'total': 0, 'active': 0})
        entry['total'] += 1
        if a.is_active:
            entry['active'] += 1
    officer_rows = sorted(officer_counts.values(), key=lambda c: c['total'], reverse=True)
    totals = {
        'assignments': len(assignments),
        'active': sum(1 for a in assignments if a.is_active),
        'cameras': len(camera_ids),
        'officers': len(officer_rows),
    }
    return render(request, 'dashboard/supervisor/camera_assignments.html', {
        'assignments': assignments,
        'officer_rows': officer_rows,
        'totals': totals,
    })
