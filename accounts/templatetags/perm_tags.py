"""
Permission template tags - read from accounts/permissions.py
which is auto-generated from permission.json.

Usage in templates:
  {% load perm_tags %}
  {% if request.user|has_perm:'add_camera' %}
    <a>Add Camera</a>
  {% endif %}

  {% if request.user|has_any_perm:'view_challans,add_manual_challan' %}
    <a>Chalans</a>
  {% endif %}
"""
from django import template
from django.utils.safestring import mark_safe

from accounts.permissions import user_has_permission, user_has_any_permission

register = template.Library()


@register.filter(name='has_perm')
def has_perm(user, permission_key):
    """Return True if the user has the given permission key.
    Use in templates as: {% if user|has_perm:"add_camera" %}
    (double-quoted string required for smartif compatibility)"""
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
    """Simple tag version for use in {% if %} blocks that need to compare
    the result. Usage: {% if_perm user "add_camera" as can_add %}
    This avoids smartif's single-quote parsing limitation entirely."""
    return bool(has_perm(user, permission_key))


@register.filter(name='has_any_perm')
def has_any_perm(user, permission_keys):
    """permission_keys can be a comma-separated string or a list of strings."""
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
def perm_nav(user, permission_key, css_class='', icon=''):
    """Return a hidden placeholder if the user lacks the permission.
    Useful for collapsing sidebar items in-place."""
    if not user or not getattr(user, 'is_authenticated', False):
        return mark_safe('')
    if user_has_permission(user, permission_key):
        return mark_safe(f'data-perm="{permission_key}" data-allowed="1"')
    return mark_safe(f'data-perm="{permission_key}" data-allowed="0"')


@register.filter(name='role_label')
def role_label(user):
    """Human-readable role label."""
    if not user or not getattr(user, 'is_authenticated', False):
        return ''
    role = getattr(user, 'role', '')
    from accounts.permissions import ROLE_HIERARCHY
    info = ROLE_HIERARCHY.get(role, {})
    return info.get('label', role)
