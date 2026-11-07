import re
from typing import Optional

_DANGEROUS = re.compile(
    r'(<script|javascript:|onerror\s*=|onload\s*=|data:text/html|'
    r'union\s+select|drop\s+table|--\s|/\*|\*/|\bor\b\s+\b1\b\s*=\s*1|'
    r'\bexec\b\s*\(|<iframe|<embed|<object|document\.cookie|window\.location)',
    re.IGNORECASE,
)


def looks_malicious(value: Optional[str]) -> bool:
    if not value:
        return False
    return bool(_DANGEROUS.search(str(value)))
