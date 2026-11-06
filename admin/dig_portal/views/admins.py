from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib import messages
from django.utils import timezone
from django.conf import settings as dj_settings

from .system import self_profile
from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from django.db.models import Q
from accounts.models import User
from accounts.decorators import dig_required
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from accounts.decorators import staff_required


@dig_required
def admin_list(request):
    from accounts.models import User
    if request.method == 'POST' and request.POST.get('action') == 'update_permissions':
        uid = request.POST.get('user_id')
        target = User.objects.filter(pk=uid).first()
        if not target:
            messages.error(request, "User not found.")
            return redirect('dig:admin_list')
        flag_map = {
            'perm_view_challans': 'can_review_detections',
            'perm_review_appeals': 'can_review_appeals',
            'perm_view_analytics': 'can_view_own_performance',
            'perm_flag_dig': 'can_flag_for_dig',
            'perm_internal_notes': 'can_add_internal_notes',
            'perm_live_tracking': 'can_live_tracking',
            'perm_live_monitor': 'can_live_monitor',
            'perm_record_payment': 'can_record_payment',
            'perm_manage_blacklist': 'can_manage_blacklist',
        }
        from accounts.models import OfficerProfile
        prof, _ = OfficerProfile.objects.get_or_create(officer=target)
        for post_key, attr in flag_map.items():
            if hasattr(prof, attr):
                setattr(prof, attr, post_key in request.POST)
        prof.save()
        target.save()
        try:
            from ..models import AuditLog
            AuditLog.write(request, 'admin.permissions_update', 'User', target.id)
        except Exception:
            pass
        messages.success(request, f"Permissions updated for {target.email or target.username}.")
        return redirect('dig:admin_list')

    from .admin_profiles import all_dropdowns, ROLE_PROFILES
    import json
    admins = list(User.objects.filter(role__in=[User.DIG, User.SSP, User.SUPERVISOR, User.OFFICER, User.AUDIT, User.IT_SUPPORT]).order_by('role', '-date_joined'))
    from accounts.models import OfficerProfile
    profiles = {op.officer_id: op for op in OfficerProfile.objects.filter(officer_id__in=[u.id for u in admins])}
    for u in admins:
        op = profiles.get(u.id)
        for attr in (
            'can_review_detections', 'can_review_appeals',
            'can_view_own_performance', 'can_live_tracking', 'can_live_monitor',
            'can_record_payment', 'can_manage_blacklist',
            'can_flag_for_dig', 'can_add_internal_notes',
        ):
            setattr(u, attr, bool(getattr(op, attr, False)) if op else False)
        if u.role in (User.DIG, User.SSP, User.SUPERVISOR, User.IT_SUPPORT) and not op:
            u.can_live_monitor = True
            u.can_live_tracking = True
    role_profiles_json = json.dumps({
        role: {
            'designation':     p.get('designation', ''),
            'department':      p.get('department', ''),
            'region':          p.get('region', ''),
            'staff_id_prefix': p.get('staff_id_prefix', 'PSC'),
            'rank':            p.get('rank', ''),
            'office':          p.get('default_office', ''),
        }
        for role, p in ROLE_PROFILES.items()
    })
    from accounts.permissions import ROLE_PERMISSION_MATRIX, PERMISSIONS
    role_perm_map = {
        role: sorted(list(perms))
        for role, perms in ROLE_PERMISSION_MATRIX.items()
    }
    return render(request, 'dashboard/dig/admin_list.html', {
        'admins': admins,
        'dropdowns': all_dropdowns(),
        'role_profiles_json': role_profiles_json,
        'role_perm_map_json': json.dumps(role_perm_map),
        'all_permissions': list(PERMISSIONS),
    })


