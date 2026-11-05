from datetime import timedelta

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.core.exceptions import ValidationError
from django_ratelimit.decorators import ratelimit
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse

from django.utils.http import url_has_allowed_host_and_scheme

from accounts.forms import LoginForm, UserSignupForm
from accounts.models import User, PasswordResetToken
from accounts.backends import find_user_by_identifier


ADMIN_ROLE_DASHBOARD_URLS = {
    User.DIG:         'dig:dashboard',
    User.SSP:         'ssp_portal:dashboard',
    User.SUPERVISOR:  'supervisor_portal:dashboard',
    User.OFFICER:     'officer_portal:review_queue',
    User.AUDIT:       'audit_portal:dashboard',
    User.IT_SUPPORT:  'it_support_portal:dashboard',
}

ADMIN_ROLE_PORTAL_PATHS = {
    User.DIG:         '/portal/dig/',
    User.SSP:         '/portal/ssp/',
    User.SUPERVISOR:  '/portal/supervisor/',
    User.OFFICER:     '/portal/officer/',
    User.AUDIT:       '/portal/audit/',
    User.IT_SUPPORT:  '/portal/it/',
    User.USER:        '/portal/citizen/',
}

ALLOWED_ADMIN_ROLES = tuple(ADMIN_ROLE_DASHBOARD_URLS.keys())

RESET_TOKEN_TTL_HOURS = 2


@ratelimit(key='ip', rate='20/15m', method='POST', block=True)
def admin_login(request):
    if request.user.is_authenticated:
        return redirect('auth_portal:role_redirect')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_locked:
                messages.error(request, "Your account is locked. Please contact your administrator.")
                return render(request, 'auth/admin/admin_login.html', {'form': form})
            if user.role not in ALLOWED_ADMIN_ROLES:
                messages.error(request, "Citizens must use the citizen login page.")
                return render(request, 'auth/admin/admin_login.html', {'form': form})

            login(request, user, backend='accounts.backends.PhoneOrEmailBackend')
            ip = request.META.get('HTTP_X_FORWARDED_FOR')
            if ip:
                ip = ip.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            user.last_login_ip = ip
            user.reset_failed_login()
            messages.success(request, f"Welcome, {user.display_name}.")
            return _login_redirect(request, default='auth_portal:role_redirect')

        identifier = (request.POST.get('username') or '').strip()
        candidate = find_user_by_identifier(identifier)
        if candidate and candidate.is_locked:
            messages.error(
                request,
                "Your account is temporarily locked due to multiple failed login "
                "attempts. Please try again later or contact your administrator."
            )
        elif candidate and candidate.role not in ALLOWED_ADMIN_ROLES:
            messages.error(request, "Citizens must use the citizen login page.")
        else:
            messages.error(request, "Invalid credentials.")
    else:
        form = LoginForm(request)
    return render(request, 'auth/admin/admin_login.html', {'form': form})


def _login_redirect(request, default):
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    if default.startswith('/'):
        return redirect(default)
    return redirect(default)


@login_required
def role_redirect(request):
    user = request.user
    target_path = ADMIN_ROLE_PORTAL_PATHS.get(user.role)
    if target_path:
        return redirect(target_path)
    messages.error(request, "Your role does not have a portal configured.")
    return redirect('auth_portal:admin_login')


@ratelimit(key='ip', rate='30/15m', method='POST', block=True)
def citizen_login(request):
    if request.user.is_authenticated:
        if request.user.role != User.USER:
            return redirect('auth_portal:role_redirect')
        return redirect('/portal/citizen/')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.role != User.USER:
                messages.error(request, "Staff must use the staff login page.")
                return render(request, 'auth/citizen/citizen_login.html', {'form': form})
            if user.is_locked:
                messages.error(request, "Your account is temporarily locked due to multiple failed login attempts. Please try again later.")
                return render(request, 'auth/citizen/citizen_login.html', {'form': form})
            login(request, user, backend='accounts.backends.PhoneOrEmailBackend')
            messages.success(request, f"Welcome, {user.display_name}.")
            return _login_redirect(request, default='/portal/citizen/')

        identifier = (request.POST.get('username') or '').strip()
        candidate = find_user_by_identifier(identifier)
        if candidate and candidate.is_locked:
            messages.error(
                request,
                "Your account is temporarily locked due to multiple failed login "
                "attempts. Please try again later or contact your administrator."
            )
        elif candidate and candidate.role != User.USER:
            messages.error(request, "Staff must use the staff login page.")
        else:
            messages.error(request, "Invalid CNIC or password.")
    else:
        form = LoginForm(request)
    return render(request, 'auth/citizen/citizen_login.html', {'form': form})


