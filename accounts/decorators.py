from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages

from .permissions import user_has_permission, user_has_any_permission


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.role in roles:
                return view(request, *args, **kwargs)
            messages.error(request, "You do not have permission to access that portal.")
            return _safe_redirect(request)
        return _wrapped
    return decorator


def permission_required(permission_name):
    def decorator(view):
        @wraps(view)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if user_has_permission(request.user, permission_name):
                return view(request, *args, **kwargs)
            messages.error(
                request,
                f"Your role ({request.user.role_label}) does not grant "
                f"permission: {permission_name}."
            )
            return _safe_redirect(request)
        return _wrapped
    return decorator


def any_permission_required(*permission_names):
    def decorator(view):
        @wraps(view)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if user_has_any_permission(request.user, permission_names):
                return view(request, *args, **kwargs)
            messages.error(
                request,
                f"Your role ({request.user.role_label}) does not grant any of: "
                f"{', '.join(permission_names)}."
            )
            return _safe_redirect(request)
        return _wrapped
    return decorator


def _safe_redirect(request):
    role = request.user.role
    if role == 'DIG':
        return redirect('dig:dashboard')
    if role == 'SSP':
        return redirect('ssp_portal:dashboard')
    if role == 'SUPV':
        return redirect('supervisor_portal:dashboard')
    if role == 'OFFICER':
        return redirect('officer_portal:review_queue')
    if role == 'AUDIT':
        return redirect('audit_portal:dashboard')
    if role == 'IT':
        return redirect('it_support_portal:dashboard')
    return redirect('citizen_portal:home')


def dig_required(view):
    return role_required('DIG')(view)


def it_required(view):
    return role_required('IT')(view)


def dig_or_it_required(view):
    return role_required('DIG', 'IT')(view)


def staff_required(view):
    return role_required('DIG', 'SSP', 'SUPV', 'OFFICER', 'AUDIT', 'IT')(view)


def senior_staff_required(view):
    return role_required('DIG', 'SSP', 'SUPV', 'OFFICER', 'AUDIT')(view)


def officer_or_dig_required(view):
    return role_required('DIG', 'SSP', 'SUPV', 'OFFICER')(view)


def user_only_required(view):
    @wraps(view)
    @login_required
    def _wrapped(request, *args, **kwargs):
        u = request.user
        if u.role == 'USER':
            return view(request, *args, **kwargs)
        if u.role == 'DIG':
            return redirect('dig:dashboard')
        if u.role == 'SSP':
            return redirect('ssp_portal:dashboard')
        if u.role == 'SUPV':
            return redirect('supervisor_portal:dashboard')
        if u.role == 'OFFICER':
            return redirect('officer_portal:review_queue')
        if u.role == 'AUDIT':
            return redirect('audit_portal:dashboard')
        if u.role == 'IT':
            return redirect('it_support_portal:dashboard')
        messages.error(request, "Invalid account.")
        return redirect('auth_portal:citizen_login')
    return _wrapped
