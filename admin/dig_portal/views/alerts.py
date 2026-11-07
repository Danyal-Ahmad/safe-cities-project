from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings as dj_settings

from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from accounts.models import User
from accounts.decorators import dig_required
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from accounts.decorators import role_required


def _alerts_hub_url(tab='alerts', request=None):
    ns = 'dig'
    if request is not None:
        ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'dig'
    return reverse(f'{ns}:alerts_hub') + f'?tab={tab}'


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
def alerts_hub(request):
    alerts = Alert.objects.all().order_by('-created_at')[:50]
    broadcasts = AuditLog.objects.filter(action='broadcast.send').order_by('-timestamp')[:50]
    banners = Banner.objects.all().order_by('-created_at')[:100]
    active_tab = request.GET.get('tab', 'alerts')
    return render(request, 'dashboard/dig/alerts_hub.html', {
        'alerts': alerts,
        'broadcasts': broadcasts,
        'banners': banners,
        'active_tab': active_tab,
        'alerts_active_count': Alert.objects.filter(is_active=True).count(),
        'alerts_danger_count': Alert.objects.filter(severity='danger').count(),
    })


@role_required('DIG', 'IT')
def alerts_hub_add_alert(request):
    if request.method != 'POST':
        messages.info(request, "Use the form on the Alerts Hub to create an alert.")
        return redirect(_alerts_hub_url('alerts', request))
    title = request.POST.get('title', '').strip()
    message = request.POST.get('message', '').strip()
    severity = request.POST.get('severity', 'info')
    audience = request.POST.get('audience', 'all')
    expires_at = request.POST.get('expires_at') or None
    is_active = request.POST.get('is_active') == 'on'
    if not title or not message:
        messages.error(request, "Title and message are required.")
        return redirect(_alerts_hub_url('alerts', request))
    if expires_at:
        from django.utils.timezone import make_aware, get_current_timezone
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(expires_at)
            if timezone.is_naive(dt):
                dt = make_aware(dt, get_current_timezone())
            expires_at = dt
        except ValueError:
            expires_at = None
    if is_active:
        Alert.objects.filter(is_active=True).update(is_active=False)
    alert = Alert.objects.create(
        title=title, message=message, severity=severity,
        audience=audience, is_active=is_active,
        expires_at=expires_at,
        created_by=request.user,
    )
    AuditLog.write(request, 'alert.create', 'Alert', 0, title=title[:80])

    try:
        from realtime.realtime_events import emit_portal_notification
        emit_portal_notification(
            title=title, message=message, severity=severity,
            audiences=[audience] if audience else ['all'],
        )
    except Exception:
        pass
    messages.success(request, f"Alert '{title}' created. Previous active alerts have been deactivated (max 1 active ticker policy).")
    return redirect(_alerts_hub_url('alerts', request))


def alerts_hub_add_broadcast(request):
    if request.method != 'POST':
        messages.info(request, "Use the form on the Alerts Hub to send a broadcast.")
        return redirect(_alerts_hub_url('broadcasts', request))
    title = request.POST.get('title', '').strip()
    body = request.POST.get('body', '').strip()
    audience = request.POST.get('audience', 'staff')
    if not (title and body):
        messages.error(request, "Title and body are required.")
        return redirect(_alerts_hub_url('broadcasts', request))

    if audience == 'citizens':
        recipients = User.objects.filter(role=User.USER, is_active=True)
    elif audience == 'staff':
        recipients = User.objects.filter(role__in=User.STAFF_ROLES, is_active=True)
    elif audience == 'all':
        recipients = User.objects.filter(is_active=True)
    elif audience in dict(User.ROLE_CHOICES):
        recipients = User.objects.filter(role=audience, is_active=True)
    else:
        recipients = User.objects.filter(role__in=User.STAFF_ROLES, is_active=True)

    notifs = [
        Notification(recipient=u, title=title, message=body, category='system')
        for u in recipients
    ]
    Notification.objects.bulk_create(notifs, batch_size=500)

    AuditLog.write(request, 'broadcast.send', 'Notification', 0,
                   title=title[:80], body=body[:200], audience=audience,
                   recipient_count=len(notifs))
    messages.success(
        request,
        f"Broadcast sent to {len(notifs)} recipient(s) ({audience}): {title}"
    )
    return redirect(_alerts_hub_url('broadcasts', request))


@role_required('DIG', 'IT')
def alerts_hub_toggle_alert(request, alert_id):
    alert = get_object_or_404(Alert, pk=alert_id)
    alert.is_active = not alert.is_active
    alert.save()
    AuditLog.write(request, 'alert.toggle', 'Alert', alert.id, active=alert.is_active)
    messages.success(request, f"Alert '{alert.title}' {'activated' if alert.is_active else 'deactivated'}.")
    return redirect(_alerts_hub_url('alerts', request))


