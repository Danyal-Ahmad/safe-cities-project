from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

logger = logging.getLogger('wrongway.payments')


def _type_key(method) -> str:
    name = (getattr(method, 'name', None) or '').lower()
    provider = (getattr(method, 'provider', None) or '').lower()
    type_code = (getattr(method, 'type', None) or '').lower()
    blob = f'{name} {provider} {type_code}'
    mapping = {
        'wallet': 'jazzcash',
        'jazzcash': 'jazzcash',
        'jazz': 'jazzcash',
        'easypaisa': 'easypaisa',
        'easy paisa': 'easypaisa',
        'easy_paisa': 'easypaisa',
        'bank': 'bank',
        'card': 'card',
        'stripe': 'card',
    }
    for k, v in mapping.items():
        if k in blob:
            return v
    if 'jazz' in blob:
        return 'jazzcash'
    if 'easy' in blob or 'paisa' in blob:
        return 'easypaisa'
    if type_code == 'bank':
        return 'bank'
    if type_code == 'card':
        return 'card'
    return type_code or 'wallet'


def _jazzcash_secure_hash(fields: Dict[str, str], integrity_salt: str) -> str:
    keys = sorted(k for k in fields.keys() if fields.get(k) not in (None, ''))
    sorted_str = '&'.join(f'{k}={fields[k]}' for k in keys)
    msg = (integrity_salt + '&' + sorted_str).encode('utf-8')
    return hmac.new(integrity_salt.encode('utf-8'), msg, hashlib.sha256).hexdigest().upper()


def _cfg(method) -> dict:
    return dict(getattr(method, 'config', None) or {})


def _txn_settings(method) -> dict:
    return dict(getattr(method, 'transaction_settings', None) or {})


def _amount_pkr(challan) -> str:
    amt = getattr(challan, 'fine_amount', None) or Decimal('0')
    try:
        return f'{Decimal(amt):.0f}'
    except Exception:
        return str(amt)


def _has_keys(cfg: dict, *keys: str) -> bool:
    return all(bool(str(cfg.get(k) or '').strip()) for k in keys)


def initiate_payment(challan, method, return_url: str, callback_url: str) -> Dict[str, Any]:
    type_key = _type_key(method)
    cfg = _cfg(method)
    txn = _txn_settings(method)
    env = (txn.get('environment') or cfg.get('environment') or 'sandbox').lower()
    amount = _amount_pkr(challan)
    ticket = getattr(challan, 'ticket_no', None) or str(getattr(challan, 'id', ''))
    reference = f"SC{getattr(challan, 'id', '0')}-{uuid.uuid4().hex[:10].upper()}"

    name_l = (getattr(method, 'name', '') or '').lower()
    prov_l = (getattr(method, 'provider', '') or '').lower()
    if type_key in ('cash', 'bank') or name_l == 'cash' or prov_l == 'cash' or 'bank transfer' in name_l or 'bank transfer' in prov_l:
        return {
            'ok': False,
            'mode': 'error',
            'error': 'Cash and bank transfer are not accepted. Use JazzCash, EasyPaisa, or card.',
            'provider': type_key or 'blocked',
            'reference': reference,
        }


    if type_key == 'jazzcash' or 'jazz' in name_l:
        merchant_id = (cfg.get('merchant_id') or '').strip()
        password = (cfg.get('password') or '').strip()
        integrity = (cfg.get('integrity_salt') or cfg.get('integrity') or '').strip()
        if not (merchant_id and password and integrity):
            return _not_configured('jazzcash')

        action = (
            'https://sandbox.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform'
            if env != 'live' else
            'https://payments.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform'
        )
        try:
            amt_paisa = str(int(Decimal(amount) * 100))
        except Exception:
            amt_paisa = amount + '00'

        now = datetime.now()
        txn_datetime = now.strftime('%Y%m%d%H%M%S')
        expiry = now.strftime('%Y%m%d%H%M%S')
        bill_ref = (ticket or reference)[:20]
        fields = {
            'pp_Version': '1.1',
            'pp_TxnType': 'MPAY',
            'pp_Language': 'EN',
            'pp_MerchantID': merchant_id,
            'pp_Password': password,
            'pp_TxnRefNo': reference[:20],
            'pp_Amount': amt_paisa,
            'pp_TxnCurrency': 'PKR',
            'pp_TxnDateTime': txn_datetime,
            'pp_BillReference': bill_ref,
            'pp_Description': f'E-Challan {ticket}'[:100],
            'pp_ReturnURL': return_url or cfg.get('return_url') or '',
            'pp_TxnExpiryDateTime': expiry,
        }
        if integrity:
            try:
                fields['pp_SecureHash'] = _jazzcash_secure_hash(
                    {k: v for k, v in fields.items() if k != 'pp_SecureHash'},
                    integrity,
                )
            except Exception as e:
                logger.warning('JazzCash hash failed: %s', e)
                return _not_configured('jazzcash')

        return {
            'ok': True,
            'mode': 'form',
            'provider': 'jazzcash',
            'action_url': action,
            'fields': fields,
            'reference': reference,
            'message': 'Redirecting to JazzCash…',
        }

    if type_key == 'easypaisa':
        store_id = (cfg.get('store_id') or cfg.get('merchant_id') or '').strip()
        if not store_id:
            return _not_configured('easypaisa')
        action = (
            'https://easypaystg.easypaisa.com.pk/easypay/Index.jsf'
            if env != 'live' else
            'https://easypay.easypaisa.com.pk/easypay/Index.jsf'
        )
        fields = {
            'storeId': store_id,
            'amount': amount,
            'postBackURL': return_url or '',
            'orderRefNum': reference[:20],
            'autoRedirect': '1',
            'paymentMethod': 'InitialRequest',
            'merchantPaymentMethod': '',
        }
        return {
            'ok': True,
            'mode': 'form',
            'provider': 'easypaisa',
            'action_url': action,
            'fields': fields,
            'reference': reference,
            'message': 'Redirecting to EasyPaisa…',
        }

    if type_key == 'bank':
        return {
            'ok': True,
            'mode': 'bank',
            'provider': 'bank',
            'action_url': return_url or '',
            'fields': {
                'bank_name': cfg.get('bank_name') or cfg.get('name') or '',
                'account_title': cfg.get('account_title') or cfg.get('title') or 'Safe Cities Project',
                'account_number': cfg.get('account_number') or cfg.get('account') or '',
                'iban': cfg.get('iban') or '',
                'branch': cfg.get('branch') or '',
                'reference': reference,
                'amount': amount,
            },
            'reference': reference,
            'message': 'Pay via bank transfer using the PSID / account details.',
        }

    if type_key == 'card':
        if not _has_keys(cfg, 'publishable_key', 'secret_key'):
            return _not_configured('card')
        return {
            'ok': True,
            'mode': 'redirect',
            'provider': 'card',
            'action_url': return_url,
            'fields': {},
            'reference': reference,
            'message': 'Card gateway configured - complete on return URL.',
        }

    return _not_configured(type_key or 'wallet')


def _not_configured(provider: str) -> Dict[str, Any]:
    logger.warning('Payment gateway %s has no credentials configured', provider)
    return {
        'ok': False,
        'mode': 'error',
        'error': (
            f'{provider.title()} is active but its merchant credentials are not '
            'configured. Ask IT Support to configure the gateway credentials '
            'before attempting payment.'
        ),
    }
