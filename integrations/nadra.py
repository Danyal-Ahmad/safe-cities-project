from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger('wrongway.nadra')

_CNIC_RE = re.compile(r'^\d{5}-\d{7}-\d$')


def is_valid_cnic_format(cnic: str) -> bool:
    return bool(_CNIC_RE.match((cnic or '').strip()))


def _settings():
    try:
        from admin.dig_portal.models import SystemSettings
        return SystemSettings.get()
    except Exception:
        return None


def verify_cnic(cnic: str, expected_name: Optional[str] = None) -> Dict[str, Any]:
    from integrations.mode import is_real
    cnic = (cnic or '').strip()
    if not is_valid_cnic_format(cnic):
        return {
            'ok': False, 'cnic': cnic, 'name': None,
            'status': 'bad_format', 'source': 'format_only', 'name_match': None,
        }

    sys = _settings()
    api_url = ''
    api_key = ''
    if sys is not None:
        api_url = (getattr(sys, 'nadra_api_url', None) or '').strip()
        api_key = (getattr(sys, 'nadra_api_key', None) or '').strip()
    api_url = api_url or os.environ.get('NADRA_API_URL', '').strip()
    api_key = api_key or os.environ.get('NADRA_API_KEY', '').strip()

    if api_url and is_real():
        try:
            url = f"{api_url}&cnic={cnic}" if '?' in api_url else f"{api_url.rstrip('/')}?cnic={cnic}"
            headers = {'Accept': 'application/json', 'User-Agent': 'SafeCities-Project/1.0'}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            r = requests.get(url, headers=headers, timeout=8)
            if r.ok:
                data = r.json() if r.content else {}
                if isinstance(data, dict) and isinstance(data.get('data'), dict):
                    data = data['data']
                name = (data.get('name') or data.get('citizen_name') or data.get('full_name') or '').strip()
                status = (data.get('status') or 'valid').lower()
                ok = status in ('valid', 'active', 'verified', 'ok', '1', 'true')
                name_match = None
                if expected_name and name:
                    name_match = expected_name.strip().lower() in name.lower() or name.lower() in expected_name.strip().lower()
                return {
                    'ok': ok, 'cnic': cnic, 'name': name or None,
                    'status': 'valid' if ok else 'invalid',
                    'source': 'nadra_api', 'name_match': name_match,
                }
            logger.warning('NADRA API HTTP %s cnic=%s', r.status_code, cnic)
        except Exception as e:
            logger.warning('NADRA API error cnic=%s: %s', cnic, e)

    return {
        'ok': False, 'cnic': cnic, 'name': None,
        'status': 'unavailable', 'source': 'nadra_unconfigured', 'name_match': None,
    }

