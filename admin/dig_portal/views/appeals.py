from django.contrib import messages
from django.conf import settings as dj_settings

from challans.models import Challan
from appeals.models import ChallanAppeal
from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from detections.models import Detection
from accounts.models import User
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from accounts.decorators import role_required


@role_required('SSP', 'DIG', 'SUPV')
def appeal_override(request, appeal_id):
    appeal = get_object_or_404(ChallanAppeal, pk=appeal_id)
    user_role = request.user.role

    if appeal.status != ChallanAppeal.PENDING:
        messages.info(request, "This appeal has already been decided by the SSP.")
    elif user_role != User.SSP:
        messages.info(request, "Mistake-challan appeals are decided by the SSP only.")

    if request.method == 'POST':
        comment = (request.POST.get('comment') or '').strip()
        action = request.POST.get('action', '').strip()
        if user_role != User.SSP:
            AuditLog.write(request, 'appeal.decision_denied', 'ChallanAppeal', appeal.id,
                           actor_role=user_role)
            messages.error(request, "Only the SSP can decide mistake-challan appeals.")
            return redirect('dig:appeal_override', appeal_id=appeal.id)
        if action not in ('approve', 'reject'):
            messages.error(request, "Invalid action.")
            return redirect('dig:appeal_override', appeal_id=appeal.id)
        if appeal.status != ChallanAppeal.PENDING:
            messages.error(request, "This appeal has already been decided.")
            return redirect('dig:appeal_override', appeal_id=appeal.id)
        if len(comment) < 30:
            messages.error(request, "Comment is required (min 30 chars).")
            return redirect('dig:appeal_override', appeal_id=appeal.id)

        from admin.dig_portal.models import Notification as _Notif
        c = appeal.challan
        detail_msg = (
            f"APPEAL {action.upper()} | SSP DECISION\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Appeal ID: APL-{appeal.id:06d}\n"
            f"Challan No: {c.ticket_no}\n"
            f"Plate: {c.plate_number}\n"
            f"Violation: {c.get_violation_type_display()}\n"
            f"Fine: PKR {c.fine_amount}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Reviewer: {request.user.display_name} (SSP)\n"
            f"Comment: {comment}\n"
        )

        decision = ChallanAppeal.APPROVED if action == 'approve' else ChallanAppeal.REJECTED
        appeal.finalize(decision, comment, request.user)
        if action == 'approve' and appeal.challan.payment_status == Challan.UNPAID:
            appeal.challan.payment_status = Challan.VOIDED
            appeal.challan.save()
        AuditLog.write(request, f'appeal.ssp_{action}', 'ChallanAppeal', appeal.id,
                       challan=c.ticket_no, comment=comment[:100])
        if appeal.submitted_by:
            _Notif.objects.create(recipient=appeal.submitted_by,
                title=f"Appeal {action}d | {c.ticket_no}",
                message=detail_msg + f"\n\nDecision: {action.upper()}",
                category=f'appeal_{"approved" if action == "approve" else "rejected"}',
                target_url="/portal/")
        messages.success(request, f"Appeal {action}d. Final decision recorded. Citizen notified.")
        return redirect('dig:appeals_queue')

    return render(request, 'dashboard/dig/appeal_override.html', {
        'appeal': appeal,
        'can_finalize': user_role == User.SSP and appeal.status == ChallanAppeal.PENDING,
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT')
def appeals_queue(request):
    appeals = list(
        ChallanAppeal.objects.all().select_related('challan', 'submitted_by').order_by('-created_at')[:100]
    )
    pending_appeals = [a for a in appeals if a.status == ChallanAppeal.PENDING]
    decided_appeals = [a for a in appeals if a.status != ChallanAppeal.PENDING]
    flagged = Detection.objects.filter(status=Detection.FLAGGED).order_by('-created_at')[:50]
    return render(request, 'dashboard/dig/case_escalation.html', {
        'pending_appeals': pending_appeals,
        'decided_appeals': decided_appeals,
        'appeals': appeals,
        'flagged': flagged,
    })
