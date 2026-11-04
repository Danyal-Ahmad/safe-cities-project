import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timezone as dt_timezone
import datetime as _dt

from accounts.decorators import role_required
from challans.models import Challan
from appeals.models import ChallanAppeal
from admin.dig_portal.models import AuditLog


HIGH_VALUE_THRESHOLD = 5000


@role_required('SSP', 'DIG')
def dashboard(request):
    now = timezone.now()
    today = now.date()
    last_7d = now - datetime.timedelta(days=7)

    high_value_challans = Challan.objects.filter(
        fine_amount__gte=HIGH_VALUE_THRESHOLD,
        payment_status='UNPAID',
    ).order_by('-issue_date')[:20]

    pending_appeals = ChallanAppeal.objects.filter(
        status=ChallanAppeal.PENDING,
        current_stage=ChallanAppeal.STAGE_SSP,
    ).select_related('challan', 'submitted_by', 'challan__created_by').order_by('-created_at')[:20]

    escalations = ChallanAppeal.objects.filter(
        status=ChallanAppeal.ESCALATED,
    ).select_related('challan', 'submitted_by').order_by('-escalated_at')[:20]

    escalated = ChallanAppeal.objects.filter(status=ChallanAppeal.ESCALATED).count()
    total_revenue = Challan.objects.filter(payment_status='PAID').aggregate(t=Sum('fine_amount'))['t'] or 0
    total_challans = Challan.objects.count()
    high_value_count = Challan.objects.filter(fine_amount__gte=HIGH_VALUE_THRESHOLD, payment_status='UNPAID').count()
    high_value_revenue = Challan.objects.filter(
        fine_amount__gte=HIGH_VALUE_THRESHOLD, payment_status='UNPAID'
    ).aggregate(t=Sum('fine_amount'))['t'] or 0

    approved_appeals = ChallanAppeal.objects.filter(status=ChallanAppeal.APPROVED).count()
    rejected_appeals = ChallanAppeal.objects.filter(status=ChallanAppeal.REJECTED).count()

    # 7-day appeal trend
    days_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_start = datetime.datetime.combine(day, datetime.time.min).replace(tzinfo=dt_timezone.utc)
        day_end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time.min).replace(tzinfo=dt_timezone.utc)
        submitted = ChallanAppeal.objects.filter(
            created_at__gte=day_start, created_at__lt=day_end
        ).count()
        decided = ChallanAppeal.objects.filter(
            reviewed_at__gte=day_start, reviewed_at__lt=day_end
        ).exclude(status=ChallanAppeal.PENDING).count()
        days_data.append({'label': day.strftime('%a'), 'submitted': submitted, 'decided': decided})

    # Violation breakdown
    violation_dist = (
        Challan.objects.values('violation_type')
        .annotate(c=Count('id'))
        .order_by('-c')[:6]
    )
    violation_labels = [v['violation_type'].replace('_', ' ').title() for v in violation_dist]
    violation_counts = [v['c'] for v in violation_dist]

    return render(request, 'dashboard/ssp/dashboard.html', {
        'high_value_challans': high_value_challans,
        'pending_appeals': pending_appeals,
        'escalations': escalations,
        'escalated': escalated,
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
        AuditLog.write(request, 'ssp.challan_approved', 'Challan', challan.id,
                       ticket=challan.ticket_no, amount=float(challan.fine_amount))
        messages.success(request, f"Challan {challan.ticket_no} approved by SSP.")
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
        if appeal.status != ChallanAppeal.PENDING or appeal.current_stage != ChallanAppeal.STAGE_SSP:
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

        from admin.dig_portal.models import Notification
        decision_text = "APPROVED" if decision == 'APPROVED' else "REJECTED"
        notification_msg = (
            f"Your appeal has been {decision_text}.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Appeal ID: APL-{appeal.id:06d}\n"
            f"Challan No: {appeal.challan.ticket_no}\n"
            f"Decision: {decision_text}\n"
            f"Reviewed by: {request.user.display_name} (SSP)\n"
            f"Decision timestamp: {timezone.now():%Y-%m-%d %H:%M:%S}\n"
            f"SSP Comment: {reason or '—'}\n"
        )
        if decision == 'APPROVED':
            notification_msg += "\nYour challan has been voided. No payment is required."
        else:
            notification_msg += "\nYour challan remains active. Please pay before the due date."

        Notification.objects.create(
            recipient=appeal.submitted_by,
            title=f"Appeal {decision_text} — {appeal.challan.ticket_no}",
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

