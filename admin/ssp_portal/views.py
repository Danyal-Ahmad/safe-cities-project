import csv
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from django.utils import timezone

from accounts.decorators import role_required
from accounts.models import User
from challans.models import Challan
from cameras.models import Camera
from detections.models import Detection
from appeals.models import ChallanAppeal
from admin.dig_portal.models import AuditLog, Notification


HIGH_VALUE_THRESHOLD = 5000
ACK_ACTION = 'ssp.challan_acknowledged'
CAMERA_ONLINE_GRACE_MINUTES = 15
CAMERA_OFFLINE_AFTER_MINUTES = 60


def _production_date(request):
    raw = (request.GET.get('date') or '').strip()
    if not raw:
        return timezone.localdate(), None
    try:
        return datetime.date.fromisoformat(raw), None
    except ValueError:
        return timezone.localdate(), raw


def _day_production(day):
    agg = Challan.objects.filter(issue_date=day).aggregate(
        issued=Count('id'),
        paid=Count('id', filter=Q(payment_status=Challan.PAID)),
        unpaid=Count('id', filter=Q(payment_status=Challan.UNPAID)),
        voided=Count('id', filter=Q(payment_status=Challan.VOIDED)),
        fines_issued=Sum('fine_amount'),
        fines_paid=Sum('fine_amount', filter=Q(payment_status=Challan.PAID)),
        fines_unpaid=Sum('fine_amount', filter=Q(payment_status=Challan.UNPAID)),
        fines_voided=Sum('fine_amount', filter=Q(payment_status=Challan.VOIDED)),
    )
    return {k: (v or 0) for k, v in agg.items()}


def _production_rows(day):
    violation_rows = list(
        Challan.objects.filter(issue_date=day)
        .values('violation_type')
        .annotate(
            issued=Count('id'),
            paid=Count('id', filter=Q(payment_status=Challan.PAID)),
            unpaid=Count('id', filter=Q(payment_status=Challan.UNPAID)),
            voided=Count('id', filter=Q(payment_status=Challan.VOIDED)),
            fines_issued=Sum('fine_amount'),
            fines_paid=Sum('fine_amount', filter=Q(payment_status=Challan.PAID)),
            fines_unpaid=Sum('fine_amount', filter=Q(payment_status=Challan.UNPAID)),
            fines_voided=Sum('fine_amount', filter=Q(payment_status=Challan.VOIDED)),
        )
        .order_by('-issued')
    )
    for row in violation_rows:
        row['label'] = (row['violation_type'] or 'other').replace('_', ' ').title()
        for key in ('fines_issued', 'fines_paid', 'fines_unpaid', 'fines_voided'):
            row[key] = row[key] or 0

    camera_rows = list(
        Challan.objects.filter(issue_date=day, camera__isnull=False)
        .values('camera_id', 'camera__camera_id', 'camera__location')
        .annotate(issued=Count('id'), fines_issued=Sum('fine_amount'))
        .order_by('-issued')[:10]
    )
    for row in camera_rows:
        row['cam_code'] = row.pop('camera__camera_id') or '-'
        row['cam_location'] = row.pop('camera__location') or '-'
        row['fines_issued'] = row['fines_issued'] or 0

    officer_rows = list(
        User.objects.filter(role=User.OFFICER, challans_created__issue_date=day)
        .annotate(
            issued=Count('challans_created'),
            fines_issued=Sum('challans_created__fine_amount'),
        )
        .order_by('-issued')
    )
    for officer in officer_rows:
        officer.fines_issued = officer.fines_issued or 0

    return {
        'violation_rows': violation_rows,
        'camera_rows': camera_rows,
        'officer_rows': officer_rows,
    }


@role_required('SSP', 'DIG')
def daily_production(request):
    selected_date, invalid_raw = _production_date(request)
    if invalid_raw:
        messages.error(request, f"Invalid date '{invalid_raw}'. Showing production for today.")
    prev_date = selected_date - datetime.timedelta(days=1)
    totals = _day_production(selected_date)
    prev_totals = _day_production(prev_date)
    deltas = {k: totals[k] - prev_totals[k] for k in totals}
    rows = _production_rows(selected_date)
    return render(request, 'dashboard/ssp/daily_production.html', {
        'selected_date': selected_date,
        'prev_date': prev_date,
        'totals': totals,
        'prev_totals': prev_totals,
        'deltas': deltas,
        'violation_rows': rows['violation_rows'],
        'camera_rows': rows['camera_rows'],
        'officer_rows': rows['officer_rows'],
    })