def citizen_signup(request):
    if request.user.is_authenticated:
        return redirect('/portal/citizen/')
    if request.method == 'POST':
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = User.USER
            # Found during the 2026 hardening pass: the form permits phone-only
            # signup but sets email=None, while the DB column is NOT NULL -
            # a phone-only signup 500'd with IntegrityError. Coerce to ''.
            if user.email is None:
                user.email = ''
            user.save()
            login(request, user, backend='accounts.backends.PhoneOrEmailBackend')
            messages.success(request, f"Welcome, {user.display_name}! Your account has been created.")
            return redirect('/portal/citizen/')
    else:
        form = UserSignupForm()
    return render(request, 'auth/citizen/citizen_signup.html', {'form': form})


def admin_forgot_password(request):
    if request.user.is_authenticated:
        return redirect('auth_portal:role_redirect')

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        if not email:
            messages.error(request, "Email address is required.")
            return render(request, 'auth/admin/admin_forgot_password.html', {'step': 'request'})

        user = User.objects.filter(email__iexact=email).first()
        if user and user.role != User.USER and user.is_active and not user.is_locked:
            from accounts.models import AdminPasswordResetRequest
            AdminPasswordResetRequest.objects.filter(
                target_user=user, status=AdminPasswordResetRequest.STATUS_PENDING
            ).update(status=AdminPasswordResetRequest.STATUS_CANCELLED)

            req = AdminPasswordResetRequest.objects.create(
                target_user=user,
                requested_by_email=email,
                ip_address=_client_ip(request),
            )
            try:
                _notify_dig_for_reset(request, user, req)
            except Exception:
                pass

        return render(request, 'auth/admin/admin_forgot_password.html', {
            'step': 'sent', 'email': email,
        })

    return render(request, 'auth/admin/admin_forgot_password.html', {'step': 'request'})


def forgot_password(request):
    """Citizen forgot password.

    Step 1: visitor submits a CNIC. If an active citizen account matches, a
    single-use reset token is created and the reset link is DELIVERED to the
    registered email address only. The token is never rendered into the
    response, and the result message is identical whether or not the account
    exists (anti-enumeration). Step 2 happens on /auth/citizen/reset/<token>/
    (citizen_reset_confirm) after the visitor follows the emailed link.
    """
    if request.method == 'POST':
        cnic = (request.POST.get('cnic') or '').strip()
        cnic_digits = ''.join(ch for ch in cnic if ch.isdigit())

        if not cnic_digits or len(cnic_digits) != 13:
            messages.error(request, "Please enter a valid 13-digit CNIC.")
            return render(request, 'auth/citizen/forgot_password.html', {
                'step': 'request', 'cnic': cnic,
            })

        user = User.objects.filter(cnic=cnic, role=User.USER, is_active=True).first()
        if not user:
            user = User.objects.filter(cnic=cnic_digits, role=User.USER, is_active=True).first()

        if user:
            PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
            token = PasswordResetToken.objects.create(user=user)
            token.ip_address = _client_ip(request)
            token.save(update_fields=['ip_address'])
            _send_reset_email(request, user, token, kind='citizen')
            AuditLog_object = _get_audit_log()
            if AuditLog_object is not None:
                try:
                    AuditLog_object.write(request, 'auth.reset_requested', 'User', user.id,
                                          delivery='email')
                except Exception:
                    pass

        messages.success(request, (
            "If an active citizen account exists for that CNIC, a password "
            "reset link has been sent to the registered email address. The "
            "link is valid for %d hours." % RESET_TOKEN_TTL_HOURS
        ))
        return render(request, 'auth/citizen/forgot_password.html', {'step': 'request'})

    return render(request, 'auth/citizen/forgot_password.html', {'step': 'request'})


