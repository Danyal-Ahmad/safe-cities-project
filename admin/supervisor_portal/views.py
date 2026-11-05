import datetime
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import role_required
from accounts.models import User
from appeals.models import ChallanAppeal
from detections.models import Detection
from challans.models import Challan


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
        accuracy = (confirmed / reviewed * 100) if reviewed else 100.0
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