@dig_required
@xframe_options_sameorigin
def admin_edit(request, user_id):
    ROLE_CHOICES_FOR_EDIT = [
        ('DIG', 'DIG'), ('SSP', 'SSP'), ('SUPV', 'Supervisor'),
        ('OFFICER', 'Officer'), ('AUDIT', 'Audit'), ('IT', 'IT Support'),
    ]

    from accounts.permissions import (
        ROLE_HIERARCHY, ROLE_PERMISSION_MATRIX, summarize_role,
    )
    from .admin_profiles import all_dropdowns, ROLE_PROFILES
    import json
    _ae_dropdowns = all_dropdowns()
    _ae_role_profiles_json = json.dumps({
        role: {
            'designation':     p.get('designation', ''),
            'department':      p.get('department', ''),
            'region':          p.get('region', ''),
            'staff_id_prefix': p.get('staff_id_prefix', 'PSC'),
            'rank':            p.get('rank', ''),
            'office':          p.get('default_office', ''),
        }
        for role, p in ROLE_PROFILES.items()
    })

    target = get_object_or_404(User, pk=user_id)
    if target.role == User.USER:
        messages.error(request, "Use the Users section to edit citizens.")
        return redirect('dig:admin_list')

    dig_count = User.objects.filter(role=User.DIG, is_active=True).count()

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        if not first_name:
            messages.error(request, "Name is required.")
            return render(request, 'dashboard/dig/admin_edit.html', {
            'roles': ROLE_CHOICES_FOR_EDIT,
                'target': target, 'role_options': ROLE_HIERARCHY.items(),
                'dig_count': dig_count, 'dropdowns': _ae_dropdowns,
                'role_profiles_json': _ae_role_profiles_json,
            })

        new_role = request.POST.get('role', target.role)
        if new_role not in dict(User.ROLE_CHOICES).keys():
            messages.error(request, f"Invalid role: {new_role}")
            return render(request, 'dashboard/dig/admin_edit.html', {
            'roles': ROLE_CHOICES_FOR_EDIT,
                'target': target, 'role_options': ROLE_HIERARCHY.items(),
                'dig_count': dig_count, 'dropdowns': _ae_dropdowns,
                'role_profiles_json': _ae_role_profiles_json,
            })
        if target.role == User.DIG and new_role != User.DIG and dig_count <= 1:
            messages.error(
                request,
                "Cannot demote the last active DIG account. Promote another "
                "user to DIG first."
            )
            return render(request, 'dashboard/dig/admin_edit.html', {
            'roles': ROLE_CHOICES_FOR_EDIT,
                'target': target, 'role_options': ROLE_HIERARCHY.items(),
                'dig_count': dig_count, 'dropdowns': _ae_dropdowns,
                'role_profiles_json': _ae_role_profiles_json,
            })
        if new_role != target.role:
            old_role_label = target.role_label
            target.role = new_role
            new_perms = ROLE_PERMISSION_MATRIX.get(new_role, frozenset())
            messages.success(
                request,
                f"Role changed from {old_role_label} to {dict(User.ROLE_CHOICES)[new_role]}. "
                f"Auto-assigned {len(new_perms)} permissions."
            )

        target.first_name = first_name
        new_email = (request.POST.get('email') or '').strip()
        new_phone = (request.POST.get('phone') or '').strip()
        if not new_email:
            messages.error(request, "Email is required for admin accounts.")
            return render(request, 'dashboard/dig/admin_edit.html', {
            'roles': ROLE_CHOICES_FOR_EDIT,
                'target': target, 'role_options': ROLE_HIERARCHY.items(),
                'dig_count': dig_count, 'dropdowns': _ae_dropdowns,
                'role_profiles_json': _ae_role_profiles_json,
            })
        if new_email != (target.email or '') and User.objects.filter(email=new_email).exists():
            messages.error(request, f"Another account already uses email {new_email}.")
            return render(request, 'dashboard/dig/admin_edit.html', {
            'roles': ROLE_CHOICES_FOR_EDIT,
                'target': target, 'role_options': ROLE_HIERARCHY.items(),
                'dig_count': dig_count, 'dropdowns': _ae_dropdowns,
                'role_profiles_json': _ae_role_profiles_json,
            })
        if new_phone and new_phone != (target.phone or '') and User.objects.filter(phone=new_phone).exists():
            messages.error(request, f"Another account already uses phone {new_phone}.")
            return render(request, 'dashboard/dig/admin_edit.html', {
            'roles': ROLE_CHOICES_FOR_EDIT,
                'target': target, 'role_options': ROLE_HIERARCHY.items(),
                'dig_count': dig_count, 'dropdowns': _ae_dropdowns,
                'role_profiles_json': _ae_role_profiles_json,
            })
        target.email = new_email
        target.username = new_email
        target.phone = new_phone or None
        target.cnic = request.POST.get('cnic') or None
        target.designation = request.POST.get('designation') or None
        target.department = request.POST.get('department') or None
        target.staff_id = request.POST.get('staff_id') or None
        target.region = request.POST.get('region') or None
        target.is_active = request.POST.get('is_active') in ('on', '1', 'true', 'True')
        if 'avatar' in request.FILES:
            avatar = request.FILES['avatar']
            if avatar.content_type and not avatar.content_type.startswith('image/'):
                messages.error(request, "Avatar must be an image file.")
                return render(request, 'dashboard/dig/admin_edit.html', {
            'roles': ROLE_CHOICES_FOR_EDIT,
                    'target': target, 'role_options': ROLE_HIERARCHY.items(),
                    'dig_count': dig_count, 'dropdowns': _ae_dropdowns,
                    'role_profiles_json': _ae_role_profiles_json,
                })
            try:
                from io import BytesIO
                from django.core.files.base import ContentFile
                from PIL import Image
                img = Image.open(avatar)
                img = img.convert('L').convert('RGB')
                w, h = img.size
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                img = img.crop((left, top, left + side, top + side)).resize((256, 256))
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=88)
                buf.seek(0)
                target.avatar.save(f"staff_{target.pk or 'new'}.jpg", ContentFile(buf.read()), save=False)
            except Exception:
                target.avatar = avatar
        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            if len(new_password) < 12:
                messages.error(request, "Password must be at least 12 characters.")
                return render(request, 'dashboard/dig/admin_edit.html', {
            'roles': ROLE_CHOICES_FOR_EDIT,
                    'target': target, 'role_options': ROLE_HIERARCHY.items(),
                    'dig_count': dig_count, 'dropdowns': _ae_dropdowns,
                    'role_profiles_json': _ae_role_profiles_json,
                })
            target.set_password(new_password)
            messages.info(request, f"Password changed for {target.display_name}.")
        target.save()
        AuditLog.write(request, 'admin.edit', 'User', target.id, name=target.display_name, role=target.role)
        messages.success(request, f"Admin {target.display_name} updated.")
        if request.GET.get('embed') == '1' or request.POST.get('embed') == '1':
            from django.http import HttpResponse
            return HttpResponse(
                "<script>try{parent.location.reload();}catch(e){location.href='/portal/dig/admins/';}</script>"
            )
        return redirect('dig:admin_list')
    from accounts.permissions import get_role_permissions
    _perms = sorted(get_role_permissions(target.role))[:24]
    return render(request, 'dashboard/dig/admin_edit.html', {
            'roles': ROLE_CHOICES_FOR_EDIT,
        'target': target,
        'role_options': ROLE_HIERARCHY.items(),
        'role_permissions': _perms,
        'dig_count': dig_count,
        'dropdowns': _ae_dropdowns,
        'role_profiles_json': _ae_role_profiles_json,
        'role_summaries': {code: summarize_role(code) for code in ROLE_HIERARCHY.keys()},
    })


