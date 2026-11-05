from django import template
register = template.Library()


@register.filter
def get_item(d, key):
    if d is None:
        return None
    try:
        return d.get(key)
    except (AttributeError, TypeError):
        pass
    try:
        idx = int(key)
        return d[idx]
    except (ValueError, TypeError, KeyError, IndexError):
        try:
            return d[key]
        except (KeyError, TypeError, IndexError):
            return None


@register.filter(name='zip')
def zip_lists(a, b):
    return zip(a, b)


@register.filter
def currency(value):
    try:
        return f"PKR {int(value):,}"
    except (ValueError, TypeError):
        return value


@register.filter
def hours_ago(dt):
    from django.utils import timezone
    if not dt: return '-'
    delta = timezone.now() - dt
    mins = int(delta.total_seconds() / 60)
    if mins < 1: return 'just now'
    if mins < 60: return f'{mins}m ago'
    hrs = mins // 60
    if hrs < 24: return f'{hrs}h ago'
    days = hrs // 24
    return f'{days}d ago'


@register.filter
def filter_online_count(cameras):
    return sum(1 for c in cameras if c.health_status == 'online')


@register.filter
def filter_offline_count(cameras):
    return sum(1 for c in cameras if c.health_status == 'offline')


@register.filter
def paid_count(challans):
    return sum(1 for c in challans if c.payment_status == 'PAID')


@register.filter
def unpaid_count(challans):
    return sum(1 for c in challans if c.payment_status == 'UNPAID')


@register.filter
def voided_count(challans):
    return sum(1 for c in challans if c.payment_status == 'VOIDED')

