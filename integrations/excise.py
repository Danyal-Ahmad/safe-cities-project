from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

import requests

logger = logging.getLogger('wrongway.excise')

_OFFLINE_REGISTRY = {
    'LEA1234': {
        'owner_name': 'Ahmad Raza',
        'cnic': '35202-7481936-4',
        'address': 'House 23, Street 4, DHA Phase 5, Lahore',
        'phone': '0300-8452197',
        'vehicle_type': 'car',
        'make_year': '2022',
        'color': 'White',
        'chassis_no': 'NZE1415092834',
        'make': 'Toyota Corolla GLi',
    },
    'LEA1001': {
        'owner_name': 'Muhammad Bilal Khokhar',
        'cnic': '35201-3347821-9',
        'address': '34-B Gulberg III, Lahore Cantt',
        'phone': '0321-4478021',
        'vehicle_type': 'car',
        'make_year': '2020',
        'color': 'Graphite Grey',
        'chassis_no': 'FK8123456789',
        'make': 'Honda Civic Oriel',
    },
    'ABC999': {
        'owner_name': 'Sara Fatima Khan',
        'cnic': '35202-9912045-6',
        'address': 'House 112, Block C, Model Town, Lahore',
        'phone': '0333-5219874',
        'vehicle_type': 'car',
        'make_year': '2019',
        'color': 'Black',
        'chassis_no': 'NCP13129876',
        'make': 'Toyota Corolla Altis',
    },
    'LEB456': {
        'owner_name': 'Usman Ghani',
        'cnic': '35201-7842109-2',
        'address': 'Flat 4B, Askari 11, Lahore Cantt',
        'phone': '0301-8874521',
        'vehicle_type': 'car',
        'make_year': '2021',
        'color': 'Silver',
        'chassis_no': 'MBH4112345',
        'make': 'Suzuki Cultus VXL',
    },
    'LZA789': {
        'owner_name': 'Ayesha Siddiqui',
        'cnic': '35202-1122334-0',
        'address': 'House 7, Street 21, Bahria Town, Lahore',
        'phone': '0345-9987412',
        'vehicle_type': 'car',
        'make_year': '2023',
        'color': 'Pearl White',
        'chassis_no': 'JTMHV05J4021',
        'make': 'Toyota Yaris ATIV',
    },
    'ACR597': {
        'owner_name': 'Tahir Mehmood Bhatti',
        'cnic': '37405-1122334-3',
        'address': 'Chak 45 GB, Jaranwala Road, Faisalabad',
        'phone': '0300-4127856',
        'vehicle_type': 'car',
        'make_year': '2018',
        'color': 'Blue',
        'chassis_no': 'EK3123987',
        'make': 'Honda City Aspire',
    },
    'LEO826': {
        'owner_name': 'Kiran Shahzadi',
        'cnic': '35202-4455667-7',
        'address': 'House 89, Sector C, Bahria Orchard, Lahore',
        'phone': '0312-7412589',
        'vehicle_type': 'car',
        'make_year': '2020',
        'color': 'Red',
        'chassis_no': 'ZA81P0123456',
        'make': 'Suzuki Swift GL',
    },
    'LWX552': {
        'owner_name': 'Zafar Iqbal Chaudhry',
        'cnic': '34101-8877445-1',
        'address': 'House 156, Block R-3, Johar Town, Lahore',
        'phone': '0322-6985214',
        'vehicle_type': 'car',
        'make_year': '2017',
        'color': 'Gunmetal',
        'chassis_no': 'WDD2040123A',
        'make': 'Mercedes-Benz C180',
    },
    'LES305': {
        'owner_name': 'Hina Aslam Malhi',
        'cnic': '33100-5544332-8',
        'address': 'House 45, Model Colony, Sargodha',
        'phone': '0334-8521479',
        'vehicle_type': 'car',
        'make_year': '2019',
        'color': 'White Pearl',
        'chassis_no': 'MCW25123456',
        'make': 'Suzuki Alto VXL',
    },
    'LHR007': {
        'owner_name': 'Sheikh Hamza Farooq',
        'cnic': '35228-9911223-5',
        'address': 'Suite 12, 2nd Floor, Hafeez Center, Gulberg III, Lahore',
        'phone': '0300-1122334',
        'vehicle_type': 'car',
        'make_year': '2022',
        'color': 'Athletic Blue',
        'chassis_no': '1HGCV1F34LA',
        'make': 'Honda City 1.5 AS',
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
        if compact in _OFFLINE_REGISTRY:
            out = dict(_OFFLINE_REGISTRY[compact])
            out['source'] = 'excise_offline'
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