@dig_required
def admin_add(request):
    from .admin_profiles import (
        get_profile, generate_staff_id,
    )
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        cnic = request.POST.get('cnic', '').strip()
        role = request.POST.get('role', 'OFFICER')
        password = request.POST.get('password', '').strip()
        avatar = request.FILES.get('avatar')

        if not username:
            username = email
        if not first_name:
            first_name = username or (email.split('@')[0] if email else 'Staff')

        profile = get_profile(role)
        designation = request.POST.get('designation', '').strip() or profile.get('designation', '')
        department  = request.POST.get('department',  '').strip() or profile.get('department',  '')
        region      = request.POST.get('region',      '').strip() or profile.get('region',      '')
        staff_id = request.POST.get('staff_id', '').strip()
        if not staff_id:
            staff_id = profile.get('staff_id_prefix', 'PSC') + '-TBD'

        status_choice    = request.POST.get('status',           '').strip()

        if not email and not username:
            messages.error(request, "Email or Username is required for admin accounts.")
            return redirect('dig:admin_list')
        if not password or len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return redirect('dig:admin_list')
        if email and User.objects.filter(email=email).exists():
            messages.error(request, f"An account with email {email} already exists.")
            return redirect('dig:admin_list')
        if username and User.objects.filter(username=username).exists():
            messages.error(request, f"An account with username {username} already exists.")
            return redirect('dig:admin_list')
        if phone and User.objects.filter(phone=phone).exists():
            messages.error(request, f"An account with phone {phone} already exists.")
            return redirect('dig:admin_list')
        if cnic and User.objects.filter(cnic=cnic, role__in=User.STAFF_ROLES).exists():
            messages.error(request, f"A staff account with CNIC {cnic} already exists.")
            return redirect('dig:admin_list')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            phone=phone or None,
            cnic=cnic or None,
            role=role,
        )
        user.designation = designation or None
        user.department = department or None
        if staff_id.endswith('-TBD'):
            user.staff_id = generate_staff_id(role, user.pk)
        else:
            user.staff_id = staff_id
        user.region = region or None
        if avatar:
            user.avatar = avatar
        if status_choice in ('inactive', 'suspended'):
            user.is_active = False
        user.save()
        AuditLog.write(request, 'admin.create', 'User', user.id,
                       role=user.role, name=user.display_name,
                       staff_id=user.staff_id, auto_assigned=True)
        messages.success(request, f"Admin account '{user.display_name}' created with Staff ID {user.staff_id}.")
        return redirect('dig:admin_list')
    from .admin_profiles import all_dropdowns as _dd, ROLE_PROFILES as _rp
    import json as _json
    return render(request, 'dashboard/dig/admin_add.html', {
        'dropdowns': _dd(),
        'role_profiles_json': _json.dumps({k: {'designation': v.get('designation',''), 'department': v.get('department',''), 'region': v.get('region',''), 'staff_id_prefix': v.get('staff_id_prefix','PSC')} for k,v in _rp.items()}),
        'roles': [User.SSP, User.SUPERVISOR, User.OFFICER, User.AUDIT, User.IT_SUPPORT],
    })


