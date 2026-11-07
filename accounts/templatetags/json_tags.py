import json

from django import template

register = template.Library()


@register.filter(name='to_json')
def to_json(value):
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return 'null'


@register.filter(name='json_esc')
def json_esc(value):
    try:
        return json.dumps(str(value), ensure_ascii=False)
    except Exception:
        return '""'