@role_required('SSP', 'DIG')
def daily_production_export(request):
    selected_date, invalid_raw = _production_date(request)
    if invalid_raw:
        messages.error(request, f"Invalid date '{invalid_raw}'. Export uses today's production report.")
        return redirect('ssp_portal:daily_production')
    prev_date = selected_date - datetime.timedelta(days=1)
    totals = _day_production(selected_date)
    prev_totals = _day_production(prev_date)
    rows = _production_rows(selected_date)

    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="safecity_daily_production_{selected_date:%Y%m%d}.csv"'
    w = csv.writer(resp)
    w.writerow(['Safe City Daily Production Report'])
    w.writerow(['Report Date', selected_date.isoformat()])
    w.writerow(['Previous Day', prev_date.isoformat()])
    w.writerow(['Generated At', timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')])
    w.writerow([])
    w.writerow(['Section', 'Name', 'Issued', 'Paid', 'Unpaid', 'Voided',
                'Fines Issued PKR', 'Fines Paid PKR', 'Fines Unpaid PKR', 'Fines Voided PKR'])
    w.writerow(['Totals', 'All violations', totals['issued'], totals['paid'], totals['unpaid'], totals['voided'],
                totals['fines_issued'], totals['fines_paid'], totals['fines_unpaid'], totals['fines_voided']])
    w.writerow(['Previous Day Totals', 'All violations', prev_totals['issued'], prev_totals['paid'],
                prev_totals['unpaid'], prev_totals['voided'], prev_totals['fines_issued'],
                prev_totals['fines_paid'], prev_totals['fines_unpaid'], prev_totals['fines_voided']])
    for r in rows['violation_rows']:
        w.writerow(['By Violation', r['label'], r['issued'], r['paid'], r['unpaid'], r['voided'],
                    r['fines_issued'], r['fines_paid'], r['fines_unpaid'], r['fines_voided']])
    w.writerow([])
    w.writerow(['Section', 'Camera', 'Location', 'Challans', 'Fines Issued PKR'])
    for r in rows['camera_rows']:
        w.writerow(['By Camera', r['cam_code'], r['cam_location'], r['issued'], r['fines_issued']])
    w.writerow([])
    w.writerow(['Section', 'Officer', 'Username', 'Challans', 'Fines Issued PKR'])
    for r in rows['officer_rows']:
        w.writerow(['By Officer', r.display_name, r.username, r.issued, r.fines_issued])

    AuditLog.write(request, 'report.generate', 'Challan', 0,
                   kind='daily_production', date=selected_date.isoformat())
    return resp


def _outage_age_text(hours):
    if hours is None:
        return 'Never seen'
    if hours < 1:
        return f"{max(1, int(hours * 60))} min"
    if hours < 72:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} d"


@role_required('SSP', 'DIG')
def camera_outage(request):
    now = timezone.now()
    since_7d = now - datetime.timedelta(days=7)
    cameras = list(Camera.objects.all().order_by('-installed_date'))
    cam_ids = [c.id for c in cameras]

    detection_counts = {}
    if cam_ids:
        detection_counts = dict(
            Detection.objects.filter(camera_id__in=cam_ids, created_at__gte=since_7d)
            .values_list('camera_id')
            .annotate(c=Count('id'))
        )
    challan_counts = {}
    if cam_ids:
        challan_counts = dict(
            Challan.objects.filter(camera_id__in=cam_ids, created_at__gte=since_7d)
            .values_list('camera_id')
            .annotate(c=Count('id'))
        )

    rows = []
    offline_count = 0
    never_seen_count = 0
    enforcement_loss = 0
    for cam in cameras:
        detections_7d = detection_counts.get(cam.id, 0)
        challans_7d = challan_counts.get(cam.id, 0)
        signal_at = cam.last_frame_at or cam.last_health_check
        if signal_at is None:
            bucket = 'never'
            outage_age_hours = None
            sort_age = float('inf')
            never_seen_count += 1
            offline_count += 1
        else:
            age = now - signal_at
            outage_age_hours = age.total_seconds() / 3600.0
            sort_age = outage_age_hours
            minutes = age.total_seconds() / 60.0
            if minutes <= CAMERA_ONLINE_GRACE_MINUTES:
                bucket = 'online'
            elif minutes <= CAMERA_OFFLINE_AFTER_MINUTES:
                bucket = 'degraded'
            else:
                bucket = 'offline'
                offline_count += 1
        if bucket in ('offline', 'never'):
            enforcement_loss += challans_7d
        rows.append({
            'camera': cam,
            'bucket': bucket,
            'outage_age_hours': outage_age_hours,
            'outage_age_text': _outage_age_text(outage_age_hours),
            'detections_7d': detections_7d,
            'challans_7d': challans_7d,
            'sort_bucket': 0 if bucket in ('offline', 'never') else (1 if bucket == 'degraded' else 2),
            'sort_age': sort_age,
        })

    rows.sort(key=lambda r: (r['sort_bucket'], -r['sort_age']))

    total_cameras = len(cameras)
    detections_7d_total = Detection.objects.filter(created_at__gte=since_7d).count()
    avg_detections_7d = (detections_7d_total / total_cameras) if total_cameras else 0

    return render(request, 'dashboard/ssp/camera_outage.html', {
        'rows': rows,
        'total_cameras': total_cameras,
        'offline_count': offline_count,
        'never_seen_count': never_seen_count,
        'online_count': sum(1 for r in rows if r['bucket'] == 'online'),
        'degraded_count': sum(1 for r in rows if r['bucket'] == 'degraded'),
        'avg_detections_7d': avg_detections_7d,
        'enforcement_loss': enforcement_loss,
    })


@role_required('SSP', 'DIG')
def dashboard(request):
    now = timezone.now()
    today = now.date()

    high_value_challans = list(Challan.objects.filter(
        fine_amount__gte=HIGH_VALUE_THRESHOLD,
        payment_status='UNPAID',
    ).order_by('-issue_date')[:20])

    acked_ids = set()
    if high_value_challans:
        acked_ids = set(
            AuditLog.objects.filter(
                action=ACK_ACTION,
                target_model='Challan',
                target_id__in=[c.id for c in high_value_challans],
            ).values_list('target_id', flat=True)
        )

    pending_appeals = ChallanAppeal.objects.filter(
        status=ChallanAppeal.PENDING,
    ).select_related('challan', 'submitted_by', 'challan__created_by').order_by('-created_at')[:20]

    total_revenue = Challan.objects.filter(payment_status='PAID').aggregate(t=Sum('fine_amount'))['t'] or 0
    total_challans = Challan.objects.count()
    high_value_count = Challan.objects.filter(fine_amount__gte=HIGH_VALUE_THRESHOLD, payment_status='UNPAID').count()
    high_value_revenue = Challan.objects.filter(
        fine_amount__gte=HIGH_VALUE_THRESHOLD, payment_status='UNPAID'
    ).aggregate(t=Sum('fine_amount'))['t'] or 0

    approved_appeals = ChallanAppeal.objects.filter(status=ChallanAppeal.APPROVED).count()
    rejected_appeals = ChallanAppeal.objects.filter(status=ChallanAppeal.REJECTED).count()

    days_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_start = datetime.datetime.combine(day, datetime.time.min).replace(tzinfo=timezone.get_current_timezone())
        day_end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time.min).replace(tzinfo=timezone.get_current_timezone())
        submitted = ChallanAppeal.objects.filter(
            created_at__gte=day_start, created_at__lt=day_end
        ).count()
        decided = ChallanAppeal.objects.filter(
            reviewed_at__gte=day_start, reviewed_at__lt=day_end
        ).exclude(status=ChallanAppeal.PENDING).count()
        days_data.append({'label': day.strftime('%a'), 'submitted': submitted, 'decided': decided})

    violation_dist = (
        Challan.objects.values('violation_type')
        .annotate(c=Count('id'))
        .order_by('-c')[:6]
    )
    violation_labels = [v['violation_type'].replace('_', ' ').title() for v in violation_dist]
    violation_counts = [v['c'] for v in violation_dist]

    return render(request, 'dashboard/ssp/dashboard.html', {
        'high_value_challans': high_value_challans,
        'acked_ids': acked_ids,
        'pending_appeals': pending_appeals,
        'total_revenue': total_revenue,
        'total_challans': total_challans,
        'high_value_count': high_value_count,
        'high_value_revenue': high_value_revenue,
        'approved_appeals': approved_appeals,
        'rejected_appeals': rejected_appeals,
        'days_data': days_data,
        'violation_labels': violation_labels,
        'violation_counts': violation_counts,
        'HIGH_VALUE': HIGH_VALUE_THRESHOLD,
    })