@dig_required
def citizen_users_list(request):
    from accounts.models import User
    q = (request.GET.get('q') or '').strip()
    users = User.objects.filter(role=User.USER).order_by('-date_joined')
    if q:
            users = users.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) |
            Q(email__icontains=q) | Q(cnic__icontains=q) | Q(phone__icontains=q) |
            Q(username__icontains=q)
        )
    return render(request, 'dashboard/dig/citizen_users_list.html', {
        'users': users[:200],
        'q': q,
        'total': users.count(),
    })


@dig_required
def citizen_set_password(request):
    if request.method != 'POST':
        return redirect('dig:citizen_users_list')
    uid = request.POST.get('user_id')
    pw = (request.POST.get('new_password') or '').strip()
    pw2 = (request.POST.get('confirm_password') or '').strip()
    target = get_object_or_404(User, pk=uid, role=User.USER)
    if len(pw) < 8:
        messages.error(request, "Password must be at least 8 characters.")
        return redirect('dig:citizen_users_list')
    if pw != pw2:
        messages.error(request, "Passwords do not match.")
        return redirect('dig:citizen_users_list')
    target.set_password(pw)
    target.save()
    AuditLog.write(request, 'citizen.password_reset', 'User', target.id)
    messages.success(request, f"Password updated for {target.display_name}.")
    return redirect('dig:citizen_users_list')


