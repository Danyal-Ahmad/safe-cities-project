from django import template
from django.utils.safestring import mark_safe

from accounts.permissions import user_has_permission, user_has_any_permission

register = template.Library()


@register.filter(name='has_perm')
def has_perm(user, permission_key):
    if not user:
        return False
    if not getattr(user, 'is_authenticated', False):
        return False
    try:
        return user_has_permission(user, permission_key)
    except Exception:
        return False


@register.simple_tag
def if_perm(user, permission_key):
    return bool(has_perm(user, permission_key))


@register.filter(name='has_any_perm')
def has_any_perm(user, permission_keys):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if isinstance(permission_keys, str):
        keys = [k.strip() for k in permission_keys.split(',') if k.strip()]
    else:
        keys = list(permission_keys)
    try:
        return user_has_any_permission(user, keys)
    except Exception:
        return False


@register.simple_tag
@register.filter(name='role_label')
def role_label(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return ''
    role = getattr(user, 'role', '')
    from accounts.permissions import ROLE_HIERARCHY
    info = ROLE_HIERARCHY.get(role, {})
    return info.get('label', role)
