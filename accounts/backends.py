import re
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


def _normalize_cnic(raw):
    if not raw:
        return None
    digits = re.sub(r'\D', '', raw)
    if 12 <= len(digits) <= 13:
        return digits
    return None


def _cnic_dashed(digits):
    if not digits or len(digits) != 13:
        return None
    return f'{digits[:5]}-{digits[5:12]}-{digits[12]}'


def find_user_by_identifier(username):
    if not username:
        return None
    username = username.strip()

    q = Q(phone=username) | Q(email__iexact=username) | Q(username=username)
    cnic_digits = _normalize_cnic(username)
    if cnic_digits:
        q = q | Q(cnic=username)
        dashed = _cnic_dashed(cnic_digits)
        if dashed:
            q = q | Q(cnic=dashed) | Q(cnic=cnic_digits)

    user = User.objects.filter(q).first()
    if user:
        return user

    if cnic_digits:
        for u in User.objects.exclude(cnic__isnull=True).exclude(cnic=''):
            if _normalize_cnic(u.cnic) == cnic_digits:
                return u
    return None


class PhoneOrEmailBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        username = username.strip()

        q = Q(phone=username) | Q(email__iexact=username) | Q(username=username)

        cnic_digits = _normalize_cnic(username)
        if cnic_digits:
            q = q | Q(cnic=username)
            dashed = _cnic_dashed(cnic_digits)
            if dashed:
                q = q | Q(cnic=dashed) | Q(cnic=cnic_digits)

        try:
            user = User.objects.get(q)
        except User.DoesNotExist:
            if cnic_digits:
                for u in User.objects.exclude(cnic__isnull=True).exclude(cnic=''):
                    if _normalize_cnic(u.cnic) == cnic_digits:
                        user = u
                        break
                else:
                    return None
            else:
                return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(q).first()

        if user.is_locked:
            return None

        if user.check_password(password) and user.is_active:
            if request:
                ip = request.META.get('HTTP_X_FORWARDED_FOR')
                if ip:
                    ip = ip.split(',')[0].strip()
                else:
                    ip = request.META.get('REMOTE_ADDR')
                if ip:
                    user.last_login_ip = ip
                    user.save(update_fields=['last_login_ip'])
            user.reset_failed_login()
            return user
        else:
            from django.conf import settings
            user.register_failed_login(
                settings.ACCOUNT_LOCKOUT_THRESHOLD,
                settings.ACCOUNT_LOCKOUT_DURATION,
            )
            return None

