from __future__ import annotations

import logging

from django.http import HttpResponse, HttpResponseBadRequest
from django.template import Context, Template

logger = logging.getLogger('wrongway.payments')


CHECKOUT_TEMPLATE = Template("""{% load static %}<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Demo Checkout - {{ challan.ticket_no }}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="{% static 'css/payment-gateway-demo.css' %}">
</head>
<body>
<div class="card">
  <h1>Safe City &mdash; Demo Payment</h1>
  <div class="row"><span class="lbl">Method</span><span class="val">{{ method|upper }}</span></div>
  <div class="row"><span class="lbl">Reference</span><span class="val">{{ ref }}</span></div>
  <div class="row"><span class="lbl">Ticket</span><span class="val">{{ challan.ticket_no }}</span></div>
  <div class="row"><span class="lbl">Plate</span><span class="val">{{ challan.plate_number }}</span></div>
  <div class="row"><span class="lbl">Amount</span><span class="val amt">PKR {{ challan.fine_amount }}</span></div>
  <form method="post" action="{{ action_url }}">
    <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
    <input type="hidden" name="ref" value="{{ ref }}">
    <input type="hidden" name="method" value="{{ method }}">
    <input type="hidden" name="status" value="paid">
    <button class="pay" type="submit">Confirm Payment (Demo)</button>
    <button class="cancel" type="submit" formaction="{{ cancel_url }}?cancel=1">Cancel</button>
  </form>
  <p class="note">This is a DEMO checkout. No real money will be charged. Configure real JazzCash / EasyPaisa / Card credentials in System Settings &rarr; Payment to enable live payments.</p>
</div>
</body>
</html>
""")


CANCEL_TEMPLATE = Template("""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Payment Cancelled</title></head>
<body style="font-family:system-ui;padding:32px;background:#0f172a;color:#f1f5f9;">
<h2>Payment cancelled</h2>
<p>You cancelled the demo payment. No charge was made.</p>
<p><a style="color:#38bdf8" href="{{ return_url }}">Return to challan</a></p>
</body></html>
""")


DONE_TEMPLATE = Template("""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Payment Received</title>
<meta http-equiv="refresh" content="2;url={{ return_url }}">
<style>body{font-family:system-ui;padding:32px;background:#0f172a;color:#f1f5f9;} a{color:#38bdf8}</style>
</head>
<body>
<h2 style="color:#22c55e">Payment successful</h2>
<p>Challan {{ challan.ticket_no }} is now marked PAID. Redirecting&hellip;</p>
<p><a href="{{ return_url }}">Continue</a></p>
</body></html>
""")


def _render(tpl: Template, ctx: dict) -> HttpResponse:
    return HttpResponse(tpl.render(Context(ctx)))


def _pending_transaction(ref):
    from payments.models import PaymentTransaction
    return (
        PaymentTransaction.objects
        .filter(txn_ref=ref, status=PaymentTransaction.STATUS_PENDING)
        .select_related('challan')
        .first()
    )


def demo_checkout(request):
    """Simulated gateway checkout (used when merchant keys are not configured).

    GET  ?ref=…  — render the confirmation page for a PENDING PaymentTransaction.
    POST (CSRF) — visitor confirms; the matching pending transaction is settled,
    which is the ONLY path (besides the signed webhook) that marks a challan PAID.
    """
    from admin.dig_portal.models import AuditLog

    if request.method == 'POST':
        if request.POST.get('cancel') or request.GET.get('cancel'):
            ref = (request.POST.get('ref') or '').strip()
            txn = _pending_transaction(ref) if ref else None
            return_url = f"/challan/{txn.challan.id}/" if txn else "/"
            return _render(CANCEL_TEMPLATE, {'return_url': return_url})

        ref = (request.POST.get('ref') or '').strip()
        status = (request.POST.get('status') or '').strip().lower()
        if not ref:
            return HttpResponseBadRequest('missing payment reference')

        txn = _pending_transaction(ref)
        if txn is None or txn.challan is None:
            logger.warning('demo_checkout: unknown or already-used reference %r', ref)
            return HttpResponseBadRequest('unknown or already-used payment reference')

        challan = txn.challan
        return_url = f"/challan/{challan.id}/pay/done/"
        if status == 'paid' and challan.payment_status != 'PAID':
            txn.status = 'success'
            txn.gateway_ref = ref
            txn.save(update_fields=['status', 'gateway_ref', 'updated_at'])
            challan.mark_paid(txn_ref=ref, payment_method=txn.provider)
            try:
                AuditLog.write(
                    request, 'challan.payment_submitted', 'Challan', challan.id,
                    ticket_no=challan.ticket_no,
                    txn_ref=ref, method=txn.provider, status='paid',
                    source='demo_checkout',
                )
            except Exception as e:
                logger.warning('demo_checkout audit failed: %s', e)
        return _render(DONE_TEMPLATE, {'return_url': return_url, 'challan': challan})

    ref = (request.GET.get('ref') or '').strip()
    method = (request.GET.get('method') or 'demo').strip()
    if not ref:
        return HttpResponseBadRequest('missing payment reference')

    txn = _pending_transaction(ref)
    if txn is None or txn.challan is None:
        logger.warning('demo_checkout GET: unknown reference %r', ref)
        return HttpResponseBadRequest('unknown or already-used payment reference')

    challan = txn.challan
    return _render(CHECKOUT_TEMPLATE, {
        'ref': ref,
        'challan': challan,
        'method': method or txn.provider,
        'csrf_token': getattr(request, 'csrf_token', '') or '',
        'action_url': request.path,
        'cancel_url': request.path,
    })
