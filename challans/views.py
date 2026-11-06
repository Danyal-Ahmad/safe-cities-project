from django.shortcuts import render, get_object_or_404, redirect, Http404
from django.urls import reverse
from django.contrib import messages
from django.http import FileResponse, HttpResponseForbidden, HttpResponse
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.db.models import Q
from django.core.cache import cache

from accounts.models import User
from admin.shared.net import client_ip

from .models import Challan
from .pdf_service import _needs_nadra_excise_integration
from wrongway_system.security.rate_limit import rate_limit_response


import re


import os as _os


RATE_LIMIT_MAX_REQUESTS = int(_os.environ.get('SEARCH_RATE_LIMIT', 20))
RATE_LIMIT_WINDOW = int(_os.environ.get('SEARCH_RATE_WINDOW', 60))  


PDF_RATE_LIMIT = (20, 60)


_EVIDENCE_EXT_WHITELIST = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
_EVIDENCE_MAX_BYTES = 5 * 1024 * 1024


def _pdf_rate_limited(request) -> bool:
    if request.user.is_authenticated:
        ident = f'u{request.user.pk}'
    else:
        ident = 'i' + (
            client_ip(request)
            or request.META.get('REMOTE_ADDR', '127.0.0.1')
        )
    key = f'challan_pdf_rl:{ident}'
    count = cache.get(key, 0)
    if count >= PDF_RATE_LIMIT[0]:
        return True
    cache.set(key, count + 1, PDF_RATE_LIMIT[1])
    return False


def _validate_evidence_file(f):
    if f is None:
        return True, ''
    name = (getattr(f, 'name', '') or '').lower()
    if not any(name.endswith(ext) for ext in _EVIDENCE_EXT_WHITELIST):
        return False, 'Evidence must be an image (JPG, JPEG, PNG, WEBP, or GIF).'
    if f.size > _EVIDENCE_MAX_BYTES:
        return False, 'Evidence image must be under 5 MB.'
    try:
        from PIL import Image
        f.seek(0)
        with Image.open(f) as im:
            im.verify()
        f.seek(0)
    except Exception:
        return False, 'Evidence file is not a valid image.'
    return True, ''


def _check_rate_limit(request) -> bool:
    if request.user.is_authenticated and hasattr(request.user, 'role') and request.user.role != 'USER':
        return True
    ip = (
        client_ip(request)
        or request.META.get('REMOTE_ADDR', '127.0.0.1')
    )
    cache_key = f"challan_search_rl:{ip}"
    count = cache.get(cache_key, 0)
    if count >= RATE_LIMIT_MAX_REQUESTS:
        return False
    cache.set(cache_key, count + 1, RATE_LIMIT_WINDOW)
    return True


def _resolve_officer(challan):
    created_by = getattr(challan, "created_by", None)
    if created_by is not None and getattr(created_by, "is_authenticated", True):
        return created_by
    det = getattr(challan, "detection", None) or getattr(challan, "source_detection", None)
    if det is not None:
        user = getattr(det, "reviewed_by", None)
        if user is not None:
            return user
    return None


def _officer_signature_url(officer):
    if not officer:
        return None
    sig = getattr(officer, "signature", None)
    if sig and getattr(sig, "url", None):
        return sig.url
    return None


def _officer_signature_name(officer):
    if not officer:
        return None
    return (
        getattr(officer, "signature_name", None)
        or officer.get_full_name()
        or officer.first_name
        or officer.username
    )


def _officer_signature_designation(officer):
    if not officer:
        return None
    return (
        getattr(officer, "signature_designation", None)
        or getattr(officer, "designation", None)
        or officer.get_role_display()
    )


def _officer_signature_stamp_url(officer):
    if not officer:
        return None
    stamp = getattr(officer, "signature_stamp", None)
    if stamp and getattr(stamp, "url", None):
        return stamp.url
    return None


