from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

import requests

logger = logging.getLogger('wrongway.excise')

_SANDBOX_REGISTRY = {
    'LEA1001': {
        'owner_name': 'Muhammad Ali',
        'cnic': '35202-1234567-1',
        'address': 'Block A, Sector 1',
        'phone': '03001234567',
        'vehicle_type': 'car',
        'make_year': '2020',
        'color': 'White',
        'chassis_no': 'CH-SANDBOX-001',
        'make': 'Honda Civic',
    },
    'ABC999': {
        'owner_name': 'Sara Khan',
        'cnic': '35202-9999999-9',
        'address': 'Block B, Sector 2',
        'phone': '03009999999',
        'vehicle_type': 'car',
        'make_year': '2019',
        'color': 'Black',
        'chassis_no': 'CH-SANDBOX-002',
        'make': 'Toyota Corolla',
    },
    'PUB123': {
        'owner_name': 'Demo Owner',
        'cnic': '35202-1111111-1',
        'address': 'Block C, Sector 3',
        'phone': '03001111111',
        'vehicle_type': 'car',
        'make_year': '2021',
        'color': 'Silver',
        'chassis_no': 'CH-SANDBOX-003',
        'make': 'Suzuki Alto',
    },
}


def _normalize_plate(plate: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', (plate or '').upper())


def _settings():
    try:
        from admin.dig_portal.models import SystemSettings
        return SystemSettings.get()
    except Exception:
        return None


def lookup_by_plate(plate_number: str) -> Dict[str, Any]:
    from integrations.mode import is_demo, is_real
    plate = (plate_number or '').strip().upper()
    if not plate or plate == 'UNKNOWN':
        return {}

    compact = _normalize_plate(plate)
    sys = _settings()

    api_url = ''
    api_key = ''
    if sys is not None:
        api_url = (getattr(sys, 'excise_api_url', None) or '').strip()
        api_key = (getattr(sys, 'excise_api_key', None) or '').strip()
    api_url = api_url or os.environ.get('EXCISE_API_URL', '').strip()
    api_key = api_key or os.environ.get('EXCISE_API_KEY', '').strip()

    if api_url and is_real():
        try:
            url = f"{api_url}&plate={plate}" if '?' in api_url else f"{api_url.rstrip('/')}?plate={plate}"
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'SafeCities-Project/1.0',
            }
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            r = requests.get(url, headers=headers, timeout=8)
            if r.ok:
                data = r.json() if r.content else {}
                if isinstance(data, dict):
                    if isinstance(data.get('data'), dict):
                        data = data['data']
                    elif isinstance(data.get('result'), dict):
                        data = data['result']
                if isinstance(data, dict) and data:
                    out = _normalize_response(data)
                    out['source'] = 'excise_api'
                    vtype = (out.get('vehicle_type') or '').lower()
                    if vtype and vtype not in ('car', 'automobile', 'sedan', 'suv', 'hatchback', ''):
                        logger.info('Excise returned non-car type=%s plate=%s - ignored (car-only scope)', vtype, plate)
                        return {}
                    return out
            logger.warning('Excise API HTTP %s plate=%s', getattr(r, 'status_code', '?'), plate)
        except Exception as e:
            logger.warning('Excise API error plate=%s: %s', plate, e)

    if is_demo():
        if compact in _SANDBOX_REGISTRY:
            out = dict(_SANDBOX_REGISTRY[compact])
            out['source'] = 'excise_demo'
            return out
        return {}

    return {}


def _normalize_response(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'owner_name': data.get('owner_name') or data.get('name') or data.get('owner'),
        'cnic': data.get('cnic') or data.get('cnic_number'),
        'address': data.get('address') or data.get('owner_address'),
        'phone': data.get('phone') or data.get('mobile') or data.get('contact'),
        'vehicle_type': (data.get('vehicle_type') or data.get('type') or data.get('body_type') or 'car'),
        'make_year': data.get('make_year') or data.get('year') or data.get('model_year'),
        'color': data.get('color') or data.get('vehicle_color'),
        'chassis_no': data.get('chassis_no') or data.get('chassis') or data.get('chassis_number'),
        'make': data.get('make') or data.get('make_model'),
    }

