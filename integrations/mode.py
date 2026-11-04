from __future__ import annotations
import os
from typing import Literal

Mode = Literal['demo', 'real']


def get_integration_mode() -> Mode:
    env = (os.environ.get('INTEGRATION_MODE') or '').strip().lower()
    if env in ('demo', 'real'):
        return env
    try:
        from admin.dig_portal.models import SystemSettings
        m = (getattr(SystemSettings.get(), 'integration_mode', None) or 'demo').strip().lower()
        if m in ('demo', 'real'):
            return m
    except Exception:
        pass
    return 'demo'


def is_demo() -> bool:
    return get_integration_mode() == 'demo'


def is_real() -> bool:
    return get_integration_mode() == 'real'

