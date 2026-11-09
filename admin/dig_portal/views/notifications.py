from django.conf import settings as dj_settings

from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from django.http import JsonResponse
from accounts.decorators import _safe_redirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from accounts.decorators import staff_required


@staff_required
def notifications(request):
    from admin.dig_portal.models import Alert, Notification
    inbox_qs = (Notification.objects
             .filter(recipient=request.user)
             .order_by('-created_at'))
    inbox = inbox_qs[:100]
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    payment_pending = inbox_qs.filter(category='payment_verification', is_read=False)
    alerts = Alert.objects.filter(is_active=True).order_by('-created_at')[:30]
    return render(request, 'dashboard/dig/notifications.html', {
        'inbox': inbox,
        'unread_count': unread_count,
        'payment_pending': payment_pending,
        'alerts': alerts,
    })


@staff_required
def notification_read(request, notification_id):
    from admin.dig_portal.models import Notification
    n = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=['is_read'])
    if n.target_url:
        return redirect(n.target_url)
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'dig'
    try:
        return redirect(f'{ns}:notifications')
    except Exception:
        return _safe_redirect(request)


@staff_required
def notification_mark_read(request):
    if request.method == 'POST':
        from admin.dig_portal.models import Notification, Alert
        notif_id = request.POST.get('notification_id')
        alert_id = request.POST.get('alert_id')
        if notif_id:
            Notification.objects.filter(pk=notif_id, recipient=request.user).update(is_read=True)
        elif alert_id:
            dismissed = request.session.get('dismissed_alerts', [])
            dismissed.append(int(alert_id))
            request.session['dismissed_alerts'] = dismissed
        else:
            Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
            active_ids = list(Alert.objects.filter(is_active=True).values_list('id', flat=True))
            request.session['dismissed_alerts'] = active_ids
    unread_count = 0
    if request.user.is_authenticated:
        from admin.dig_portal.models import Notification
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'status': 'ok', 'unread_count': unread_count})


@staff_required
def notification_clear_all(request):
    if request.method == 'POST':
        from admin.dig_portal.models import Notification
        Notification.objects.filter(recipient=request.user).delete()
        request.session['dismissed_alerts'] = []
    return JsonResponse({'status': 'ok', 'unread_count': 0})
