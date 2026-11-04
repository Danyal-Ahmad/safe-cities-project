from __future__ import annotations

import re
import html
from typing import Optional

PLATE_RE = re.compile(r'^[A-Za-z0-9\-\s]{3,15}$')
CNIC_RE = re.compile(r'^\d{5}-?\d{7}-?\d$')
PHONE_RE = re.compile(r'^\+?[\d\s\-]{10,20}$')
EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')
INT_ID_RE = re.compile(r'^\d{1,12}$')
SAFE_TEXT_RE = re.compile(r'^[\w\s\.\,\-\@\+\(\)/:#]{0,500}$', re.UNICODE)

_DANGEROUS = re.compile(
    r"(<script|javascript:|onerror\s*=|onload\s*=|union\s+select|drop\s+table|"
    r"insert\s+into|or\s+1\s*=\s*1|;--|#\s*$|\.\./|\.\.\\)",
    re.IGNORECASE,
)


def clean_text(value: Optional[str], max_len: int = 500) -> str:
    if value is None:
        return ''
    s = str(value)
    s = ''.join(ch for ch in s if ord(ch) >= 32 or ch in '\n\t')
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) > max_len:
        s = s[:max_len]
    return s


def escape_html(value: Optional[str]) -> str:
    return html.escape(clean_text(value), quote=True)


def looks_malicious(value: Optional[str]) -> bool:
    if not value:
        return False
    return bool(_DANGEROUS.search(str(value)))


def validate_plate(value: str) -> str:
    v = clean_text(value, 15).upper().replace(' ', '')
    if not v or not PLATE_RE.match(v):
        raise ValueError('Invalid plate number format')
    if looks_malicious(v):
        raise ValueError('Invalid plate number')
    return v


def validate_cnic(value: str) -> str:
    v = clean_text(value, 20)
    digits = re.sub(r'\D', '', v)
    if len(digits) != 13:
        raise ValueError('CNIC must be 13 digits')
    return f'{digits[:5]}-{digits[5:12]}-{digits[12]}'


def validate_phone(value: str) -> str:
    v = clean_text(value, 20)
    if not PHONE_RE.match(v):
        raise ValueError('Invalid phone number')
    return v


def validate_email(value: str) -> str:
    v = clean_text(value, 120).lower()
    if not EMAIL_RE.match(v):
        raise ValueError('Invalid email address')
    return v


def validate_int_id(value) -> int:
    s = str(value).strip()
    if not INT_ID_RE.match(s):
        raise ValueError('Invalid id')
    n = int(s)
    if n < 1:
        raise ValueError('Invalid id')
    return n


def safe_post(request, key: str, default: str = '', max_len: int = 500) -> str:
    raw = request.POST.get(key, default)
    if raw is None:
        return default
    s = clean_text(raw, max_len)
    if looks_malicious(s):
        raise ValueError(f'Invalid input for {key}')
    return s


def safe_get(request, key: str, default: str = '', max_len: int = 200) -> str:
    raw = request.GET.get(key, default)
    if raw is None:
        return default
    s = clean_text(raw, max_len)
    if looks_malicious(s):
        raise ValueError(f'Invalid input for {key}')
    return s

