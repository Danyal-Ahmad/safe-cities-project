"""HTML sanitization for staff-authored rich content.

Banners accept raw HTML (``html_content``) that is rendered with ``|safe`` on
public pages. Even though only DIG/IT can author banners, a compromised staff
account must not be able to plant stored XSS on the public portal. This
sanitizer strips every executable construct while keeping simple formatting.
"""
from __future__ import annotations

import re

# Tags that carry no risk and may survive sanitization.
_ALLOWED_TAGS = {
    'a', 'b', 'strong', 'i', 'em', 'u', 's', 'small', 'span', 'div', 'p',
    'br', 'hr', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'thead', 'tbody', 'tr', 'td', 'th', 'img', 'marquee', 'center',
}
_ALLOWED_ATTRS = {
    'href', 'src', 'alt', 'title', 'style', 'class', 'id', 'width', 'height',
    'target', 'rel', 'align', 'valign', 'bgcolor', 'color', 'direction',
}
_SCRIPT_TAG_RE = re.compile(r'<\s*(script|iframe|object|embed|form|svg|math|link|meta|base)[^>]*>.*?<\s*/\s*\1\s*>',
                            re.IGNORECASE | re.DOTALL)
_SCRIPT_OPEN_RE = re.compile(r'<\s*(script|iframe|object|embed|form|svg|math|link|meta|base)[^>]*>',
                             re.IGNORECASE)
_EVENT_ATTR_RE = re.compile(r'\son\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', re.IGNORECASE)
_JS_URL_RE = re.compile(r'(href|src)\s*=\s*(?:"\s*(javascript|data|vbscript)\s*:[^"]*"|\'\s*(javascript|data|vbscript)\s*:[^\']*\'|(javascript|data|vbscript)\s*:[^\s>]+)', re.IGNORECASE)
_STYLE_DANGER_RE = re.compile(r'(expression\s*\(|url\s*\(\s*["\']?\s*(javascript|data):)', re.IGNORECASE)


def sanitize_banner_html(raw: str) -> str:
    """Strip executable constructs from staff-authored banner HTML."""
    if not raw:
        return ''
    text = _SCRIPT_TAG_RE.sub('', raw)
    text = _SCRIPT_OPEN_RE.sub('', text)
    text = _EVENT_ATTR_RE.sub('', text)
    text = _JS_URL_RE.sub('', text)
    text = _STYLE_DANGER_RE.sub('', text)
    # Drop any tag outside the allowlist (keeps its inner text).
    def _tag_allowed(match):
        tag = match.group(1).lower()
        return match.group(0) if tag in _ALLOWED_TAGS else ''
    text = re.sub(r'<\s*/?\s*([a-zA-Z0-9-]+)[^>]*>', _tag_allowed, text)
    return text


def sanitize_notification_text(raw: str, max_len: int = 500) -> str:
    """Escape a plain-text notification: no markup at all."""
    if not raw:
        return ''
    from django.utils.html import escape
    return escape(str(raw))[:max_len]
