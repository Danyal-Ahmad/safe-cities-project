import re

CNIC_RE = re.compile(r'^\d{5}-\d{7}-\d$|^\d{12,13}$')


def normalize_cnic(value):
    return re.sub(r'[^0-9]', '', value or '')


def cnic_is_valid(value):
    return bool(CNIC_RE.match(value or ''))