def home(request):
    raw_q = (request.GET.get('q') or '').strip()
    if raw_q and not (request.GET.get('plate') or request.GET.get('cnic')):
        digits = re.sub(r'\D', '', raw_q)
        if len(digits) >= 11:
            request.GET = request.GET.copy()
            request.GET['cnic'] = raw_q
        else:
            request.GET = request.GET.copy()
            request.GET['plate'] = raw_q.upper()
    raw_plate = (request.GET.get('plate') or '').strip().upper()
    raw_cnic = (request.GET.get('cnic') or '').strip()

    plate = re.sub(r'[^A-Z0-9\-]', '', raw_plate)[:12]
    cnic = re.sub(r'[^0-9\-]', '', raw_cnic)[:15]
    cnic_digits = re.sub(r'\D', '', cnic)[:13]

    challans = None
    searched = False
    if plate or cnic_digits:
        if not _check_rate_limit(request):
            return HttpResponse(
                "Too many search requests. Please wait a minute before trying again.",
                status=429,
                content_type="text/plain",
            )
        searched = True
        q = Q()
        if plate:
            plate_compact = plate.replace('-', '').replace(' ', '')
            q |= (
                Q(plate_number__iexact=plate)
                | Q(plate_number__iexact=plate_compact)
                | Q(plate_number__icontains=plate)
                | Q(plate_number__icontains=plate_compact)
                | Q(ticket_no__icontains=plate)
            )
        if cnic_digits:
            formatted_cnic = (
                f"{cnic_digits[:5]}-{cnic_digits[5:12]}-{cnic_digits[12:]}"
                if len(cnic_digits) == 13 else cnic
            )
            q |= (
                Q(cnic__iexact=cnic_digits)
                | Q(cnic__iexact=formatted_cnic)
                | Q(cnic__iexact=cnic)
                | Q(cnic__icontains=cnic_digits)
            )
        if q:
            qs = list(Challan.objects.filter(q).order_by('-issue_date')[:100])
            if plate:
                pc = plate.replace('-', '').replace(' ', '').upper()
                def _norm(s):
                    return (s or '').replace('-', '').replace(' ', '').upper()
                exactish = [c for c in qs if pc == _norm(c.plate_number) or pc in _norm(c.plate_number)]
                challans = (exactish or qs)[:25]
            else:
                challans = qs[:25]
        else:
            challans = []
        is_guest = not request.user.is_authenticated
        signer = TimestampSigner()
        for c in (challans or []):
            if is_guest and c.owner_name:
                parts = c.owner_name.split()
                c.display_owner = ' '.join([parts[0]] + [p[0] + '.' for p in parts[1:]]) if len(parts) > 1 else parts[0]
            else:
                c.display_owner = c.owner_name or '-'
            try:
                c.signed_token = signer.sign(str(c.id))
            except Exception:
                c.signed_token = ''

    return render(request, 'challan/home.html', {
        'challans': challans, 'plate': plate, 'cnic': cnic, 'searched': searched,
    })


def _citizen_owns_challan(user, challan):
    if not user or not user.is_authenticated or getattr(user, 'role', None) != 'USER':
        return False
    def _digits(v):
        return ''.join(ch for ch in str(v or '') if ch.isdigit())
    if user.cnic and challan.cnic:
        if user.cnic == challan.cnic or _digits(user.cnic) == _digits(challan.cnic):
            return True
    if user.phone and getattr(challan, 'phone', None) and user.phone == challan.phone:
        return True
    try:
        from accounts.models import VehicleRegistration
        plates = {
            (p or '').upper().replace(' ', '').replace('-', '')
            for p in VehicleRegistration.objects.filter(user=user).values_list('plate_number', flat=True)
        }
        plate = (challan.plate_number or '').upper().replace(' ', '').replace('-', '')
        if plate and plate in plates:
            return True
    except Exception:
        pass
    return False


