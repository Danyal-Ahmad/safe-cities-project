from django.db.models import Q


def system_settings(request):
    try:
        from .models import SystemSettings
        return {'system_settings': SystemSettings.get()}
    except Exception:
        return {'system_settings': None}


def active_alerts(request):
    alerts = []
    try:
        path = (request.path or '').lower()
        if any(x in path for x in (
            '/login', '/signup', '/sign-up', '/forgot', '/reset-password',
            '/password', '/auth/',
        )):
            return {'active_alerts': []}

        from .models import Alert
        from django.utils import timezone

        try:
            dismissed_ids = list(request.session.get('dismissed_alerts', []))
        except Exception:
            dismissed_ids = []
        dismissed_set = set(dismissed_ids) if dismissed_ids else set()

        if request.user.is_authenticated and getattr(request.user, 'is_regular_user', False):
            return {'active_alerts': []}

        if request.user.is_authenticated:
            qs = Alert.get_for_user(request.user)
        else:
            qs = Alert.objects.filter(
                is_active=True, audience='all',
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
            ).order_by('-created_at')

        if dismissed_set:
            qs = qs.exclude(id__in=dismissed_set)

        alerts = list(qs[:5])
    except Exception:
        pass
    return {'active_alerts': alerts}


def ads_delivery(request):
    ctx = {
        'static_post_ads': [],
        'popup_ads': [],
        'ticker_ads': [],
        'push_ads': [],
    }
    try:
        path = (request.path or '').lower()
        if any(x in path for x in (
            '/login', '/signup', '/sign-up', '/forgot', '/reset-password',
            '/password', '/auth/',
        )):
            return ctx

        from .models import Banner
        from django.utils import timezone
        from django.urls import reverse

        now = timezone.now()
        active_q = (
            Q(is_active=True)
            & (Q(start_at__isnull=True) | Q(start_at__lte=now))
            & (Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        )

        try:
            home_path = reverse('challans:home').rstrip('/')
            is_home = request.path.rstrip('/') in (home_path, '')
        except Exception:
            is_home = request.path.rstrip('/') in ('', '/challan')

        staff = request.user.is_authenticated and getattr(request.user, 'role', '') in (
            'DIG', 'SSP', 'SUPV', 'OFFICER', 'AUDIT', 'IT')

        if is_home:
            qs = Banner.objects.filter(active_q)
            if request.user.is_authenticated and not staff:
                qs = qs.filter(audience__in=['all', 'citizens'])
            elif not request.user.is_authenticated:
                qs = qs.filter(audience__in=['all', 'citizens'])
            ctx['static_post_ads'] = list(
                qs.filter(placement=Banner.PLACEMENT_STATIC_POST).order_by('-priority', '-created_at')[:8])
            ctx['popup_ads'] = list(
                qs.filter(placement=Banner.PLACEMENT_POPUP).order_by('-priority', '-created_at')[:3])
            ctx['ticker_ads'] = list(
                qs.filter(placement=Banner.PLACEMENT_TICKER).order_by('-priority', '-created_at')[:6])
        elif staff:
            ctx['ticker_ads'] = list(
                Banner.get_for_user(request.user, placement=Banner.PLACEMENT_TICKER)
                .order_by('-priority', '-created_at')[:6])
            ctx['push_ads'] = list(
                Banner.get_for_user(request.user, placement=Banner.PLACEMENT_PUSH)
                .order_by('-priority', '-created_at')[:10])
    except Exception:
        pass
    return ctx


def sidebar_badge_counts(request):
    ctx = {
        'high_value_challans_count': 0,
        'pending_appeals_count': 0,
        'pending_detections_count': 0,
    }
    if not request.user.is_authenticated:
        return ctx
    try:
        from accounts.models import User
        u = request.user
        if u.role in (User.DIG, User.SSP, User.AUDIT):
            from appeals.models import ChallanAppeal
            ctx['pending_appeals_count'] = ChallanAppeal.objects.filter(
                status=ChallanAppeal.PENDING).count()
        if u.role in (User.SSP, User.AUDIT):
            from challans.models import Challan
            ctx['high_value_challans_count'] = Challan.objects.filter(
                fine_amount__gte=5000, payment_status=Challan.UNPAID).count()
        if u.role in (User.OFFICER, User.SUPERVISOR):
            from detections.models import Detection
            ctx['pending_detections_count'] = Detection.objects.filter(
                status=Detection.PENDING).count()
    except Exception:
        pass
    return ctx


def user_notifications(request):
    ctx = {
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return ctx
    try:
        from .models import Notification
        qs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
        ctx['unread_notifications_count'] = qs.filter(is_read=False).count()
        ctx['recent_notifications'] = list(qs[:8])
    except Exception:
        pass
    return ctx


def integration_mode(request):
    try:
        from integrations.mode import get_integration_mode
        return {'INTEGRATION_MODE': get_integration_mode()}
    except Exception:
        return {'INTEGRATION_MODE': 'demo'}


def portal_namespace(request):
    VALID_PORTAL_NS = {
        'dig', 'ssp_portal', 'supervisor_portal', 'officer_portal',
        'audit_portal', 'it_support_portal', 'citizen_portal',
    }
    ns = None
    try:
        rm = getattr(request, 'resolver_match', None)
        if rm is not None and getattr(rm, 'namespace', None):
            candidate = rm.namespace
            if candidate in VALID_PORTAL_NS:
                ns = candidate
    except Exception:
        ns = None
    if not ns and getattr(request, 'user', None) and request.user.is_authenticated:
        role = getattr(request.user, 'role', None)
        role_map = {
            'DIG': 'dig',
            'SSP': 'ssp_portal',
            'SUPV': 'supervisor_portal',
            'OFFICER': 'officer_portal',
            'AUDIT': 'audit_portal',
            'IT': 'it_support_portal',
            'USER': 'citizen_portal',
        }
        ns = role_map.get(role)
    return {'portal_ns': ns}

