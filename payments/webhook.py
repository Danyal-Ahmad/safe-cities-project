from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional, Tuple

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from wrongway_system.security.rate_limit import is_rate_limited, rate_limit_response

logger = logging.getLogger('wrongway.payments')

WEBHOOK_LIMIT = (60, 60)


def _load_json(request) -> Dict[str, Any]:
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            return {}
    data = {}
    for k in request.POST:
        data[k] = request.POST.get(k)
    return data


def _check_signature(request, secret: str) -> bool:
    if not secret:
        from integrations.mode import is_real
        if is_real():
            return False
        return True
    sig = request.META.get('HTTP_X_SAFECITY_SIGNATURE') or request.META.get('HTTP_X_SIGNATURE') or ''
    if not sig:
        return False
    digest = hmac.new(secret.encode('utf-8'), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, sig)


def _extract_refs(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    ticket = (
        data.get('ticket_no') or data.get('pp_BillReference') or
        data.get('billReference') or data.get('orderId') or
        data.get('merchant_order_id') or data.get('basket_id')
    )
    txn = (
        data.get('txn_ref') or data.get('pp_TxnRefNo') or
        data.get('transactionId') or data.get('transaction_id') or
        data.get('txn_id') or data.get('rrn')
    )
    status = str(
        data.get('status') or data.get('pp_ResponseCode') or
        data.get('responseCode') or data.get('response_code') or
        data.get('txn_status') or ''
    ).strip().lower()
    return (
        str(ticket).strip() if ticket else None,
        str(txn).strip() if txn else None,
        status,
    )


def _is_success(status: str) -> bool:
    if not status:
        return False
    ok = {'paid', 'success', 'successful', 'completed', 'ok', '1', '00', '000', 'approved'}
    return status in ok or status.startswith('00')


def _resolve_challan(ticket_no: Optional[str], txn_ref: Optional[str]):
    from challans.models import Challan
    from admin.dig_portal.models import AuditLog

    if ticket_no:
        c = Challan.objects.filter(ticket_no__iexact=ticket_no).first()
        if c:
            return c
    if txn_ref:
        c = Challan.objects.filter(txn_ref=txn_ref).first()
        if c:
            return c
        try:
            from payments.models import PaymentTransaction
            tx = PaymentTransaction.objects.filter(txn_ref=txn_ref).select_related('challan').first()
            if tx and tx.challan:
                return tx.challan
        except Exception:
            pass
        logs = (AuditLog.objects
                .filter(action='challan.payment_submitted', target_model='Challan')
                .order_by('-timestamp')[:50])
        for entry in logs:
            details = entry.details if isinstance(entry.details, dict) else {}
            if str(details.get('txn_ref') or '') == txn_ref and entry.target_id:
                c = Challan.objects.filter(pk=entry.target_id).first()
                if c:
                    return c
    return None


def _webhook_secret() -> str:
    try:
        from admin.dig_portal.models import SystemSettings
        cfg = SystemSettings.get().payment_config or {}
        return (cfg.get('webhook_secret') or cfg.get('shared_secret') or '').strip()
    except Exception:
        return ''


@csrf_exempt
@require_http_methods(['POST'])
def payment_webhook(request):
    if is_rate_limited(request, 'payment_webhook',
                       limit=WEBHOOK_LIMIT[0], window=WEBHOOK_LIMIT[1]):
        return rate_limit_response(request)

    secret = _webhook_secret()
    if not _check_signature(request, secret):
        logger.warning('payment webhook: invalid signature')
        return JsonResponse({'ok': False, 'error': 'invalid_signature'}, status=401)

    data = _load_json(request)
    ticket_no, txn_ref, status_raw = _extract_refs(data)

    if not ticket_no and not txn_ref:
        return JsonResponse({'ok': False, 'error': 'missing_ticket_or_txn'}, status=400)

    if not _is_success(status_raw) and status_raw:
        logger.info('payment webhook non-success status=%s ticket=%s txn=%s',
                    status_raw, ticket_no, txn_ref)
        return JsonResponse({'ok': True, 'action': 'ignored', 'status': status_raw})

    challan = _resolve_challan(ticket_no, txn_ref)
    if not challan:
        logger.warning('payment webhook: challan not found ticket=%s txn=%s', ticket_no, txn_ref)
        return JsonResponse({'ok': False, 'error': 'challan_not_found'}, status=404)

    if challan.payment_status == challan.PAID:
        return JsonResponse({
            'ok': True, 'action': 'already_paid',
            'ticket_no': challan.ticket_no,
        })

    with transaction.atomic():
        locked = type(challan).objects.select_for_update().get(pk=challan.pk)
        if locked.payment_status == locked.PAID:
            return JsonResponse({
                'ok': True, 'action': 'already_paid',
                'ticket_no': locked.ticket_no,
            })
        locked.mark_paid(txn_ref=txn_ref)
        challan = locked
    try:
        from admin.dig_portal.models import AuditLog, Notification
        AuditLog.write(
            request, 'challan.payment_webhook', 'Challan', challan.id,
            ticket=challan.ticket_no,
            amount=str(challan.fine_amount),
            txn_ref=txn_ref or '',
            status=status_raw or 'success',
            source='gateway_webhook',
        )
        Notification.objects.filter(
            category='payment_verification',
            is_read=False,
            message__icontains=challan.ticket_no,
        ).update(is_read=True)
    except Exception as e:
        logger.warning('payment webhook audit/notify failed: %s', e)

    logger.info('payment webhook PAID ticket=%s txn=%s', challan.ticket_no, txn_ref)
    return JsonResponse({
        'ok': True,
        'action': 'marked_paid',
        'ticket_no': challan.ticket_no,
        'paid_at': timezone.now().isoformat(),
    })