@role_required('SSP', 'DIG')
def approve_challan(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    if request.method == 'POST':
        if AuditLog.objects.filter(
            action=ACK_ACTION, target_model='Challan', target_id=challan.id
        ).exists():
            messages.info(request, f"Challan {challan.ticket_no} already acknowledged.")
            return redirect('ssp_portal:dashboard')
        if challan.payment_status != Challan.UNPAID:
            messages.error(
                request,
                f"Challan {challan.ticket_no} is {challan.payment_status}, so dispatch cannot be acknowledged.",
            )
            return redirect('ssp_portal:dashboard')
        if (challan.fine_amount or 0) < HIGH_VALUE_THRESHOLD:
            messages.error(
                request,
                f"Challan {challan.ticket_no} is below the PKR {HIGH_VALUE_THRESHOLD} high-value threshold.",
            )
            return redirect('ssp_portal:dashboard')

        officer_label = challan.created_by.display_name if challan.created_by else 'System'
        AuditLog.write(
            request, ACK_ACTION, 'Challan', challan.id,
            ticket=challan.ticket_no,
            amount=float(challan.fine_amount),
            officer=officer_label,
        )
        if challan.created_by:
            Notification.objects.create(
                recipient=challan.created_by,
                title=f"High-value challan acknowledged: {challan.ticket_no}",
                message=(
                    f"Your high-value challan has been acknowledged by SSP command.\n"
                    f"----------------------------------------\n"
                    f"Challan No: {challan.ticket_no}\n"
                    f"Plate: {challan.plate_number}\n"
                    f"Amount: PKR {challan.fine_amount:,.0f}\n"
                    f"Acknowledged by: {request.user.display_name} (SSP)\n"
                    f"Timestamp: {timezone.now():%Y-%m-%d %H:%M:%S}\n"
                    f"Dispatch approved for printing and field service.\n"
                ),
                category='challan',
                target_url=reverse('challans:challan_detail', args=[challan.id]),
            )
        messages.success(request, f"Challan {challan.ticket_no} acknowledged; dispatch approved.")
    return redirect('ssp_portal:dashboard')


@role_required('SSP', 'DIG')
def decide_appeal(request, appeal_id):

    appeal = get_object_or_404(ChallanAppeal, pk=appeal_id)
    if request.method == 'POST':
        decision = request.POST.get('decision', 'APPROVED')
        reason = request.POST.get('reason', '').strip()
        if decision not in ('APPROVED', 'REJECTED'):
            messages.error(request, "Invalid decision.")
            return redirect('ssp_portal:dashboard')
        if appeal.status != ChallanAppeal.PENDING:
            messages.error(request, "This appeal is not awaiting an SSP decision.")
            return redirect('ssp_portal:dashboard')

        decision_const = ChallanAppeal.APPROVED if decision == 'APPROVED' else ChallanAppeal.REJECTED
        appeal.status = decision_const
        appeal.ssp_comment = reason
        appeal.ssp_reviewed_by = request.user
        appeal.ssp_reviewed_at = timezone.now()
        appeal.reviewed_by = request.user
        appeal.reviewed_at = timezone.now()
        appeal.save()

        if decision == 'APPROVED':
            appeal.challan.payment_status = Challan.VOIDED
            appeal.challan.save()

        decision_text = "APPROVED" if decision == 'APPROVED' else "REJECTED"
        notification_msg = (
            f"Your appeal has been {decision_text}.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Appeal ID: APL-{appeal.id:06d}\n"
            f"Challan No: {appeal.challan.ticket_no}\n"
            f"Decision: {decision_text}\n"
            f"Reviewed by: {request.user.display_name} (SSP)\n"
            f"Decision timestamp: {timezone.now():%Y-%m-%d %H:%M:%S}\n"
            f"SSP Comment: {reason or '-'}\n"
        )
        if decision == 'APPROVED':
            notification_msg += "\nYour challan has been voided. No payment is required."
        else:
            notification_msg += "\nYour challan remains active. Please pay before the due date."

        Notification.objects.create(
            recipient=appeal.submitted_by,
            title=f"Appeal {decision_text} - {appeal.challan.ticket_no}",
            message=notification_msg,
            category='appeal_approved' if decision == 'APPROVED' else 'appeal_rejected',
            target_url=reverse('citizen_portal:appeal_tracker'),
        )

        AuditLog.write(request, 'ssp.appeal_decision', 'ChallanAppeal', appeal.id,
                       decision=decision, reason=reason[:120],
                       challan=appeal.challan.ticket_no,
                       citizen_notified=True)
        messages.success(request, f"Appeal {appeal.id} {decision.lower()} by SSP. Citizen has been notified.")
    return redirect('ssp_portal:dashboard')
