from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_ratelimit.decorators import ratelimit
from django.utils import timezone
from django.db.models import Q, Sum
from django.http import JsonResponse
import json


def _safe_verify_url(challan_id):
    try:
        return reverse('dig:verify_citizen_payment', kwargs={'challan_id': challan_id})
    except Exception:
        return f'/portal/dig/challan/{challan_id}/verify-payment/'


from accounts.decorators import user_only_required
from accounts.forms import ProfileEditForm, PasswordChangeForm
from challans.models import Challan
from appeals.models import ChallanAppeal
from admin.dig_portal.models import AuditLog


def _normalize_cnic(value):
    """Strip dashes/spaces so 35202-1234567-1 matches 3520212345671."""
    if not value:
        return ''
    return ''.join(ch for ch in str(value) if ch.isdigit())


def _user_plates(user):
    try:
        from accounts.models import VehicleRegistration
        return list(
            VehicleRegistration.objects.filter(user=user)
            .values_list('plate_number', flat=True)
        )
    except Exception:
        return []


def _is_challan_owner(challan, user):
    if user.cnic and challan.cnic:
        if user.cnic == challan.cnic or _normalize_cnic(user.cnic) == _normalize_cnic(challan.cnic):
            return True
    if user.phone and getattr(challan, 'phone', None) and user.phone == challan.phone:
        return True
    plates = {p.upper().replace(' ', '') for p in _user_plates(user) if p}
    plate = (challan.plate_number or '').upper().replace(' ', '')
    if plate and plate in plates:
        return True
    return False