@role_required('DIG', 'IT')
def alerts_hub_delete_alert(request, alert_id):
    alert = get_object_or_404(Alert, pk=alert_id)
    if request.method == 'POST':
        AuditLog.write(request, 'alert.delete', 'Alert', alert.id, title=alert.title)
        alert.delete()
        messages.success(request, "Alert deleted.")
        return redirect(_alerts_hub_url('alerts', request))
    return render(request, 'dashboard/dig/alerts_hub_confirm_delete.html', {
        'kind': 'alert',
        'object': alert,
        'cancel_url': _alerts_hub_url('alerts', request),
        'confirm_url': reverse(
            f"{getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'dig'}:alerts_hub_delete_alert",
            args=[alert.id],
        ),
    })


@role_required('DIG', 'IT')
def alerts_hub_edit_alert(request, alert_id):
    alert = get_object_or_404(Alert, pk=alert_id)
    if request.method != 'POST':
        messages.info(request, "Use the edit form on the Alerts Hub to update an alert.")
        return redirect(_alerts_hub_url('alerts', request))
    title = request.POST.get('title', '').strip()
    message = request.POST.get('message', '').strip()
    severity = request.POST.get('severity', alert.severity)
    audience = request.POST.get('audience', alert.audience)
    is_active = request.POST.get('is_active') == 'on'
    if not title or not message:
        messages.error(request, "Title and message are required.")
        return redirect(_alerts_hub_url('alerts', request))
    if is_active and not alert.is_active:
        Alert.objects.filter(is_active=True).update(is_active=False)
    alert.title = title
    alert.message = message
    alert.severity = severity
    alert.audience = audience
    alert.is_active = is_active
    alert.save()
    AuditLog.write(request, 'alert.edit', 'Alert', alert.id, title=title[:80])
    messages.success(request, f"Alert '{title}' updated.")
    return redirect(_alerts_hub_url('alerts', request))


def alerts_hub_delete_broadcast(request, log_id):
    entry = get_object_or_404(AuditLog, pk=log_id, action='broadcast.send')
    if request.method == 'POST':
        entry.delete()
        messages.success(request, "Broadcast log entry deleted.")
        return redirect(_alerts_hub_url('broadcasts', request))
    return render(request, 'dashboard/dig/alerts_hub_confirm_delete.html', {
        'object_type': 'broadcast',
        'object_label': (entry.details or {}).get('title', f'Broadcast #{log_id}') if isinstance(entry.details, dict) else f'Broadcast #{log_id}',
        'cancel_url': _alerts_hub_url('broadcasts', request),
    })


def _banner_payload(request):
    data = {
        'title': (request.POST.get('title') or '').strip(),
        'html_content': (request.POST.get('html_content') or '').strip(),
        'placement': request.POST.get('placement') or Banner.PLACEMENT_TICKER,
        'audience': request.POST.get('audience') or Banner.AUDIENCE_ALL,
        'banner_type': request.POST.get('banner_type') or Banner.BANNER_TYPE_HTML,
        'image_link': (request.POST.get('image_link') or '').strip(),
        'show_on_home_only': request.POST.get('show_on_home_only') == 'on',
        'is_active': request.POST.get('is_active') == 'on',
    }
    if not data['title']:
        return None, "Title is required."
    if data['placement'] not in _BANNER_PLACEMENTS:
        data['placement'] = Banner.PLACEMENT_TICKER
    if data['audience'] not in _BANNER_AUDIENCES:
        data['audience'] = Banner.AUDIENCE_ALL
    if data['banner_type'] not in _BANNER_TYPES:
        data['banner_type'] = Banner.BANNER_TYPE_HTML
    if data['banner_type'] == Banner.BANNER_TYPE_IMAGE and not (data['html_content'] or request.FILES.get('image')):
        return None, "Image banners need an uploaded image or HTML fallback."
    if data['banner_type'] == Banner.BANNER_TYPE_HTML and not data['html_content']:
        return None, "HTML banners need content."
    return data, None


