from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.template import Context, Template
from django.utils import timezone

logger = logging.getLogger('wrongway.payments')


CHECKOUT_TEMPLATE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Demo Checkout - {{ challan.ticket_no }}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#f1f5f9;margin:0;padding:32px;}
  .card{max-width:520px;margin:24px auto;background:#1e293b;border-radius:14px;padding:28px;box-shadow:0 10px 30px rgba(0,0,0,.4);}
  h1{margin:0 0 8px 0;font-size:22px;color:#38bdf8;}
  .row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #334155;}
  .row:last-child{border-bottom:none;}
  .lbl{color:#94a3b8;}
  .val{font-weight:600;}
  .amt{font-size:24px;color:#22c55e;}
  form{margin-top:20px;display:flex;gap:8px;}
  button{flex:1;padding:12px 18px;font-size:15px;border:0;border-radius:8px;cursor:pointer;}
  .pay{background:#22c55e;color:#052e16;font-weight:700;}
  .cancel{background:#475569;color:#f1f5f9;}
  .note{font-size:12px;color:#94a3b8;margin-top:18px;line-height:1.5;}
</style>
</head>
<body>
<div class="card">
  <h1>Safe City — Demo Payment</h1>
  <div class="row"><span class="lbl">Method</span><span class="val">{{ method|upper }}</span></div>
  <div class="row"><span class="lbl">Reference</span><span class="val">{{ ref }}</span></div>
  <div class="row"><span class="lbl">Ticket</span><span class="val">{{ challan.ticket_no }}</span></div>
  <div class="row"><span class="lbl">Plate</span><span class="val">{{ challan.plate_number }}</span></div>
  <div class="row"><span class="lbl">Amount</span><span class="val amt">PKR {{ challan.fine_amount }}</span></div>
  <form method="post" action="{{ action_url }}">
    <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
    <input type="hidden" name="ref" value="{{ ref }}">
    <input type="hidden" name="challan" value="{{ challan.id }}">
    <input type="hidden" name="method" value="{{ method }}">
    <input type="hidden" name="status" value="paid">
    <button class="pay" type="submit">Confirm Payment (Demo)</button>
    <button class="cancel" type="submit" formaction="{{ cancel_url }}">Cancel</button>
  </form>
  <p class="note">This is a DEMO checkout. No real money will be charged. Configure real JazzCash / EasyPaisa / Card credentials in System Settings → Payment to enable live payments.</p>
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
<p>Challan {{ challan.ticket_no }} is now marked PAID. Redirecting…</p>
<p><a href="{{ return_url }}">Continue</a></p>
</body></html>
""")


def _render(tpl: Template, ctx: dict) -> HttpResponse:
    return HttpResponse(tpl.render(Context(ctx)))


def demo_checkout(request):
    """GET ?ref=…&challan=…&method=… — render a fake checkout page.

    POST to the same URL with status=paid marks the challan PAID and
    redirects to the gateway return URL.
    """
    from challans.models import Challan
    from admin.dig_portal.models import AuditLog

    if request.method == 'POST':
        ref = (request.POST.get('ref') or '').strip()
        challan_id = (request.POST.get('challan') or '').strip()
        method = (request.POST.get('method') or '').strip()
        status = (request.POST.get('status') or '').strip().lower()
        if not (ref and challan_id):
            return HttpResponseBadRequest('missing ref or challan')
        challan = get_object_or_404(Challan, pk=challan_id)
        return_url = f"/challan/{challan.id}/pay/done/"
        if status == 'paid':
            if challan.payment_status != Challan.PAID:
                challan.mark_paid(txn_ref=ref)
                try:
                    AuditLog.write(
                        request, 'challan.payment_submitted', 'Challan', challan.id,
                        ticket_no=challan.ticket_no,
                        txn_ref=ref, method=method, status='paid',
                        source='demo_checkout',
                    )
                except Exception as e:
                    logger.warning('demo_checkout audit failed: %s', e)
            return _render(DONE_TEMPLATE, {'return_url': return_url, 'challan': challan})
        return _render(CANCEL_TEMPLATE, {'return_url': f"/challan/{challan.id}/"})

    ref = (request.GET.get('ref') or '').strip()
    challan_id = (request.GET.get('challan') or '').strip()
    method = (request.GET.get('method') or 'demo').strip()
    if not (ref and challan_id):
        return HttpResponseBadRequest('missing ref or challan')
    challan = get_object_or_404(Challan, pk=challan_id)
    return _render(CHECKOUT_TEMPLATE, {
        'ref': ref,
        'challan': challan,
        'method': method,
        'csrf_token': getattr(request, 'csrf_token', '') or '',
        'action_url': request.path,
        'cancel_url': request.path,
    })