@login_required
@user_only_required
def home(request):
    user = request.user
    q = Q()
    if user.cnic:
        q |= Q(cnic=user.cnic)
        digits = _normalize_cnic(user.cnic)
        if digits:
            q |= Q(cnic=digits)
            q |= Q(cnic__icontains=digits[:5])  # broad safety; filtered below
    if user.phone:
        q |= Q(phone=user.phone)
    plates = _user_plates(user)
    for plate in plates:
        if plate:
            q |= Q(plate_number__iexact=plate)
            q |= Q(plate_number__iexact=plate.replace(' ', '').replace('-', ''))
    if q:
        raw = list(Challan.objects.filter(q).order_by('-issue_date')[:200])
        challans = [c for c in raw if _is_challan_owner(c, user)]
    else:
        challans = []

    today = timezone.now().date()
    unpaid = [c for c in challans if getattr(c, 'payment_status', '') == 'UNPAID']
    paid = [c for c in challans if getattr(c, 'payment_status', '') == 'PAID']
    voided = [c for c in challans if getattr(c, 'payment_status', '') == 'VOIDED']
    overdue = [c for c in challans for o in [getattr(c, 'is_overdue', False)] if o]
    outstanding_amount = sum(float(c.fine_amount or 0) for c in unpaid)
    paid_amount = sum(float(c.fine_amount or 0) for c in paid)

    from collections import Counter
    violation_counter = Counter()
    for c in challans:
        v = c.get_violation_type_display() if hasattr(c, 'get_violation_type_display') else (c.violation_type or 'Other')
        violation_counter[v] += 1
    violation_labels = list(violation_counter.keys())
    violation_counts = list(violation_counter.values())

    import datetime
    month_labels = []
    month_counts = []
    for i in range(5, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        first = datetime.date(year, month, 1)
        if month == 12:
            next_first = datetime.date(year + 1, 1, 1)
        else:
            next_first = datetime.date(year, month + 1, 1)
        count = sum(1 for c in challans if c.issue_date and first <= c.issue_date < next_first)
        month_labels.append(first.strftime('%b'))
        month_counts.append(count)

    payload = []
    for c in challans:
        try:
            violation_display = c.get_violation_type_display() if hasattr(c, 'get_violation_type_display') else c.violation_type
        except Exception:
            violation_display = getattr(c, 'violation_type', '') or ''
        payload.append({
            'id': c.id,
            'ticket_no': c.ticket_no,
            'plate_number': c.plate_number,
            'violation_type': c.violation_type,
            'get_violation_type_display': violation_display,
            'issue_date': c.issue_date.isoformat() if c.issue_date else None,
            'due_date': c.due_date.isoformat() if c.due_date else None,
            'fine_amount': float(c.fine_amount or 0),
            'payment_status': c.payment_status,
        })
    return render(request, 'dashboard/citizen/home.html', {
        'challans': challans,
        'challans_json': json.dumps(payload),
        'total_challans': len(challans),
        'unpaid_count': len(unpaid),
        'paid_count': len(paid),
        'voided_count': len(voided),
        'overdue_count': len(overdue),
        'outstanding_amount': outstanding_amount,
        'paid_amount': paid_amount,
        'violation_labels': violation_labels,
        'violation_counts': violation_counts,
        'month_labels': month_labels,
        'month_counts': month_counts,
        'user_cnic': user.cnic,
        'user_plates': plates,
    })


@login_required
@user_only_required
@ratelimit(key='user', rate='5/d', block=True)
def submit_appeal(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    if not _is_challan_owner(challan, request.user):
        messages.error(request, "You can only appeal your own challans.")
        return redirect('citizen_portal:home')
    if ChallanAppeal.has_active_appeal(challan):
        messages.error(request, "An active appeal already exists for this challan.")
        return redirect('citizen_portal:home')
    if challan.payment_status in (Challan.PAID, Challan.VOIDED):
        messages.error(request, "This challan cannot be appealed.")
        return redirect('citizen_portal:home')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        evidence = request.FILES.get('evidence')
        if len(reason) < 30:
            messages.error(request, "Reason must be at least 30 characters.")
        else:
            if evidence and (not evidence.content_type or not evidence.content_type.startswith('image/')):
                messages.error(request, "Evidence must be an image file.")
                return redirect('citizen_portal:submit_appeal', challan_id=challan.id)
            if evidence and evidence.size > 5 * 1024 * 1024:
                messages.error(request, "Evidence file exceeds 5 MB limit.")
                return redirect('citizen_portal:submit_appeal', challan_id=challan.id)
            appeal = ChallanAppeal.objects.create(
                challan=challan, submitted_by=request.user,
                reason=reason, evidence_file=evidence if evidence else None,
            )

            from accounts.models import User
            from admin.dig_portal.models import Notification
            challan = appeal.challan

            officer_info = ""
            if challan.created_by:
                off = challan.created_by
                officer_info = (
                    f"Issuing Officer: {off.display_name} (ID: {off.public_id})\n"
                    f"Officer Role: {off.role_label}\n"
                )
            else:
                officer_info = "Issuing Officer: - (auto-generated challan)\n"

            detail_msg = (
                f"NEW APPEAL SUBMITTED\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Appeal ID: APL-{appeal.id:06d}\n"
                f"Challan No: {challan.ticket_no}\n"
                f"Plate Number: {challan.plate_number}\n"
                f"Violation Type: {challan.get_violation_type_display()}\n"
                f"Fine Amount: PKR {challan.fine_amount}\n"
                f"Issue Date: {challan.issue_date}\n"
                f"Due Date: {challan.due_date}\n"
                f"Location: {challan.location or '-'}\n"
                f"Owner: {challan.owner_name or '-'}\n"
                f"CNIC: {challan.cnic or '-'}\n"
                f"Payment Status: {challan.payment_status}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{officer_info}"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Submitted by: {request.user.display_name} ({request.user.email or request.user.phone})\n"
                f"Reason: {reason}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"This appeal has been DIRECTLY ROUTED TO SSP for review.\n"
                f"SSP is the direct reviewer and final decision-maker."
            )

            for ssp in User.objects.filter(role=User.SSP, is_active=True):
                Notification.objects.create(
                    recipient=ssp,
                    title=f"[ACTION REQUIRED] New Appeal | {challan.ticket_no}",
                    message=detail_msg,
                    category='appeal_submit',
                    target_url=reverse('ssp_portal:decide_appeal', args=[appeal.id]),
                )

            AuditLog.write(request, 'appeal.submit', 'ChallanAppeal', appeal.id,
                           challan=challan.ticket_no,
                           routed_to='ssp (direct transfer per V13 spec)')
            messages.success(request, "Appeal submitted. Directly routed to SSP for review. You will be notified of the decision.")
            return redirect('citizen_portal:appeal_tracker')
    return render(request, 'dashboard/citizen/submit_appeal.html', {'challan': challan})


@login_required
@user_only_required
def appeal_tracker(request):
    appeals = ChallanAppeal.objects.filter(submitted_by=request.user).order_by('-created_at')
    return render(request, 'dashboard/citizen/appeal_tracker.html', {'appeals': appeals})


@login_required
@user_only_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST)
        if form.is_valid():
            user = request.user
            old_cnic = user.cnic
            user.first_name = form.cleaned_data['first_name']
            user.phone = form.cleaned_data['phone'] or None
            user.email = form.cleaned_data['email'] or None
            user.cnic = form.cleaned_data['cnic'] or None
            avatar_file = request.FILES.get('avatar')
            if avatar_file:
                name = (avatar_file.name or '').lower()
                if not any(name.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    messages.error(request, "Avatar must be an image (JPG, PNG, GIF, or WEBP).")
                    return redirect('citizen_portal:profile_edit')
                if avatar_file.size > 5 * 1024 * 1024:
                    messages.error(request, "Avatar file must be under 5 MB.")
                    return redirect('citizen_portal:profile_edit')
                user.avatar = avatar_file
            user.save()
            AuditLog.write(request, 'user.profile_edit', 'User', user.id, cnic_changed=(old_cnic != user.cnic))
            if old_cnic != user.cnic:
                messages.success(request, "Profile updated. CNIC set - your dashboard will now auto-match challans.")
            else:
                messages.success(request, "Profile updated.")
            return redirect('citizen_portal:profile_edit')
    else:
        form = ProfileEditForm(initial={
            'first_name': request.user.first_name,
            'phone': request.user.phone or '',
            'email': request.user.email or '',
            'cnic': request.user.cnic or '',
        })
    return render(request, 'dashboard/citizen/profile_edit.html', {'form': form})


@login_required
@user_only_required
def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST)
        if form.is_valid():
            user = request.user
            if not user.check_password(form.cleaned_data['old_password']):
                messages.error(request, "Current password is incorrect.")
            else:
                user.set_password(form.cleaned_data['new_password1'])
                user.save()
                update_session_auth_hash(request, user)
                AuditLog.write(request, 'user.password_change', 'User', user.id)
                messages.success(request, "Password changed successfully.")
                return redirect('citizen_portal:profile_edit')
    else:
        form = PasswordChangeForm()
    return render(request, 'dashboard/citizen/password_change.html', {'form': form})


@login_required
@user_only_required
def pay_challan(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    if not _is_challan_owner(challan, request.user):
        messages.error(request, "You can only pay your own challans. Use the public challan page for other payments.")
        return redirect('citizen_portal:home')
    if challan.payment_status in (Challan.PAID, Challan.VOIDED):
        messages.info(request, "This challan cannot be paid.")
        return redirect('citizen_portal:home')

    from admin.dig_portal.models import AuditLog as _AL
    recent_submit = _AL.objects.filter(
        action='challan.payment_submitted',
        target_model='Challan',
        target_id=challan.id,
    ).order_by('-timestamp').first()
    if recent_submit and challan.payment_status == Challan.UNPAID:
        messages.info(
            request,
            "A payment submission for this challan is already pending staff verification. "
            "You do not need to submit again."
        )
        return redirect('citizen_portal:home')

    from admin.it_support_portal.models import PaymentMethod
    payment_methods = PaymentMethod.active_for_citizens()

    if request.method == 'POST':
        method_id = request.POST.get('payment_method')
        txn_ref = request.POST.get('txn_ref', '').strip()
        action = (request.POST.get('action') or 'manual').strip()

        if action == 'initiate' and method_id:
            from integrations.payments import initiate_payment
            from payments.models import PaymentTransaction
            payment_method = get_object_or_404(PaymentMethod, pk=method_id, status=PaymentMethod.STATUS_ACTIVE)
            return_url = request.build_absolute_uri(f'/challan/{challan.id}/pay/done/')
            callback_url = request.build_absolute_uri('/api/v1/payment/webhook/')
            init = initiate_payment(challan, payment_method, return_url, callback_url)
            if not init.get('ok'):
                messages.error(request, init.get('error') or "Payment could not be initiated.")
                return redirect('citizen_portal:pay_challan', challan_id=challan.id)

            PaymentTransaction.objects.create(
                ticket_no=challan.ticket_no,
                challan=challan,
                provider=(init.get('provider') or payment_method.name or 'demo'),
                amount=challan.fine_amount,
                status=PaymentTransaction.STATUS_PENDING,
                txn_ref=init.get('reference'),
            )
            AuditLog.write(request, 'challan.payment_initiate', 'Challan', challan.id,
                           ticket=challan.ticket_no, txn_ref=init.get('reference'),
                           method=payment_method.name, mode=init.get('mode'))
            if init.get('mode') == 'form':
                return render(request, 'dashboard/citizen/pay_redirect.html', {
                    'challan': challan,
                    'init': init,
                    'payment_method': payment_method,
                })
            if init.get('mode') == 'demo':
                return redirect(init.get('action_url') or reverse('citizen_portal:pay_challan', kwargs={'challan_id': challan.id}))
            messages.info(request, init.get('message') or 'Use manual transaction reference.')

        if not method_id:
            messages.error(request, "Please select a payment method.")
            return redirect('citizen_portal:pay_challan', challan_id=challan.id)
        if not txn_ref or len(txn_ref) < 5:
            messages.error(request, "Transaction reference is required (min 5 characters). Enter the ID from your payment receipt.")
            return redirect('citizen_portal:pay_challan', challan_id=challan.id)

        payment_method = get_object_or_404(PaymentMethod, pk=method_id, status=PaymentMethod.STATUS_ACTIVE)

        AuditLog.write(request, 'challan.payment_submitted', 'Challan', challan.id,
                       ticket=challan.ticket_no, amount=str(challan.fine_amount),
                       payment_method=payment_method.name, txn_ref=txn_ref,
                       status='PENDING_VERIFICATION')

        from admin.dig_portal.models import Notification
        from accounts.models import User
        for staff in User.objects.filter(role__in=['DIG', 'SSP', 'SUPV'], is_active=True):
            Notification.objects.create(
                recipient=staff,
                title=f"Payment Verification Required | {challan.ticket_no}",
                message=f"Citizen {request.user.display_name} submitted payment of PKR {challan.fine_amount} via {payment_method.name}. Transaction Ref: {txn_ref}. Please verify and confirm.",
                category='payment_verification',
                target_url=_safe_verify_url(challan.id),
            )

        messages.success(
            request,
            f"Payment reference submitted. Staff will verify {txn_ref} and mark "
            f"{challan.ticket_no} as paid after confirmation."
        )
        return redirect('citizen_portal:home')

    return render(request, 'dashboard/citizen/pay_challan.html', {
        'challan': challan,
        'payment_methods': payment_methods,
        'psid': challan.psid,
        'qr_payload': challan.payment_qr_payload,
    })



def _citizen_challans_qs(user):
    """All challans matching this citizen (CNIC / phone / registered plates),
    strict ownership filtered - same rules as the dashboard home view."""
    q = Q()
    if user.cnic:
        q |= Q(cnic=user.cnic)
        digits = _normalize_cnic(user.cnic)
        if digits:
            q |= Q(cnic=digits)
    if user.phone:
        q |= Q(phone=user.phone)
    for plate in _user_plates(user):
        if plate:
            q |= Q(plate_number__iexact=plate)
            q |= Q(plate_number__iexact=plate.replace(' ', '').replace('-', ''))
    if not q:
        return Challan.objects.none()
    raw = Challan.objects.filter(q).order_by('-issue_date')[:200]
    ids = [c.id for c in raw if _is_challan_owner(c, user)]
    return Challan.objects.filter(id__in=ids).order_by('-issue_date')


@login_required
@user_only_required
def api_citizen_kpis(request):
    """KPIs scoped to the logged-in citizen: their own challans, appeals, payments."""
    user = request.user
    my_challans = _citizen_challans_qs(user)
    return JsonResponse({
        'ts': int(timezone.now().timestamp()),
        'kpis': {
            'unpaid':          my_challans.filter(payment_status=Challan.UNPAID).count(),
            'paid':            my_challans.filter(payment_status=Challan.PAID).count(),
            'overdue':         my_challans.filter(payment_status=Challan.UNPAID, due_date__lt=timezone.now().date()).count(),
            'total_due':       float(my_challans.filter(payment_status=Challan.UNPAID).aggregate(t=Sum('fine_amount'))['t'] or 0),
            'total_paid':      float(my_challans.filter(payment_status=Challan.PAID).aggregate(t=Sum('fine_amount'))['t'] or 0),
            'open_appeals':    ChallanAppeal.objects.filter(submitted_by=user, status=ChallanAppeal.PENDING).count(),
            'resolved_appeals': ChallanAppeal.objects.filter(
                submitted_by=user, status__in=[ChallanAppeal.APPROVED, ChallanAppeal.REJECTED]).count(),
        },
    })


@login_required
@user_only_required
def api_citizen_challans(request):
    """DataTables server-side endpoint for the citizen's own challans."""
    try:
        draw   = int(request.GET.get('draw', 1))
        start  = int(request.GET.get('start', 0))
        length = max(1, min(100, int(request.GET.get('length', 10))))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid params'}, status=400)

    qs = _citizen_challans_qs(request.user)
    total = qs.count()
    qs = qs[start:start + length]
    data = [{
        'id':         c.id,
        'ticket':     c.ticket_no,
        'psid':       c.ticket_no,
        'violation':  c.violation_type,
        'fine':       float(c.fine_amount or 0),
        'status':     c.get_payment_status_display(),
        'issue_date': c.issue_date.strftime('%Y-%m-%d') if c.issue_date else '',
        'due_date':   c.due_date.strftime('%Y-%m-%d') if c.due_date else '',
    } for c in qs]
    return JsonResponse({
        'draw': draw, 'recordsTotal': total, 'recordsFiltered': total, 'data': data,
    })