def _mask_challan_pii(challan):
    def _mask_name(name):
        if not name:
            return name
        parts = str(name).split()
        if len(parts) > 1:
            return ' '.join([parts[0]] + [p[0] + '.' for p in parts[1:]])
        return parts[0]

    def _mask_cnic(v):
        d = ''.join(ch for ch in str(v or '') if ch.isdigit())
        if len(d) == 13:
            return f"{d[:5]}-•••••••-{d[12]}"
        return '•••••-•••••••-•' if v else v

    challan.owner_name = _mask_name(challan.owner_name)
    challan.cnic = _mask_cnic(challan.cnic)
    challan.phone = '•••• •••••••' if challan.phone else challan.phone
    if challan.address:
        challan.address = str(challan.address)[:12] + '…'
    challan.chassis_no = '•••••••' if challan.chassis_no else challan.chassis_no


def challan_detail(request, challan_id):
    from appeals.models import ChallanAppeal
    from admin.it_support_portal.models import PaymentMethod

    challan = get_object_or_404(Challan.objects.select_related('camera', 'detection'), pk=challan_id)
    is_guest = not request.user.is_authenticated
    is_owner = _citizen_owns_challan(request.user, challan) if not is_guest else False
    has_active = ChallanAppeal.has_active_appeal(challan)

    def _cnic_digits(s):
        return ''.join(ch for ch in (s or '') if ch.isdigit())

    can_appeal = (
        challan.payment_status == Challan.UNPAID
        and not has_active
    )  
    existing_appeals = list(
        ChallanAppeal.objects.filter(challan=challan).order_by('-created_at')[:5]
    )

    payment_methods = [
        m for m in PaymentMethod.active_for_citizens()
        if (m.name or '').lower() != 'cash'
        and (m.provider or '').lower() != 'cash'
        and m.type != 'cash'
        and 'bank transfer' not in (m.name or '').lower()
        and 'bank transfer' not in (m.provider or '').lower()
    ]

    if request.method == 'POST' and request.POST.get('action') == 'submit_appeal':
        if not can_appeal:
            messages.error(request, "This challan cannot be appealed (already under review, paid, or voided).")
            return redirect('challans:challan_detail', challan_id=challan.id)

        reason = (request.POST.get('reason') or '').strip()
        review_reason = (request.POST.get('review_reason') or '').strip()
        if review_reason:
            reason = f'[{review_reason}] {reason}'.strip()
        guest_cnic = _cnic_digits(request.POST.get('guest_cnic') or '')
        guest_name = (request.POST.get('guest_name') or '').strip()[:120]

        if len(reason) < 20:
            messages.error(request, "Please provide a detailed reason (at least 20 characters).")
            return redirect(request.get_full_path() or f'/challan/{challan.id}/?tab=review')

        if is_guest:
            challan_cnic = _cnic_digits(challan.cnic)
            if not guest_cnic or len(guest_cnic) != 13:
                messages.error(request, "Enter the 13-digit CNIC linked to this challan to appeal without signing in.")
                return redirect(f'/challan/{challan.id}/?tab=review')
            if challan_cnic and guest_cnic != challan_cnic:
                messages.error(request, "CNIC does not match this challan. Sign in with the owner account or use the correct CNIC.")
                return redirect(f'/challan/{challan.id}/?tab=review')
            evidence = request.FILES.get('evidence_file')
            ok, err = _validate_evidence_file(evidence)
            if not ok:
                messages.error(request, err)
                return redirect(f'/challan/{challan.id}/?tab=review')
            appeal = ChallanAppeal(
                challan=challan,
                submitted_by=None,
                guest_cnic=guest_cnic,
                guest_name=guest_name or (challan.owner_name or ''),
                reason=reason,
                status=ChallanAppeal.PENDING,
            )
        else:
            if not is_owner and request.user.role == User.USER:
                messages.error(request, "You can only appeal your own challans.")
                return redirect('challans:challan_detail', challan_id=challan.id)
            appeal = ChallanAppeal(
                challan=challan,
                submitted_by=request.user,
                reason=reason,
                status=ChallanAppeal.PENDING,
            )
        if request.FILES.get('evidence_file'):

            evidence = request.FILES['evidence_file']
            ok, err = _validate_evidence_file(evidence)
            if not ok:
                messages.error(request, err)
                return redirect(f'/challan/{challan.id}/?tab=review')
            appeal.evidence_file = evidence
        appeal.save()
        try:
            from admin.dig_portal.models import AuditLog
            AuditLog.write(request, 'appeal.submit', 'ChallanAppeal', appeal.id,
                           ticket=challan.ticket_no, guest=is_guest)
        except Exception:
            pass
        try:
            from accounts.models import User as _User
            from admin.dig_portal.models import Notification
            for ssp in _User.objects.filter(role=_User.SSP, is_active=True):
                Notification.objects.create(
                    recipient=ssp,
                    title=f"[ACTION REQUIRED] New Appeal | {challan.ticket_no}",
                    message=(
                        f"NEW APPEAL SUBMITTED\n"
                        f"Challan No: {challan.ticket_no}\n"
                        f"Plate Number: {challan.plate_number}\n"
                        f"Violation: {challan.get_violation_type_display()}\n"
                        f"Fine: PKR {challan.fine_amount}\n"
                        f"Submitted by: {guest_name or 'Guest (CNIC matched)'}\n"
                        f"Reason: {reason}"
                    ),
                    category='appeal_submit',
                    target_url=reverse('ssp_portal:decide_appeal', args=[appeal.id]),
                )
        except Exception:
            pass
        messages.success(request, "Appeal submitted. SSP will review your case.")
        return redirect(f'/challan/{challan.id}/?tab=review')

    if is_guest and not is_owner:
        _mask_challan_pii(challan)

    return render(request, 'challan/detail.html', {
        'challan': challan,
        'is_guest': is_guest,
        'is_owner': is_owner,
        'can_appeal': can_appeal,
        'issuing_officer': _resolve_officer(challan),
        'officer_signature_url': _officer_signature_url(_resolve_officer(challan)),
        'officer_signature_name': _officer_signature_name(_resolve_officer(challan)),
        'officer_signature_designation': _officer_signature_designation(_resolve_officer(challan)),
        'officer_signature_stamp_url': _officer_signature_stamp_url(_resolve_officer(challan)),
        'officer_staff_id': getattr(_resolve_officer(challan), 'staff_id', None) or '-',
        'officer_region': getattr(_resolve_officer(challan), 'region', None) or '-',
        'has_active_appeal': has_active,
        'existing_appeals': existing_appeals,
        'active_tab': request.GET.get('tab') or 'base',
        'payment_methods': payment_methods,
        'psid': getattr(challan, 'psid', '') or '',
        'needs_nadra_excise': _needs_nadra_excise_integration(challan),
    })