@dig_required
def staff_set_password(request):
    if request.method != 'POST':
        return redirect('dig:admin_list')
    uid = request.POST.get('user_id')
    pw = (request.POST.get('new_password') or '').strip()
    pw2 = (request.POST.get('confirm_password') or '').strip()
    target = get_object_or_404(User, pk=uid)
    if target.role == User.USER:
        messages.error(request, "Use citizen password reset for citizens.")
        return redirect('dig:admin_list')
    if len(pw) < 12:
        messages.error(request, "Password must be at least 12 characters.")
        return redirect('dig:admin_list')
    if pw != pw2:
        messages.error(request, "Passwords do not match.")
        return redirect('dig:admin_list')
    target.set_password(pw)
    target.save()
    AuditLog.write(request, 'admin.password_set', 'User', target.id)
    messages.success(request, f"Password updated for {target.display_name}.")
    return redirect('dig:admin_list')


@dig_required
def admin_reset_request_list(request):
    from accounts.models import AdminPasswordResetRequest

    pending = (
        AdminPasswordResetRequest.objects
        .select_related('target_user')
        .filter(status=AdminPasswordResetRequest.STATUS_PENDING)
        .order_by('-created_at')
    )
    resolved = (
        AdminPasswordResetRequest.objects
        .select_related('target_user', 'resolved_by')
        .exclude(status=AdminPasswordResetRequest.STATUS_PENDING)
        .order_by('-created_at')[:50]
    )

    return render(request, 'dashboard/dig/admin_reset_request_list.html', {
        'page_title': 'Admin Password Resets',
        'pending': pending,
        'resolved': resolved,
    })


@dig_required
def admin_reset_password(request, token):
    from accounts.models import AdminPasswordResetRequest
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    req = get_object_or_404(
        AdminPasswordResetRequest.objects.select_related('target_user'),
        token=token,
    )

    if req.status != AdminPasswordResetRequest.STATUS_PENDING:
        messages.error(request, "This reset request is no longer pending.")
        return redirect('dig:admin_reset_request_list')

    if req.is_expired():
        req.status = AdminPasswordResetRequest.STATUS_CANCELLED
        req.save(update_fields=['status'])
        messages.error(request, "This reset request has expired.")
        return redirect('dig:admin_reset_request_list')

    target = req.target_user

    if request.method == 'POST':
        new_password = (request.POST.get('new_password') or '').strip()
        confirm_password = (request.POST.get('confirm_password') or '').strip()
        if not new_password:
            messages.error(request, "New password is required.")
        elif new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
        elif len(new_password) < 12:
            messages.error(request, "Password must be at least 12 characters.")
        else:
            try:
                validate_password(new_password, user=target)
            except ValidationError as ve:
                for msg in ve.messages:
                    messages.error(request, msg)
                return render(request, 'dashboard/dig/admin_reset_password.html', {
                    'page_title': 'Reset Admin Password',
                    'req': req,
                    'target': target,
                })
            target.set_password(new_password)
            target.save(update_fields=['password'])

            AuditLog.write(request, 'admin.password_reset', 'User', target.id)

            req.status = AdminPasswordResetRequest.STATUS_RESOLVED
            req.resolved_at = timezone.now()
            req.resolved_by = request.user
            req.save(update_fields=['status', 'resolved_at', 'resolved_by'])

            Notification.objects.filter(
                recipient=request.user,
                category='system',
                target_url__icontains=token,
            ).update(is_read=True)

            messages.success(
                request,
                f"Password reset for {target.display_name} ({target.email}). "
                "They can now sign in with the new password."
            )
            return redirect('dig:admin_reset_request_list')

        return render(request, 'dashboard/dig/admin_reset_password.html', {
            'page_title': 'Reset Admin Password',
            'req': req,
            'target': target,
        })

    return render(request, 'dashboard/dig/admin_reset_password.html', {
        'page_title': 'Reset Admin Password',
        'req': req,
        'target': target,
    })


@staff_required
def staff_change_password(request):
    return self_profile(request)


@dig_required


def regional_access(request):
    ssp_users = User.objects.filter(role=User.SSP)
    supervisor_users = User.objects.filter(role=User.SUPERVISOR)
    return render(request, 'dashboard/dig/regional_access.html', {
        'ssp_users': ssp_users, 'supervisor_users': supervisor_users,
    })