def citizen_reset_confirm(request, token):
    tok = _get_valid_token(token)
    if not tok:
        return render(request, 'auth/citizen/forgot_password.html', {
            'step': 'invalid',
        })

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
                validate_password(new_password, user=tok.user)
            except ValidationError as ve:
                for msg in ve.messages:
                    messages.error(request, msg)
                return render(request, 'auth/citizen/forgot_password.html', {
                    'step': '2', 'token': token, 'user_name': tok.user.display_name,
                    'cnic': tok.user.cnic or '',
                })
            # Atomically claim the token BEFORE setting the password. The old
            # flow was check-then-act (`used_at is None` read in
            # _get_valid_token, then written back after) - two concurrent
            # requests sharing a token link could BOTH pass and reset the
            # password twice. The guarded UPDATE makes single-use airtight:
            # only the first claimant proceeds.
            claimed = PasswordResetToken.objects.filter(
                pk=tok.pk, used_at__isnull=True,
            ).update(used_at=timezone.now())
            if not claimed:
                return render(request, 'auth/citizen/forgot_password.html', {
                    'step': 'invalid',
                })
            tok.user.set_password(new_password)
            tok.user.save()
            messages.success(request, "Password updated successfully! You can now sign in.")
            return redirect('auth_portal:citizen_login')

        return render(request, 'auth/citizen/forgot_password.html', {
            'step': 'verified', 'token': token, 'user_name': tok.user.display_name,
            'cnic': tok.user.cnic or '',
        })

    return render(request, 'auth/citizen/forgot_password.html', {
        'step': 'verified', 'token': token, 'user_name': tok.user.display_name,
        'cnic': tok.user.cnic or '',
    })


def _get_valid_token(token_str):
    try:
        tok = PasswordResetToken.objects.select_related('user').get(token=token_str)
    except PasswordResetToken.DoesNotExist:
        return None
    if tok.used_at is not None:
        return None
    if tok.created_at < timezone.now() - timedelta(hours=RESET_TOKEN_TTL_HOURS):
        return None
    if not tok.user.is_active:
        return None
    return tok


def _get_audit_log():
    """Lazily resolve AuditLog to avoid circular imports."""
    try:
        from admin.dig_portal.models import AuditLog
        return AuditLog
    except Exception:
        return None


def _client_ip(request):
    """Extract client IP from request, honouring X-Forwarded-For."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _notify_dig_for_reset(request, user, req):
    """Create in-app notifications for every active DIG.

    Each notification links to the DIG-side reset action that lets the
    DIG set a new password on behalf of the locked-out admin.
    """
    try:
        from admin.dig_portal.models import Notification
    except Exception:
        return

    dig_users = User.objects.filter(role=User.DIG, is_active=True)
    if not dig_users.exists():
        return

    try:
        reset_url = reverse('dig:admin_reset_password', args=[req.token])
    except Exception:
        reset_url = '/portal/dig/admin-resets/'

    abs_url = request.build_absolute_uri(reset_url) if request else reset_url

    for dig in dig_users:
        try:
            Notification.objects.create(
                recipient=dig,
                title="Admin Password Reset Request",
                message=(
                    f"{user.display_name} ({user.email or 'no-email'}) has requested "
                    f"a password reset. Review the request and set a new password."
                ),
                category='system',
                target_url=abs_url,
            )
        except Exception:
            continue


def _send_reset_email(request, user, token, kind='admin'):
    if kind == 'admin':
        reset_url = request.build_absolute_uri(
            reverse('auth_portal:admin_reset_confirm', args=[token.token])
        )
    else:
        reset_url = request.build_absolute_uri(
            reverse('auth_portal:citizen_reset_confirm', args=[token.token])
        )
    subject = "SafeCity FYP | Password Reset"
    body = (
        f"Hello {user.display_name},\n\n"
        f"We received a request to reset your SafeCity password.\n\n"
        f"Reset link (valid for {RESET_TOKEN_TTL_HOURS} hours):\n{reset_url}\n\n"
        f"If you did not request this reset, you can safely ignore this email.\n\n"
        f"- SafeCity FYP"
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [user.email], fail_silently=True)
    except Exception:
        pass


from django.views.decorators.http import require_POST


@require_POST
def logout_view(request):
    is_admin = False
    if request.user.is_authenticated:
        is_admin = request.user.role != User.USER
    logout(request)
    if is_admin:
        return redirect('auth_portal:admin_login')
    return redirect('challans:home')