def challan_detail_signed(request, signed_token):
    signer = TimestampSigner()
    try:
        unsigned = signer.unsign(signed_token, max_age=30 * 24 * 3600)
        challan_id = int(unsigned)
    except (BadSignature, SignatureExpired, ValueError):
        return render(request, 'challan/signed_link_expired.html', status=403)
    challan = get_object_or_404(Challan, pk=challan_id)
    return render(request, 'challan/detail.html', {
        'challan': challan, 'is_guest': True, 'can_appeal': False, 'from_signed_link': True,
        'needs_nadra_excise': _needs_nadra_excise_integration(challan),
    })


def challan_pdf(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    if request.user.is_authenticated:
        if request.user.role in ('DIG', 'SSP', 'SUPV', 'OFFICER', 'AUDIT', 'IT'):
            pass
        elif (challan.cnic and request.user.cnic and challan.cnic == request.user.cnic) or \
             (challan.phone and request.user.phone and challan.phone == request.user.phone):
            pass
        else:
            return HttpResponseForbidden("You can only view your own challans.")
    else:
        token = (request.GET.get('token') or '').strip()
        if not token:
            return HttpResponseForbidden("Authentication or signed token required.")
        signer = TimestampSigner()
        try:
            unsigned = signer.unsign(token, max_age=30 * 24 * 3600)
            if int(unsigned) != challan.id:
                return HttpResponseForbidden("Invalid token.")
        except (BadSignature, SignatureExpired, ValueError):
            return HttpResponseForbidden("Expired or invalid token.")

    force = (request.GET.get('regen') or '') == '1'


    if _pdf_rate_limited(request):
        return rate_limit_response(request)

    if force or not challan.pdf_file:
        from challans.pdf_service import save_challan_pdf
        try:
            save_challan_pdf(challan, force=force)
        except Exception:
            save_challan_pdf(challan, force=True)
        challan.refresh_from_db()
    try:
        return FileResponse(
            challan.pdf_file.open('rb'),
            as_attachment=True,
            content_type='application/pdf',
            filename=f"challan_{challan.ticket_no}.pdf",
        )
    except Exception:
        raise Http404("PDF not available.")


def guest_pay(request, challan_id):
    from admin.it_support_portal.models import PaymentMethod
    from integrations.payments import initiate_payment
    from payments.models import PaymentTransaction

    challan = get_object_or_404(Challan, pk=challan_id)
    if challan.payment_status == Challan.PAID:
        messages.info(request, f"Challan {challan.ticket_no} is already paid.")
        return redirect('challans:challan_detail', challan_id=challan.id)
    if challan.payment_status == Challan.VOIDED:
        messages.error(request, "This challan is voided and cannot be paid.")
        return redirect('challans:challan_detail', challan_id=challan.id)

    methods = list(PaymentMethod.active_for_citizens())

    if request.method == 'POST':
        method_id = request.POST.get('payment_method') or request.GET.get('method')
        method = None
        if method_id:
            method = PaymentMethod.objects.filter(pk=method_id, status=PaymentMethod.STATUS_ACTIVE).first()
        if not method and methods:
            method = methods[0]

        if not method:
            messages.error(request, "No digital payment method is configured.")
            return redirect('challans:guest_pay', challan_id=challan.id)

        return_url = request.build_absolute_uri(f'/challan/{challan.id}/pay/done/')
        callback_url = request.build_absolute_uri('/api/v1/payment/webhook/')
        init = initiate_payment(challan, method, return_url, callback_url)

        if not init.get('ok'):
            messages.error(request, init.get('error') or "Payment could not be initiated.")
            return redirect('challans:guest_pay', challan_id=challan.id)

        PaymentTransaction.objects.create(
            ticket_no=challan.ticket_no,
            challan=challan,
            provider=(init.get('provider') or method.name or 'demo'),
            amount=challan.fine_amount,
            status=PaymentTransaction.STATUS_PENDING,
            txn_ref=init.get('reference'),
        )
        try:
            from admin.dig_portal.models import AuditLog
            AuditLog.write(request, 'challan.payment_initiated', 'Challan', challan.id,
                           ticket_no=challan.ticket_no, method=method.name,
                           mode=init.get('mode'), reference=init.get('reference'))
        except Exception:
            pass

        if init.get('mode') == 'form' and init.get('action'):
            return render(request, 'challan/pay_redirect.html', {
                'challan': challan,
                'init': init,
                'payment_method': method,
            })

        if init.get('mode') == 'demo':
            return redirect(init.get('action_url') or f"/challan/{challan.id}/")

        if init.get('mode') == 'bank':
            return render(request, 'challan/guest_pay.html', {
                'challan': challan,
                'payment_methods': methods,
                'bank_instructions': init.get('fields') or {},
                'has_active': ChallanAppeal.has_active_appeal(challan),
            })

        messages.info(request, "Payment session started. Complete it at the gateway.")
        return redirect(init.get('action_url') or f"/challan/{challan.id}/")

    return render(request, 'challan/guest_pay.html', {
        'challan': challan,
        'payment_methods': methods,
        'has_active': ChallanAppeal.has_active_appeal(challan),
    })


def guest_pay_done(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    if challan.payment_status == Challan.PAID:
        messages.success(request, f"Payment received. Challan {challan.ticket_no} is PAID.")
    else:
        messages.info(
            request,
            f"Payment for {challan.ticket_no} is still awaiting confirmation from the gateway. "
            "Refresh this page in a few seconds."
        )
    return redirect('challans:challan_detail', challan_id=challan.id)