@role_required('DIG', 'IT')
def alerts_hub_add_banner(request):
    if request.method != 'POST':
        messages.info(request, "Use the Alerts Hub banners tab to create a banner.")
        return redirect(_alerts_hub_url('banners', request))
    data, error = _banner_payload(request)
    if error:
        messages.error(request, error)
        return redirect(_alerts_hub_url('banners', request))
    banner = Banner.objects.create(
        created_by=request.user,
        image=request.FILES.get('image') or None,
        **data,
    )
    AuditLog.write(request, 'banner.create', 'Banner', banner.id, title=banner.title[:80],
                   placement=banner.placement, audience=banner.audience)
    messages.success(request, f"Banner '{banner.title}' created and scheduled.")
    return redirect(_alerts_hub_url('banners', request))


@role_required('DIG', 'IT')
def alerts_hub_edit_banner(request, banner_id):
    banner = get_object_or_404(Banner, pk=banner_id)
    if request.method != 'POST':
        messages.info(request, "Use the edit button on a banner card to change it.")
        return redirect(_alerts_hub_url('banners', request))
    data, error = _banner_payload(request)
    if error:
        messages.error(request, error)
        return redirect(_alerts_hub_url('banners', request))
    for field, value in data.items():
        setattr(banner, field, value)
    if request.FILES.get('image'):
        banner.image = request.FILES['image']
    banner.save()
    AuditLog.write(request, 'banner.update', 'Banner', banner.id, title=banner.title[:80])
    messages.success(request, f"Banner '{banner.title}' updated.")
    return redirect(_alerts_hub_url('banners', request))


@role_required('DIG', 'IT')
def alerts_hub_toggle_banner(request, banner_id):
    banner = get_object_or_404(Banner, pk=banner_id)
    banner.is_active = not banner.is_active
    banner.save(update_fields=['is_active'])
    AuditLog.write(request, 'banner.toggle', 'Banner', banner.id, active=banner.is_active)
    messages.success(request, f"Banner '{banner.title}' {'activated' if banner.is_active else 'deactivated'}.")
    return redirect(_alerts_hub_url('banners', request))


@role_required('DIG', 'IT')
def alerts_hub_delete_banner(request, banner_id):
    banner = get_object_or_404(Banner, pk=banner_id)
    if request.method == 'POST':
        AuditLog.write(request, 'banner.delete', 'Banner', banner.id, title=banner.title[:80])
        title = banner.title
        banner.delete()
        messages.success(request, f"Banner '{title}' deleted.")
        return redirect(_alerts_hub_url('banners', request))
    return render(request, 'dashboard/dig/alerts_hub_confirm_delete.html', {
        'object_type': 'banner',
        'object_label': banner.title,
        'cancel_url': _alerts_hub_url('banners', request),
    })


@role_required('DIG')
def ads_select(request):
    if request.method == 'POST':
        action = request.POST.get('action', '')
        banner_id = request.POST.get('banner_id')
        banner = Banner.objects.filter(pk=banner_id).first()
        if banner is None:
            messages.error(request, "Ad not found.")
            return redirect('dig:ads_select')
        if action == 'toggle':
            banner.is_active = not banner.is_active
            banner.save(update_fields=['is_active'])
            AuditLog.write(request, 'ad.toggle', 'Banner', banner.pk,
                           title=banner.title[:80], active=banner.is_active)
            messages.success(request, f"'{banner.title}' is now {'active' if banner.is_active else 'inactive'}.")
        elif action == 'priority':
            try:
                banner.priority = max(-100, min(1000, int(request.POST.get('priority', 0))))
                banner.save(update_fields=['priority'])
                AuditLog.write(request, 'ad.priority', 'Banner', banner.pk,
                               title=banner.title[:80], priority=banner.priority)
                messages.success(request, f"Priority for '{banner.title}' updated to {banner.priority}.")
            except (TypeError, ValueError):
                messages.error(request, "Priority must be a number.")
        return redirect('dig:ads_select')

    banners = Banner.objects.all().order_by('-is_active', '-priority', '-created_at')
    channels = {
        'static_post': 'Static post ad (home)',
        'popup': 'Popup ad (home)',
        'ticker': 'Ticker ad (portals + home)',
        'push': 'Push notification (portals)',
    }
    return render(request, 'dashboard/dig/ads_select.html', {
        'banners': banners,
        'channels': channels,
        'active_count': banners.filter(is_active=True).count(),
    })


@dig_required
def broadcast_notification(request):
    messages.info(request, "Broadcasting was removed. Use the Alerts Hub for alerts and popup ads.")
    return redirect(_alerts_hub_url('alerts', request))


_BANNER_PLACEMENTS = {code for code, _ in Banner.PLACEMENT_CHOICES}


_BANNER_AUDIENCES = {code for code, _ in Banner.AUDIENCE_CHOICES}


_BANNER_TYPES = {code for code, _ in Banner.BANNER_TYPE_CHOICES}
