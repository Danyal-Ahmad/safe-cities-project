import csv
import datetime
import logging
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.conf import settings as dj_settings
from pathlib import Path

from accounts.decorators import dig_required, senior_staff_required, staff_required, it_required, dig_or_it_required, role_required, permission_required, any_permission_required, _safe_redirect
from accounts.models import User, OfficerProfile
from cameras.models import Camera
from detections.models import Detection, DetectionReviewNote
from challans.models import Challan
from appeals.models import ChallanAppeal
from realtime.models import LiveFeed
from .models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry


def _alerts_hub_url(tab='alerts', request=None):
    ns = 'dig'
    if request is not None:
        ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'dig'
    return reverse(f'{ns}:alerts_hub') + f'?tab={tab}'


@dig_required
def dashboard(request):
    from datetime import timedelta
    today = timezone.localdate()
    week_start = today - timedelta(days=7)
    total_today = Challan.objects.filter(issue_date=today).count()
    total_week = Challan.objects.filter(issue_date__gte=week_start).count()
    paid_today = Challan.objects.filter(issue_date=today, payment_status=Challan.PAID).count()
    revenue_collected = Challan.objects.filter(payment_status=Challan.PAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    revenue_today = Challan.objects.filter(issue_date=today, payment_status=Challan.PAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    revenue_pending = Challan.objects.filter(payment_status=Challan.UNPAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    active_cameras = Camera.objects.filter(is_active=True, is_streaming=True).count()
    online_cameras = Camera.objects.filter(health_status='online').count()
    pending_detections = Detection.objects.filter(status=Detection.PENDING).count()
    flagged_detections = Detection.objects.filter(status=Detection.FLAGGED).count()
    pending_appeals = ChallanAppeal.objects.filter(status=ChallanAppeal.PENDING).count()
    escalated_appeals = ChallanAppeal.objects.filter(status=ChallanAppeal.ESCALATED).count()
    total_users = User.objects.filter(role=User.USER).count()
    total_officers = User.objects.filter(role=User.OFFICER).count()

    by_type = Challan.objects.values('violation_type').annotate(c=Count('id')).order_by('-c')
    type_labels = [t['violation_type'] for t in by_type]
    type_counts = [t['c'] for t in by_type]
    max_type_count = max(type_counts) if type_counts else 1

    by_location = (Challan.objects.exclude(location__isnull=True).exclude(location='')
                   .values('location').annotate(c=Count('id')).order_by('-c')[:10])
    loc_labels = [l['location'] for l in by_location]
    loc_counts = [l['c'] for l in by_location]
    max_loc_count = max(loc_counts) if loc_counts else 1

    officers = User.objects.filter(role=User.OFFICER)
    officer_stats = []
    for off in officers:
        confirmed = Detection.objects.filter(reviewed_by=off, status=Detection.CONFIRMED).count()
        rejected = Detection.objects.filter(reviewed_by=off, status=Detection.REJECTED).count()
        pending = Detection.objects.filter(reviewed_by=off, status=Detection.PENDING).count()
        reviewed_qs = Detection.objects.filter(reviewed_by=off, status__in=[Detection.CONFIRMED, Detection.REJECTED])
        review_count = reviewed_qs.count()
        avg_review_hrs = 0
        valid = reviewed_qs.exclude(reviewed_at__isnull=True)
        if valid.exists():
            deltas = [(d.reviewed_at - d.created_at).total_seconds() / 3600
                      for d in valid if d.reviewed_at and d.created_at]
            if deltas:
                avg_review_hrs = round(sum(deltas) / len(deltas), 1)
        appeals = ChallanAppeal.objects.filter(reviewed_by=off).count()
        accuracy = round((confirmed / review_count * 100), 1) if review_count else 0.0
        officer_stats.append({
            'user': off, 'officer': off,
            'confirmed': confirmed, 'rejected': rejected, 'pending': pending,
            'reviewed': review_count, 'appeals': appeals,
            'avg_review_hrs': avg_review_hrs, 'accuracy': accuracy,
        })

    # 7-day activity trend
    trend_daily = []
    for d in range(6, -1, -1):
        day = timezone.now() - timedelta(days=d)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        trend_daily.append({
            'date': day_start.strftime('%b %d'),
            'detections': Detection.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count(),
            'challans': Challan.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count(),
        })

    # Active alerts for the dashboard widget
    from admin.dig_portal.models import Alert
    active_alerts = list(
        Alert.objects.filter(is_active=True).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).order_by('-created_at')[:5]
    )

    pending_appeals_recent = list(
        ChallanAppeal.objects.filter(status=ChallanAppeal.PENDING)
        .select_related('challan', 'submitted_by').order_by('-created_at')[:5]
    )
    recent_detections = list(
        Detection.objects.select_related('camera').order_by('-created_at')[:10]
    )

    return render(request, 'dashboard/dig/dashboard.html', {
        'total_today': total_today, 'total_week': total_week, 'paid_today': paid_today,
        'revenue_collected': revenue_collected, 'revenue_today': revenue_today, 'revenue_pending': revenue_pending,
        'active_cameras': active_cameras, 'online_cameras': online_cameras,
        'pending_detections': pending_detections, 'flagged_detections': flagged_detections,
        'pending_appeals': pending_appeals, 'escalated_appeals': escalated_appeals,
        'pending_appeals_recent': pending_appeals_recent,
        'recent_detections': recent_detections,
        'total_users': total_users, 'total_officers': total_officers,
        'type_labels': type_labels, 'type_counts': type_counts, 'max_type_count': max_type_count,
        'loc_labels': loc_labels, 'loc_counts': loc_counts, 'max_loc_count': max_loc_count,
        'officer_stats': officer_stats, 'officers': officers,
        'active_alerts': active_alerts, 'trend_daily': trend_daily,
    })


@staff_required
@permission_required('view_live_monitor')
def live_monitor(request):
    cameras = list(Camera.objects.all().order_by('-is_active', '-installed_date')[:200])

    from realtime.models import LiveFeed
    feed_by_cam = {}
    for f in LiveFeed.objects.filter(is_active=True).select_related('camera').order_by('-created_at'):
        if f.camera_id and f.camera_id not in feed_by_cam:
            feed_by_cam[f.camera_id] = f

    cam_ids = [c.id for c in cameras]
    latest_detections = {}
    if cam_ids:
        from detections.models import Detection
        for d in Detection.objects.filter(camera_id__in=cam_ids).order_by('-created_at'):
            if d.camera_id not in latest_detections:
                if d.status == Detection.CONFIRMED:
                    latest_detections[d.camera_id] = 'confirmed'
                elif d.status == Detection.PENDING:
                    latest_detections[d.camera_id] = 'doubt'
                elif d.status == Detection.REJECTED:
                    latest_detections[d.camera_id] = 'ignored'
                else:
                    latest_detections[d.camera_id] = ''

    for c in cameras:
        c.latest_detection_status = latest_detections.get(c.id, '')
        stream = (c.rtsp_url or '').strip() or (c.http_snapshot_url or '').strip()
        if not stream and c.id in feed_by_cam:
            f = feed_by_cam[c.id]
            try:
                if f.video_file:
                    stream = f.video_file.url
            except Exception:
                stream = ''
        c.playable_stream = stream
        if stream and c.health_status in ('unknown', '', None):
            c.health_status = 'online'

    live_feeds = list(LiveFeed.objects.filter(is_active=True).order_by('-created_at')[:50])
    all_cameras = cameras

    online_count = sum(1 for c in cameras if c.health_status == 'online' or getattr(c, 'playable_stream', None))
    offline_count = max(0, len(cameras) - online_count)

    recent_detections = []
    if cam_ids:
        from detections.models import Detection
        recent_detections = list(
            Detection.objects.filter(camera_id__in=cam_ids).order_by('-created_at')[:10]
        )

    return render(request, 'dashboard/dig/live_monitor.html', {
        'cameras': cameras,
        'live_feeds': live_feeds,
        'all_cameras': all_cameras,
        'online_count': online_count,
        'offline_count': offline_count,
        'total_cameras': len(cameras),
        'recent_detections': recent_detections,
    })


@staff_required
@permission_required('view_live_monitor')
def live_monitor_feed(request):
    """JSON feed for the Live Monitor page: recent activity + camera status counts.
    Polled client-side so the alert ticker and status badges refresh in place
    without a full page reload (which would otherwise restart video tiles).
    """
    from detections.models import Detection

    cameras = Camera.objects.all()
    online_count = cameras.filter(health_status='online').count()
    total_cameras = cameras.count()
    offline_count = max(0, total_cameras - online_count)

    recent = list(Detection.objects.select_related('camera').order_by('-created_at')[:10])
    items = []
    for d in recent:
        items.append({
            'id': d.id,
            'camera_id': d.camera.camera_id if d.camera else None,
            'plate': d.effective_plate or None,
            'violation_type': d.effective_violation_type or None,
            'status': d.status,
            'created_at': d.created_at.isoformat() if d.created_at else None,
            'created_at_display': d.created_at.strftime('%H:%M:%S') if d.created_at else '',
        })

    return JsonResponse({
        'online_count': online_count,
        'offline_count': offline_count,
        'total_cameras': total_cameras,
        'recent_detections': items,
        'server_time': timezone.now().isoformat(),
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
def analytics(request):
    qs = Challan.objects.all()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from: qs = qs.filter(issue_date__gte=date_from)
    if date_to: qs = qs.filter(issue_date__lte=date_to)
    vt_data = []
    vt_css_map = {
        Challan.WRONG_WAY: 'wrong-way', Challan.NO_HELMET: 'no-helmet',
        Challan.SIGNAL_BREAK: 'signal-break', Challan.OVER_SPEED: 'over-speed',
        Challan.OTHER: 'other',
    }
    vt_max = 0
    for code, label in Challan.VIOLATION_CHOICES:
        cnt = qs.filter(violation_type=code).count()
        if cnt > vt_max:
            vt_max = cnt
        vt_data.append({'code': code, 'label': label, 'count': cnt, 'css_class': vt_css_map.get(code, 'other')})
    for vt in vt_data:
        vt['pct'] = round(vt['count'] / vt_max * 100) if vt_max > 0 else 0

    return render(request, 'dashboard/dig/analytics.html', {
        'challans': qs[:100], 'total': qs.count(),
        'paid': qs.filter(payment_status=Challan.PAID).count(),
        'unpaid': qs.filter(payment_status=Challan.UNPAID).count(),
        'voided': qs.filter(payment_status=Challan.VOIDED).count(),
        'total_revenue': qs.filter(payment_status=Challan.PAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0,
        'pending_revenue': qs.filter(payment_status=Challan.UNPAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0,
        'date_from': date_from, 'date_to': date_to,
        'violation_types': vt_data,
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
def revenue_dashboard(request):
    today = timezone.localdate()
    periods = {
        'Today': Challan.objects.filter(issue_date=today),
        'This Week': Challan.objects.filter(issue_date__gte=today - datetime.timedelta(days=7)),
        'This Month': Challan.objects.filter(issue_date__gte=today - datetime.timedelta(days=30)),
        'This Year': Challan.objects.filter(issue_date__gte=today - datetime.timedelta(days=365)),
        'All Time': Challan.objects.all(),
    }
    summary = []
    for label, qs in periods.items():
        collected = qs.filter(payment_status=Challan.PAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0
        pending = qs.filter(payment_status=Challan.UNPAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0
        summary.append({'period': label, 'collected': collected, 'pending': pending,
                        'total': collected + pending, 'challans': qs.count()})
    daily = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        qs = Challan.objects.filter(issue_date=d)
        daily.append({
            'date': d,
            'collected': qs.filter(payment_status=Challan.PAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0,
            'pending': qs.filter(payment_status=Challan.UNPAID).aggregate(Sum('fine_amount'))['fine_amount__sum'] or 0,
            'count': qs.count(),
        })
    max_daily = max([d['collected'] + d['pending'] for d in daily] or [1])
    return render(request, 'dashboard/dig/revenue_dashboard.html', {
        'summary': summary, 'daily': daily, 'max_daily': max_daily,
    })


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
        # Persist flags on OfficerProfile for any staff (used by permission checks)
        from accounts.models import OfficerProfile
        prof, _ = OfficerProfile.objects.get_or_create(officer=target)
        for post_key, attr in flag_map.items():
            if hasattr(prof, attr):
                setattr(prof, attr, post_key in request.POST)
        prof.save()
        target.save()
        try:
            from .models import AuditLog
            AuditLog.write(request, 'admin.permissions_update', 'User', target.id)
        except Exception:
            pass
        messages.success(request, f"Permissions updated for {target.email or target.username}.")
        return redirect('dig:admin_list')

    from .admin_profiles import all_dropdowns, ROLE_PROFILES
    import json
    admins = list(User.objects.filter(role__in=[User.DIG, User.SSP, User.SUPERVISOR, User.OFFICER, User.AUDIT, User.IT_SUPPORT]).order_by('role', '-date_joined'))
    # Attach OfficerProfile flags for template data-p* (permissions modal)
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
        # Non-officer staff: sensible defaults for live monitor
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
    from accounts.permissions import ROLE_PERMISSION_MATRIX, PERMISSIONS, summarize_role
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

    """DIG edits an admin/staff user. Avatar upload supported.
    Role is editable via checkboxes — permissions are auto-derived from role
    via ROLE_PERMISSION_MATRIX. The DIG can reassign any admin role here.
    Name (first_name) is required."""
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


@role_required('DIG', 'SSP')
def officer_activity(request, officer_id):
    officer = get_object_or_404(User, pk=officer_id, role=User.OFFICER)
    recent_actions = Detection.objects.filter(reviewed_by=officer).order_by('-reviewed_at')[:20]
    appeals_handled = ChallanAppeal.objects.filter(reviewed_by=officer).order_by('-reviewed_at')[:20]
    notes_added = DetectionReviewNote.objects.filter(author=officer).order_by('-created_at')[:20]
    stats = {
        'total_reviewed': Detection.objects.filter(reviewed_by=officer).count(),
        'total_appeals': ChallanAppeal.objects.filter(reviewed_by=officer).count(),
        'total_notes': DetectionReviewNote.objects.filter(author=officer).count(),
    }
    return render(request, 'dashboard/dig/officer_activity.html', {
        'officer': officer, 'recent_actions': recent_actions,
        'appeals_handled': appeals_handled, 'notes_added': notes_added,
        'stats': stats,
    })


def _camera_list_redirect(request):
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'it_support_portal'
    return redirect(f'{ns}:camera_list')


@role_required('DIG', 'IT', 'SSP', 'SUPV', 'AUDIT')
def camera_list(request):
    cameras = list(Camera.objects.all().order_by('-installed_date'))
    online_count = sum(1 for c in cameras if c.is_active and (c.health_status in ('online', 'unknown') or c.rtsp_url))
    offline_count = sum(1 for c in cameras if not c.is_active or c.health_status == 'offline')
    with_media = sum(1 for c in cameras if c.rtsp_url)
    is_it = request.user.role == 'IT'
    return render(request, 'dashboard/dig/camera_list.html', {
        'cameras': cameras,
        'can_manage': is_it,
        'online_count': online_count,
        'offline_count': offline_count,
        'with_video': with_media,
    })


@dig_required
def citizen_users_list(request):
    from accounts.models import User
    q = (request.GET.get('q') or '').strip()
    users = User.objects.filter(role=User.USER).order_by('-date_joined')
    if q:
        from django.db.models import Q
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

@it_required
def camera_add(request):
    if request.method == 'POST':
        source_type = request.POST.get('source_type', 'rtsp')
        video_file = request.FILES.get('video_file')

        new_camera_id = (request.POST.get('camera_id') or '').strip()
        new_location = (request.POST.get('location') or '').strip()
        if not new_camera_id:
            messages.error(request, "Camera ID is required.")
            return redirect('it_support_portal:camera_add')
        if not new_location:
            messages.error(request, "Location is required.")
            return redirect('it_support_portal:camera_add')
        if Camera.objects.filter(camera_id=new_camera_id).exists():
            messages.error(request, f"A camera with ID '{new_camera_id}' already exists.")
            return redirect('it_support_portal:camera_add')

        rtsp_url = None
        http_snapshot_url = None
        notes = request.POST.get('notes') or None

        if source_type == 'video' and video_file:
            from django.core.files.storage import default_storage
            safe_name = video_file.name.replace(' ', '_')
            rel_path = f'camera_videos/{safe_name}'
            saved = default_storage.save(rel_path, video_file)
            media_url = dj_settings.MEDIA_URL.rstrip('/') + '/' + saved
            rtsp_url = media_url
            http_snapshot_url = None
            notes = ((notes or '') + f' [Demo video: {safe_name}]').strip()
        else:
            rtsp_url = request.POST.get('rtsp_url') or None
            http_snapshot_url = request.POST.get('http_snapshot_url') or None

        try:
            threshold = float(request.POST.get('auto_confirm_threshold', 0.85))
            threshold = max(0.50, min(0.99, threshold))
        except (TypeError, ValueError):
            threshold = 0.85

        from django.db import transaction
        try:
            with transaction.atomic():
                try:
                    lat = float(request.POST.get('latitude')) if request.POST.get('latitude') not in (None, '') else None
                except (TypeError, ValueError):
                    lat = None
                try:
                    lng = float(request.POST.get('longitude')) if request.POST.get('longitude') not in (None, '') else None
                except (TypeError, ValueError):
                    lng = None
                camera = Camera.objects.create(
                    camera_id=new_camera_id,
                    location=new_location,
                    latitude=lat,
                    longitude=lng,
                    legal_direction=request.POST.get('legal_direction', 'N'),
                    violation_side=request.POST.get('violation_side', 'back'),
                    auto_confirm_threshold=threshold,
                    rtsp_url=rtsp_url,
                    http_snapshot_url=http_snapshot_url,
                    is_active=True,
                    is_streaming=True,
                    capture_interval=int(request.POST.get('capture_interval', 5)),
                    notes=notes,
                    health_status='online',
                )
                if source_type == 'video' and video_file:
                    camera.last_frame_at = timezone.now()
                    camera.last_health_check = timezone.now()
                    camera.save(update_fields=['last_frame_at', 'last_health_check'])
                    lf = LiveFeed.objects.create(
                        title=f"Camera {camera.camera_id} — {camera.location}",
                        video_file=video_file,
                        camera=camera,
                        location_label=camera.location,
                        uploaded_by=request.user,
                        is_active=True,
                    )
                    try:
                        if lf.video_file:
                            camera.rtsp_url = lf.video_file.url
                            camera.health_status = 'online'
                            camera.is_active = True
                            camera.is_streaming = True
                            camera.save(update_fields=['rtsp_url', 'health_status', 'is_active', 'is_streaming'])
                    except Exception:
                        pass
                    try:
                        from video_processor.models import VideoUpload
                        from cameras.video_processing import start_processing_async
                        upload = VideoUpload.objects.create(
                            camera=camera,
                            video_file=video_file,
                            original_filename=getattr(video_file, 'name', 'upload.mp4'),
                            uploaded_by=request.user,
                            camera_location=camera.location or '',
                        )
                        start_processing_async(upload.id)
                        msg_extra = " AI processing started on uploaded video."
                    except Exception as _vu_err:
                        import logging
                        logging.getLogger(__name__).warning("VideoUpload pipeline failed: %s", _vu_err)
                        msg_extra = ""
                if not camera.rtsp_url and not camera.http_snapshot_url:
                    camera.enrollment_token = uuid.uuid4()
                    camera.is_enrolled = False
                    camera.save()
                    AuditLog.write(request, 'camera.add', 'Camera', camera.id, camera_id=camera.camera_id,
                                   enrollment='pending')
                    msg = f"Camera {camera.camera_id} added. Enrollment token: {camera.enrollment_token}"
                else:
                    camera.is_enrolled = True
                    camera.save()
                    AuditLog.write(request, 'camera.add', 'Camera', camera.id, camera_id=camera.camera_id,
                                   rtsp=camera.rtsp_url or camera.http_snapshot_url)
                    msg = f"Camera {camera.camera_id} added. API key: {camera.api_key}" + (msg_extra if "msg_extra" in dir() else "")
        except Exception as e:
            messages.error(request, f"Failed to create camera: {e}")
            return redirect('it_support_portal:camera_add')
        messages.success(request, msg)
        return _camera_list_redirect(request)
    return render(request, 'dashboard/dig/camera_add.html', {})


@it_required
def camera_edit(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    if request.method == 'POST':
        before_rtsp = camera.rtsp_url
        camera.location = request.POST.get('location', camera.location)
        try:
            camera.latitude = float(request.POST.get('latitude')) if request.POST.get('latitude') not in (None, '') else None
        except (TypeError, ValueError):
            pass
        try:
            camera.longitude = float(request.POST.get('longitude')) if request.POST.get('longitude') not in (None, '') else None
        except (TypeError, ValueError):
            pass
        camera.legal_direction = request.POST.get('legal_direction', camera.legal_direction)
        camera.violation_side = request.POST.get('violation_side', camera.violation_side)
        try:
            threshold = float(request.POST.get('auto_confirm_threshold', camera.auto_confirm_threshold))
            camera.auto_confirm_threshold = max(0.50, min(0.99, threshold))
        except (TypeError, ValueError):
            pass
        camera.rtsp_url = request.POST.get('rtsp_url') or None
        camera.http_snapshot_url = request.POST.get('http_snapshot_url') or None
        camera.capture_interval = int(request.POST.get('capture_interval', 5) or 5)
        camera.is_streaming = request.POST.get('is_streaming') == 'on'
        camera.notes = request.POST.get('notes') or None
        video_file = request.FILES.get('video_file')
        if video_file:
            from django.core.files.storage import default_storage
            from realtime.models import LiveFeed
            rel_path = f"cameras/videos/{camera.camera_id}_{video_file.name.replace(' ', '_')}"
            saved = default_storage.save(rel_path, video_file)
            from django.conf import settings as dj_settings
            camera.rtsp_url = dj_settings.MEDIA_URL.rstrip('/') + '/' + saved
            camera.is_active = True
            camera.is_streaming = True
            camera.health_status = 'online'
            camera.last_frame_at = timezone.now()
            LiveFeed.objects.update_or_create(
                camera=camera,
                defaults={
                    'title': f"Camera {camera.camera_id} — {camera.location}",
                    'video_file': video_file,
                    'location_label': camera.location,
                    'uploaded_by': request.user,
                    'is_active': True,
                },
            )
            # Run the AI detection pipeline over the uploaded video so the
            # frames land in the review queue and on Live Tracking (the
            # camera_add flow already did this; camera_edit was missing it).
            try:
                from video_processor.models import VideoUpload
                from cameras.video_processing import start_processing_async
                upload = VideoUpload.objects.create(
                    camera=camera,
                    video_file=video_file,
                    original_filename=getattr(video_file, 'name', 'upload.mp4'),
                    uploaded_by=request.user,
                    camera_location=camera.location or '',
                )
                start_processing_async(upload.id)
                messages.info(request, "AI processing started on the uploaded video — detections will appear in the review queue and on Live Tracking.")
            except Exception as _vu_err:
                logging.getLogger(__name__).warning("VideoUpload pipeline failed on camera_edit: %s", _vu_err)
        camera.save()
        AuditLog.write(request, 'camera.edit', 'Camera', camera.id, camera_id=camera.camera_id,
                       before_rtsp=before_rtsp, after_rtsp=camera.rtsp_url,
                       violation_side=camera.violation_side,
                       auto_confirm_threshold=camera.auto_confirm_threshold)
        messages.success(request, f"Camera {camera.camera_id} updated.")
        return _camera_list_redirect(request)
    return render(request, 'dashboard/dig/camera_edit.html', {'camera': camera})


@dig_or_it_required
def camera_toggle(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    camera.toggle()
    AuditLog.write(request, 'camera.toggle', 'Camera', camera.id, active=camera.is_active)
    messages.success(request, f"Camera {camera.camera_id} {'activated' if camera.is_active else 'deactivated'}.")
    return _camera_list_redirect(request)


@dig_or_it_required
def camera_set_online(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    camera.health_status = 'online'
    camera.last_frame_at = timezone.now()
    camera.last_health_check = timezone.now()
    camera.is_active = True
    camera.is_streaming = True
    camera.save()
    AuditLog.write(request, 'camera.set_online', 'Camera', camera.id, camera_id=camera.camera_id)
    messages.success(request, f"Camera {camera.camera_id} set to ONLINE / LIVE. Protected from auto-degradation for 24 hours.")
    return _camera_list_redirect(request)


def _camera_delete_impact(camera):
    """Non-destructive summary of what still references this camera, so IT can
    make an informed choice between deactivating (safe, reversible) and force
    deleting (detaches history, still preserved via SET_NULL but no longer
    attributable to this camera record once it's gone)."""
    from realtime.models import CameraAssignment
    return {
        'detections': camera.detections.count(),
        'assignments': CameraAssignment.objects.filter(camera=camera, is_active=True).count(),
        'challans': camera.challan_set.count() if hasattr(camera, 'challan_set') else 0,
    }


def _do_camera_delete(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    impact = _camera_delete_impact(camera)
    has_history = any(impact.values())
    if request.method == 'POST':
        force = request.POST.get('force') == 'on' or not has_history
        if has_history and not force:
            messages.error(
                request,
                f"Camera {camera.camera_id} has {impact['detections']} detection(s), "
                f"{impact['challans']} challan(s) and {impact['assignments']} active officer "
                f"assignment(s) linked to it. Deactivate it instead, or tick 'force delete' to "
                f"remove the camera record anyway (history is preserved but detached from it)."
            )
            return render(request, 'dashboard/dig/camera_confirm_delete.html',
                          {'camera': camera, 'impact': impact})
        AuditLog.write(request, 'camera.delete', 'Camera', camera.id,
                        camera_id=camera.camera_id, **impact)
        cid = camera.camera_id
        camera.delete()
        messages.success(request, f"Camera {cid} deleted.")
        return _camera_list_redirect(request)
    return render(request, 'dashboard/dig/camera_confirm_delete.html',
                  {'camera': camera, 'impact': impact})


@it_required
def camera_delete(request, camera_id):
    return _do_camera_delete(request, camera_id)


@it_required
def regenerate_enrollment_token(request, camera_id):
    camera = get_object_or_404(Camera, pk=camera_id)
    if request.method == 'POST':
        camera.enrollment_token = uuid.uuid4()
        camera.is_enrolled = False
        camera.save()
        AuditLog.write(request, 'camera.regenerate_token', 'Camera', camera.id, camera_id=camera.camera_id)
        messages.success(request, f"New enrollment token for {camera.camera_id}: {camera.enrollment_token}")
    return _camera_list_redirect(request)


@staff_required
def cameras_status(request):
    cameras = Camera.objects.all().order_by('-installed_date')
    threshold = timezone.now() - datetime.timedelta(minutes=3)
    manual_online_threshold = timezone.now() - datetime.timedelta(hours=24)
    for c in cameras:
        is_demo = (c.rtsp_url and c.rtsp_url.startswith('file://'))
        if is_demo:
            if c.health_status != 'online' and c.is_active:
                c.health_status = 'online'
                c.save(update_fields=['health_status'])
            continue
        if not c.is_active:
            continue
        if c.last_health_check and c.last_health_check > manual_online_threshold and c.health_status == 'online':
            continue
        if not c.rtsp_url and not c.http_snapshot_url:
            continue
        if c.last_frame_at and c.last_frame_at > threshold:
            if c.health_status != 'online':
                c.health_status = 'online'
                c.save(update_fields=['health_status'])
        else:
            if c.last_frame_at and c.health_status == 'online':
                if not (c.last_health_check and c.last_health_check > manual_online_threshold):
                    c.health_status = 'degraded'
                    c.save(update_fields=['health_status'])
    return render(request, 'dashboard/dig/cameras_status.html', {'cameras': cameras, 'now': timezone.now()})


@it_required
def settings_edit(request):
    if getattr(request.user, 'role', '') == 'DIG':
        from django.contrib import messages as _m
        _m.info(request, 'Administrative form selection is managed under Staff workflows. System configuration is handled by IT Support.')
        return redirect('dig:dashboard')

    """IT-only system configuration. DIG is redirected to dashboard."""
    from .models import ChallanTemplate
    is_it = (
        getattr(request.user, 'role', '') in ('IT', 'IT_SUPPORT')
        or getattr(request.user, 'is_it_support', False)
        or getattr(request.user, 'is_it', False)
    )
    is_dig = getattr(request.user, 'role', '') == 'DIG' or getattr(request.user, 'is_dig', False)
    if is_dig and not is_it:
        messages.info(request, "Administrative template selection was moved. System settings are managed by IT Support.")
        return redirect('dig:dashboard')

    if request.method == 'POST':
        action = request.POST.get('action') or ''

        if action in ('upload_challan_template', 'save_challan_template',
                      'delete_challan_template', 'activate_preset', 'set_challan_template'):
            return redirect('it_support_portal:challan_templates')

        if not is_it:
            messages.error(request, "System configuration is managed by IT Support.")
            return redirect('it_support_portal:settings_edit')

        settings = SystemSettings.get()
        try:
            settings.due_date_days = int(request.POST.get('due_date_days', 30))

            tc = dict(settings.template_config or {})
            for k in ('smtp_host','smtp_port','smtp_user','smtp_password','smtp_from','smtp_tls',
                      'sms_provider','sms_api_url','sms_api_key','sms_api_secret','sms_sender',
                      'header_text','account_number','footer_text'):
                if k in request.POST:
                    tc[k] = request.POST.get(k, '').strip()
            tc['auto_blacklist_enabled'] = request.POST.get('auto_blacklist_enabled') in ('on', '1', 'true', 'True')
            try:
                tc['auto_blacklist_threshold'] = max(1, int(request.POST.get('auto_blacklist_threshold') or 5))
            except ValueError:
                tc['auto_blacklist_threshold'] = 5
            settings.template_config = tc
            settings.email_enabled = request.POST.get('email_enabled') in ('on', '1', 'true', 'True')
            if 'integration_mode' in request.POST and hasattr(settings, 'integration_mode'):
                settings.integration_mode = request.POST.get('integration_mode') or settings.integration_mode
            if 'nadra_api_url' in request.POST and hasattr(settings, 'nadra_api_url'):
                settings.nadra_api_url = request.POST.get('nadra_api_url', '').strip()
            if 'nadra_api_key' in request.POST and hasattr(settings, 'nadra_api_key'):
                settings.nadra_api_key = request.POST.get('nadra_api_key', '').strip()

        except ValueError:
            pass
        try:
            settings.ai_confidence_threshold = float(request.POST.get('ai_confidence_threshold', 0.90))
        except ValueError:
            pass
        ai = settings.ai_config or {}
        pd = dict(ai.get('plate_detector') or {})
        sc = dict(ai.get('side_classifier') or {})
        try:
            if request.POST.get('plate_confidence_threshold') is not None:
                pd['confidence_threshold'] = float(request.POST.get('plate_confidence_threshold'))
            if request.POST.get('max_box_area_ratio') is not None:
                pd['max_box_area_ratio'] = float(request.POST.get('max_box_area_ratio'))
            if request.POST.get('box_tighten') is not None:
                pd['box_tighten'] = float(request.POST.get('box_tighten'))
            if request.POST.get('side_back_threshold') is not None:
                sc['back_threshold'] = float(request.POST.get('side_back_threshold'))
            if request.POST.get('min_side_confidence') is not None:
                sc['min_side_confidence'] = float(request.POST.get('min_side_confidence'))
        except ValueError:
            pass
        pd.setdefault('input_shape', [1, 3, 560, 560])
        pd.setdefault('num_classes', 91)
        pd.setdefault('car_class_id', 3)
        pd.setdefault('vehicle_class_ids', [3, 4, 6, 8])
        pd.setdefault('file', 'NumberPlate_detection_model_int8.onnx')
        sc.setdefault('input_shape', [1, 224, 224, 3])
        sc.setdefault('file', 'car_side_Classifier_model_int8.onnx')
        ai['plate_detector'] = pd
        ai['side_classifier'] = sc
        ai['car_only'] = request.POST.get('car_only') in ('on', 'true', '1', None) or True
        ai['reject_person'] = request.POST.get('reject_person') in ('on', 'true', '1', None) or True
        if request.POST.get('car_only') == 'off':
            ai['car_only'] = False
        settings.ai_config = ai
        settings.email_enabled = request.POST.get('email_enabled') in ('on', 'true', '1')
        fines = dict(settings.default_fines or {})
        try:
            if request.POST.get('fine_wrong_way') is not None:
                fines['wrong_way'] = float(request.POST.get('fine_wrong_way'))
        except ValueError:
            pass
        settings.default_fines = fines
        tcfg = dict(settings.template_config or {})
        for key in ('grace_hours', 'max_trail_frames', 'live_refresh_sec'):
            if request.POST.get(key) is not None:
                try:
                    tcfg[key] = int(request.POST.get(key))
                except ValueError:
                    pass
        tcfg['auto_confirm_high_conf'] = request.POST.get('auto_confirm_high_conf') in ('on', 'true', '1')
        settings.template_config = tcfg

        et = settings.email_template or {}
        if request.POST.get('email_from_name') is not None:
            et['from_name'] = request.POST.get('email_from_name') or et.get('from_name', '')
        if request.POST.get('email_subject_prefix') is not None:
            et['subject_prefix'] = request.POST.get('email_subject_prefix') or et.get('subject_prefix', '')
        settings.email_template = et
        settings.excise_api_url = request.POST.get('excise_api_url') or None
        settings.excise_api_key = request.POST.get('excise_api_key') or None
        settings.nadra_api_url = request.POST.get('nadra_api_url') or None
        settings.nadra_api_key = request.POST.get('nadra_api_key') or None
        mode = (request.POST.get('integration_mode') or 'demo').strip().lower()
        settings.integration_mode = mode if mode in ('demo', 'real') else 'demo'
        settings.updated_by = request.user
        settings.save()
        AuditLog.write(request, 'settings.edit', 'SystemSettings', settings.id,
                       email_enabled=settings.email_enabled)
        messages.success(request, "System configuration saved.")
        return redirect('it_support_portal:settings_edit')


    if request.GET.get('tab') == 'challan_templates':
        return redirect('it_support_portal:challan_templates')
    if request.GET.get('tab') == 'pdf':
        return redirect('it_support_portal:pdf_settings')

    settings = SystemSettings.get()
    templates = list(ChallanTemplate.objects.all().order_by('-created_at')[:50])
    from detections.ai import get_model_info
    model_info = get_model_info()
    ai_cfg = (settings.ai_config if settings else {}) or {}
    return render(request, 'dashboard/dig/settings_edit.html', {
        'settings': settings,
        'default_fines': SystemSettings.DEFAULT_FINES,
        'challan_templates': templates,
        'model_info': model_info,
        'ai_cfg': ai_cfg,
        'is_it': is_it,
        'is_dig': is_dig,
    })


@it_required
def challan_templates_manage(request):
    from .models import ChallanTemplate
    sys_settings = SystemSettings.get()

    if request.method == 'POST':
        action = request.POST.get('action') or ''
        if action == 'upload_pdf_template':
            name = (request.POST.get('template_name') or '').strip() or 'PDF Template'
            pdf_file = request.FILES.get('pdf_file')
            if not pdf_file:
                messages.error(request, "Please choose a PDF file to upload.")
                return redirect('it_support_portal:challan_templates')
            ct = ChallanTemplate(
                name=name,
                uploaded_by=request.user,
                is_active=False,
                html_content='',
            )
            ct.file.save(pdf_file.name, pdf_file, save=True)
            ct.save()
            AuditLog.write(
                request, 'challan_template.upload_pdf', 'ChallanTemplate', ct.id,
                name=ct.name, file=ct.file.name if ct.file else '',
            )
            messages.success(request, f"PDF template '{ct.name}' uploaded.")
            return redirect('it_support_portal:challan_templates')

        if action in ('upload_challan_template', 'save_challan_template'):
            name = (request.POST.get('template_name') or '').strip() or 'Template'
            html = (request.POST.get('html_content') or '').strip()
            tid = request.POST.get('template_id') or ''
            if not html:
                messages.error(request, "Template HTML content is required.")
                return redirect('it_support_portal:challan_templates')
            if tid:
                obj = ChallanTemplate.objects.filter(pk=tid).first()
                if not obj:
                    messages.error(request, "Template not found.")
                    return redirect('it_support_portal:challan_templates')
                obj.name = name
                obj.html_content = html
                obj.save()
                messages.success(request, f"Template '{obj.name}' updated.")
            else:
                obj = ChallanTemplate.objects.create(name=name, html_content=html, uploaded_by=request.user, file=None)
                messages.success(request, f"Template '{obj.name}' created.")
            return redirect('it_support_portal:challan_templates')
        if action == 'delete_challan_template':
            tid = request.POST.get('template_id')
            obj = ChallanTemplate.objects.filter(pk=tid).first()
            if obj:
                nm = obj.name
                obj.delete()
                messages.success(request, f"Template '{nm}' deleted.")
            return redirect('it_support_portal:challan_templates')
        if action == 'set_challan_template':
            tid = request.POST.get('active_template')
            if tid and tid != 'default':
                obj = ChallanTemplate.objects.filter(pk=tid).first()
                if obj:
                    obj.is_active = True
                    obj.save()
                    sys_settings.pdf_template = f'db:{obj.id}'
                    sys_settings.save(update_fields=['pdf_template'])
                    messages.success(request, f"Active template set to '{obj.name}'.")
            else:
                ChallanTemplate.objects.update(is_active=False)
                sys_settings.pdf_template = 'modern_a4'
                sys_settings.save(update_fields=['pdf_template'])
                messages.success(request, "Default official template activated.")
            return redirect('it_support_portal:challan_templates')
        if action == 'activate_file_template':
            key = (request.POST.get('template_key') or '').strip()
            from pathlib import Path
            from django.conf import settings as dj_settings
            fs_path = Path(dj_settings.BASE_DIR) / 'templates' / 'challan' / 'challan_templates' / f'{key}.html'
            if not key or not fs_path.is_file():
                messages.error(request, "Template layout not found.")
                return redirect('it_support_portal:challan_templates')
            ChallanTemplate.objects.update(is_active=False)
            sys_settings.pdf_template = key
            sys_settings.save(update_fields=['pdf_template'])
            messages.success(request, f"Active layout set to '{key.replace('_', ' ').title()}'.")
            return redirect('it_support_portal:challan_templates')
        if action == 'save_file_template':
            key = (request.POST.get('template_key') or '').strip()
            html = request.POST.get('html_content') or ''
            from pathlib import Path
            from django.conf import settings as dj_settings
            fs_dir = Path(dj_settings.BASE_DIR) / 'templates' / 'challan' / 'challan_templates'
            fs_path = fs_dir / f'{key}.html'
            if not key or '/' in key or '\\' in key or '..' in key or not fs_path.resolve().is_relative_to(fs_dir.resolve()):
                messages.error(request, "Invalid template key.")
                return redirect('it_support_portal:challan_templates')
            if not html.strip():
                messages.error(request, "Template HTML content is required.")
                return redirect('it_support_portal:challan_templates')
            try:
                fs_path.write_text(html, encoding='utf-8')
                AuditLog.write(request, 'challan_template.edit', 'ChallanTemplateFile', 0, key=key)
                messages.success(request, f"Layout '{key.replace('_', ' ').title()}' saved.")
            except OSError as e:
                messages.error(request, f"Could not save layout: {e}")
            return redirect('it_support_portal:challan_templates')


    DEFAULT_TEMPLATES = [
        ("Safe City E-Challan (A4)", "{% load static %}\n<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"UTF-8\">\n<style>\n    @page { size: A4 portrait; margin: 8mm; }\n    * { box-sizing: border-box; }\n    body { font-family: 'Helvetica', 'Arial', sans-serif; font-size: 7.5px; color: #333; margin: 0; padding: 0; line-height: 1.25; background: #fff; }\n    .header { display: flex; justify-content: space-between; align-items: center; padding: 5px 6px 4px 6px; background: #fff; border: 1.5px solid #000; border-bottom: 2px solid #000; }\n    .header-title { flex: 1; text-align: left; padding: 0 8px; }\n    .header-title h1 { font-size: 18px; margin: 0; font-weight: 900; color: #000; letter-spacing: 1.5px; text-transform: uppercase; }\n    .header-title h2 { font-size: 8px; font-weight: 700; color: #000; letter-spacing: 0.5px; text-transform: uppercase; margin-top: 1px; }\n    .header-logos { display: flex; gap: 4px; align-items: center; }\n    .logo-box img { height: 42px; width: auto; display: block; object-fit: contain; }\n    .top-bar { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; border: 1.5px solid #000; border-top: none; }\n    .tb-cell { padding: 3px 5px; border-right: 1px solid #000; }\n    .tb-cell:last-child { border-right: none; }\n    .tb-label { font-size: 5.5px; color: #444; font-weight: 700; display: block; margin-bottom: 1px; text-transform: uppercase; letter-spacing: 0.4px; }\n    .barcode-ticket svg, .barcode-ticket img { height: 36px; width: auto; max-width: 100%; display:block; margin:0 auto; }\n    .barcode-ticket { text-align:center; }\n    .barcode-ticket svg { height:38px; width:auto; max-width:100%; display:block; margin:0 auto; }\n    .ticket-no-text { font-size:8px; font-weight:700; letter-spacing:1px; margin-top:2px; }\n    .tb-val { font-size: 9px; font-weight: 800; color: #000; display: block; letter-spacing: 0.2px; }\n    .barcode-area { display: flex; align-items: stretch; border: 1.5px solid #000; border-top: none; }\n    .barcode-area > div:first-child { padding: 4px 8px; display: flex; flex-direction: column; align-items: center; justify-content: center; border-right: 1px solid #000; background: #fff; }\n    .pay-box { background: #f9f9f9; padding: 4px 8px; flex: 1; border-left: none; }\n    .pay-amt { font-size: 13px; font-weight: 900; color: #000; display: block; letter-spacing: 0.8px; margin-top: 1px; }\n    .section-header { background: #e0e0e0; color: #000; padding: 2px 5px; font-weight: 900; font-size: 6.5px; border: 1.5px solid #000; border-top: none; text-align: center; letter-spacing: 1.5px; text-transform: uppercase; }\n    .data-grid { display: grid; grid-template-columns: repeat(5, 1fr); border: 1.5px solid #000; border-top: none; }\n    .dg-cell { padding: 2px 4px; border-right: 1px solid #ccc; font-size: 7px; background: #fff; }\n    .dg-cell:last-child { border-right: none; }\n    .dg-label { color: #555; font-size: 5.5px; display: block; margin-bottom: 1px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px; }\n    .dg-val { font-weight: 700; color: #000; display: block; font-size: 7px; }\n    .dg-val.alert { font-weight: 900; color: #cc0000; }\n    .row-2 { display: grid; grid-template-columns: 3fr 1fr 1fr; border: 1.5px solid #000; border-top: none; }\n    .img-container { padding: 4px; background: #efefef; border: 1.5px solid #000; border-top: none; }\n    .img-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }\n    .img-box { border: 1px solid #666; background: #fff; position: relative; }\n    .img-box img { width: 100%; height: auto; display: block; }\n    .img-label { position: absolute; top: 2px; left: 2px; background: rgba(0,0,0,0.7); color: #fff; font-size: 5px; padding: 1px 3px; font-weight: 700; }\n    .notice { font-size: 6.5px; color: #000; padding: 5px 6px; border: 1.5px solid #000; border-top: none; background: #fff; text-align: justify; line-height: 1.4; }\n    .cutter { display: flex; align-items: center; gap: 4px; padding: 0; margin: 0 -5px 6px -5px; background: #fff; line-height: 1; height: 10px; }\n    .cutter span { font-size: 20px; font-weight: bold; display: block; margin-top: 4px; }\n    .cutter::after { content: ''; flex: 1; border-top: 1.5px dashed #555; margin-top: 10px; }\n    .po-stamp { float: right; width: 80px; height: 35px; border: 1.5px dashed #888; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 5.5px; color: #666; text-align: center; letter-spacing: 0.3px; text-transform: uppercase; margin-left: 15px; margin-bottom: 3px; line-height: 0.8; }\n    .post-office { margin-top: 6px; border: 1.5px solid #000; padding: 0 5px 5px 5px; }\n    .po-body { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 12px; font-size: 7px; }\n    .po-row { margin-bottom: 2px; display: flex; gap: 3px; align-items: baseline; border-bottom: 1px dotted #bbb; padding-bottom: 1px; }\n    .po-label { font-weight: 700; color: #000; white-space: nowrap; font-size: 6px; text-transform: uppercase; letter-spacing: 0.2px; }\n    .po-cashier-row { display: flex; justify-content: space-between; margin-top: 6px; font-size: 6px; border-top: 1px solid #000; padding-top: 4px; }\n</style>\n</head>\n<body>\n\n<div class=\"header\">\n    <div class=\"header-title\">\n        <h1>SAFE CITY</h1>\n        <h2>Traffic Police Electronic-Challan</h2>\n    </div>\n    <div class=\"header-logos\">\n        <div class=\"logo-box\">\n            <img src=\"file://{{ logo_left_path }}\" alt=\"Logo Left\">\n        </div>\n        <div class=\"logo-box\">\n            <img src=\"file://{{ logo_right_path }}\" alt=\"Logo Right\">\n        </div>\n    </div>\n</div>\n\n<div class=\"top-bar\">\n    <div class=\"tb-cell\">\n        <div class=\"tb-label\">Ticket No.</div>\n        <div class=\"tb-val barcode-ticket\">\n          {% if barcode_svg %}\n            {{ barcode_svg|safe }}\n          {% else %}\n            <svg id=\"ticket-barcode-fallback\" xmlns=\"http://www.w3.org/2000/svg\" width=\"180\" height=\"40\"></svg>\n          {% endif %}\n          <div class=\"ticket-no-text\">{{ challan.ticket_no }}</div>\n        </div>\n        </div>\n    </div>\n    <div class=\"tb-cell\">\n        <div class=\"tb-label\">Registration No.</div>\n        <div class=\"tb-val\">{{ challan.plate_number }}</div>\n    </div>\n    <div class=\"tb-cell\">\n        <div class=\"tb-label\">Issue Date</div>\n        <div class=\"tb-val\">{{ challan.issue_date|date:\"d-M-Y\" }}</div>\n    </div>\n    <div class=\"tb-cell\">\n        <div class=\"tb-label\">Payment Status</div>\n        <div class=\"tb-val\">\n            {% if challan.payment_status == 'PAID' %}<span style=\"color:#00aa00;font-weight:900;\">PAID</span>\n            {% elif challan.payment_status == 'VOIDED' %}<span style=\"color:#0066cc;font-weight:900;\">VOIDED</span>\n            {% else %}<span style=\"color:#cc0000;font-weight:900;\">UNPAID</span>{% endif %}\n        </div>\n    </div>\n</div>\n\n<div class=\"barcode-area\">\n      <div style=\"flex:1;text-align:center;padding:6px 8px;\">\n        {% if barcode_svg %}\n          {{ barcode_svg|safe }}\n        {% else %}\n          <div style=\"font-family:monospace;font-size:12px;letter-spacing:2px;\">{{ challan.ticket_no }}</div>\n        {% endif %}\n        <div style=\"font-size:7px;color:#000;margin-top:2px;letter-spacing:0.5px;\">{{ challan.ticket_no }}</div>\n      </div>\n    </div>\n    <div class=\"pay-box\">\n        <div style=\"font-size:5.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#444;\">Payment Within Due Date</div>\n        <div class=\"pay-amt\">PKR {{ challan.fine_amount|floatformat:0 }}/-</div>\n        <div style=\"font-size:6px;margin-top:2px;\"><b>Due Date:</b> {{ challan.due_date|date:\"d-M-Y\" }}</div>\n        <div style=\"font-size:5px;margin-top:3px;border-top:1px solid #ccc;padding-top:2px;color:#333;letter-spacing:0.2px;\">\n            To be credited under Head <b>\"C0263A\"</b> &mdash; IC3 E-Challans\n        </div>\n    </div>\n</div>\n\n<div class=\"section-header\">Offender Information</div>\n<div class=\"data-grid\" style=\"grid-template-columns: 2fr 1fr 1fr 1fr;\">\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Name (First, Middle, Last)</span>\n        <span class=\"dg-val\">{{ challan.owner_name|default:\"Awaiting Excise Integration\" }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Father's Name</span>\n        <span class=\"dg-val\">Awaiting Excise Integration</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Violation Type</span>\n        <span class=\"dg-val alert\">{{ challan.get_violation_type_display|upper }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Fine Amount</span>\n        <span class=\"dg-val\">PKR {{ challan.fine_amount|floatformat:0 }}/-</span>\n    </div>\n</div>\n<div class=\"row-2\">\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Address</span>\n        <span class=\"dg-val\">{{ challan.address|default:\"Awaiting Excise Integration\" }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">City</span>\n        <span class=\"dg-val\">{{ challan.location|default:\"—\" }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Phone No.</span>\n        <span class=\"dg-val\">{{ challan.phone|default:\"Awaiting Excise Integration\" }}</span>\n    </div>\n</div>\n\n<div class=\"section-header\">Vehicle Information</div>\n<div class=\"data-grid\">\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Vehicle Type</span>\n        <span class=\"dg-val\">{{ challan.vehicle_type|default:\"Car\" }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Make / Year</span>\n        <span class=\"dg-val\">{{ challan.make_year|default:\"Awaiting Excise Integration\" }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Color</span>\n        <span class=\"dg-val\">{{ challan.color|default:\"Awaiting Excise Integration\" }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Chassis No.</span>\n        <span class=\"dg-val\">{{ challan.chassis_no|default:\"Awaiting Excise Integration\" }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Date &amp; Time</span>\n        <span class=\"dg-val\">{{ challan.issue_date|date:\"Y-m-d\" }} {{ challan.created_at|time:\"H:i\" }}</span>\n    </div>\n</div>\n\n<div class=\"section-header\">Violation Evidence</div>\n<div class=\"data-grid\" style=\"grid-template-columns: repeat(5, 1fr);\">\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Location</span>\n        <span class=\"dg-val\">{{ challan.location|default:\"—\" }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Legal Direction</span>\n        <span class=\"dg-val\">{{ challan.legal_direction|default:\"UP\" }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Moving Direction</span>\n        <span class=\"dg-val alert\">{{ challan.moving_direction|default:\"DOWN\" }}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">AI Confidence</span>\n        <span class=\"dg-val\">{% if challan.ai_confidence %}{{ challan.ai_confidence|floatformat:2 }}{% else %}N/A{% endif %}</span>\n    </div>\n    <div class=\"dg-cell\">\n        <span class=\"dg-label\">Camera ID</span>\n        <span class=\"dg-val\">{{ challan.camera.camera_id|default:\"CAM-FYP-001\" }}</span>\n    </div>\n</div>\n\n<div class=\"img-container\">\n    <div style=\"font-size:6px;font-weight:900;margin-bottom:2px;letter-spacing:1px;text-transform:uppercase;\">\n        Captured Violation Evidence (2K Enhanced)</div>\n    <div class=\"img-grid\">\n        <div class=\"img-box\">\n            <div class=\"img-label\">WIDE ANGLE</div>\n            {% if challan.detection.raw_image %}\n            <img src=\"file://{{ challan.detection.raw_image.path }}\" alt=\"Wide Angle\">\n            {% else %}\n            <div style=\"height:100px;display:flex;align-items:center;justify-content:center;color:#999;font-size:8px;\">[Not Available]</div>\n            {% endif %}\n        </div>\n        <div class=\"img-box\">\n            <div class=\"img-label\">VEHICLE ZOOM</div>\n            {% if challan.detection.raw_image %}\n            <img src=\"file://{{ challan.detection.raw_image.path }}\" alt=\"Vehicle Zoom\">\n            {% else %}\n            <div style=\"height:100px;display:flex;align-items:center;justify-content:center;color:#999;font-size:8px;\">[Not Available]</div>\n            {% endif %}\n        </div>\n        <div class=\"img-box\">\n            <div class=\"img-label\">LICENSE PLATE</div>\n            {% if challan.detection.plate_crop_image %}\n            <img src=\"file://{{ challan.detection.plate_crop_image.path }}\" alt=\"License Plate\">\n            {% else %}\n            <div style=\"height:100px;display:flex;align-items:center;justify-content:center;color:#999;font-size:8px;\">[Not Available]</div>\n            {% endif %}\n        </div>\n        <div class=\"img-box\">\n            <div class=\"img-label\">DIRECTION</div>\n            <div style=\"height:100px;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#f0f0f0;\">\n                <div style=\"font-size:32px;color:#cc0000;font-weight:bold;\">{{ challan.moving_direction|default:\"\u2193\" }}</div>\n                <div style=\"font-size:6px;color:#333;\">Moving: {{ challan.moving_direction|default:\"DOWN\" }}<br>Legal: {{ challan.legal_direction|default:\"UP\" }}</div>\n            </div>\n        </div>\n    </div>\n</div>\n\n<div class=\"notice\">\n    <b>INSTRUCTIONS:</b> You have been fined for a traffic violation under Section 99-A of the Motor Vehicles\n    Ordinance, 1965. Please pay your fine within <b>10 days</b> of the issuance of this notice. Failure to do so may\n    result in further legal action, and your vehicle may be impounded until the outstanding fine is paid.\n    <div style=\"margin-top:4px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid #ccc;padding-top:3px;font-size:6px;\">\n        <span><b>Paid Challans:</b> 0 &emsp; <b>Unpaid Challans:</b> 0 &emsp; <b>Issue Date:</b> {{ challan.issue_date|date:\"d-M-Y\" }}\n            &emsp; <b>Penalty Points:</b> 0 out of 20</span>\n    </div>\n</div>\n\n<div class=\"cutter\"><span>\u2702</span></div>\n\n<div class=\"post-office\">\n    <h2 style=\"text-align:center;font-weight:900;\">POST OFFICE COPY</h2>\n    <div class=\"po-stamp\"><span>Post Office</span><br><span>Received Stamp</span></div>\n    <div class=\"po-body\">\n        <div>\n            <div class=\"po-row\"><span class=\"po-label\">Ticket No.:</span> {{ challan.ticket_no }}</div>\n            <div class=\"po-row\"><span class=\"po-label\">Name:</span> {{ challan.owner_name|default:\"Awaiting Excise Integration\" }}</div>\n            <div class=\"po-row\"><span class=\"po-label\">Address:</span> {{ challan.address|default:\"Awaiting Excise Integration\" }}</div>\n            <div class=\"po-row\"><span class=\"po-label\">Violation Type:</span> {{ challan.get_violation_type_display }}</div>\n        </div>\n        <div>\n            <div class=\"po-row\"><span class=\"po-label\">Reg. No.:</span> {{ challan.plate_number }}</div>\n            <div class=\"po-row\"><span class=\"po-label\">Amount:</span> PKR {{ challan.fine_amount|floatformat:0 }}/-</div>\n            <div class=\"po-row\"><span class=\"po-label\">Due Date:</span> {{ challan.due_date|date:\"d-M-Y\" }}</div>\n            <div class=\"po-row\"><span class=\"po-label\">Account No.:</span> \"C0263A\" E-Challans</div>\n        </div>\n    </div>\n    <div class=\"po-cashier-row\">\n        <span style=\"font-size:5px;color:#444;font-style:italic;\">* This is a system-generated challan. No manual signature or stamp required.</span>\n        <span><b>Cashier / Counter Signature:</b> _______________</span>\n    </div>\n</div>\n\n\n\n<div class=\"barcode-wrap\">{% if barcode_svg %}{{ barcode_svg|safe }}{% endif %}<div class=\"barcode-text\">{{ challan.ticket_no }}</div></div>\n</body>\n</html>\n", "<div style=\"font-family:Helvetica,Arial,sans-serif;font-size:11px;color:#333;border:1.5px solid #000;background:#fff;padding:0;max-width:100%\">\n  <div style=\"display:flex;justify-content:space-between;align-items:center;padding:8px;border-bottom:2px solid #000\">\n    <div><div style=\"font-size:16px;font-weight:900;letter-spacing:1px\">SAFE CITY</div>\n    <div style=\"font-size:10px;font-weight:700\">Traffic Police Electronic-Challan</div></div>\n  </div>\n  <div style=\"display:grid;grid-template-columns:1fr 1fr 1fr 1fr;border-bottom:1.5px solid #000\">\n    <div style=\"padding:6px;border-right:1px solid #000\"><div style=\"font-size:8px;color:#444\">TICKET NO.</div><b>CH-2026-0001</b></div>\n    <div style=\"padding:6px;border-right:1px solid #000\"><div style=\"font-size:8px;color:#444\">REG. NO.</div><b>LES-1234</b></div>\n    <div style=\"padding:6px;border-right:1px solid #000\"><div style=\"font-size:8px;color:#444\">ISSUE DATE</div><b>15-Aug-2026</b></div>\n    <div style=\"padding:6px\"><div style=\"font-size:8px;color:#444\">STATUS</div><b style=\"color:#cc0000\">UNPAID</b></div>\n  </div>\n  <div style=\"padding:8px;background:#f9f9f9;border-bottom:1.5px solid #000\">\n    <div style=\"font-size:8px\">PAYMENT WITHIN DUE DATE</div>\n    <div style=\"font-size:18px;font-weight:900\">PKR 2,000/-</div>\n    <div style=\"font-size:10px\">Due: 25-Aug-2026 \u00b7 Head C0263A</div>\n  </div>\n  <div style=\"background:#e0e0e0;text-align:center;font-weight:900;font-size:9px;padding:4px;border-bottom:1.5px solid #000\">OFFENDER INFORMATION</div>\n  <div style=\"padding:8px\"><b>Ahmed Khan</b> \u00b7 Wrong Way \u00b7 PKR 2,000<br>Location: Main Boulevard</div>\n  <div style=\"background:#e0e0e0;text-align:center;font-weight:900;font-size:9px;padding:4px;border-bottom:1.5px solid #000\">EVIDENCE</div>\n  <div style=\"padding:8px;display:grid;grid-template-columns:1fr 1fr;gap:4px\">\n    <div style=\"height:48px;background:#efefef;border:1px solid #666;font-size:9px;display:flex;align-items:center;justify-content:center\">WIDE ANGLE</div>\n    <div style=\"height:48px;background:#efefef;border:1px solid #666;font-size:9px;display:flex;align-items:center;justify-content:center\">PLATE CROP</div>\n  </div>\n</div>"),
        ("Safe City Compact", "<div style=\"font-family:Inter,Arial,sans-serif;border:2px solid #1d4f7c;border-radius:8px;overflow:hidden;background:#fff\">\n  <div style=\"background:#1d4f7c;color:#fff;padding:12px;font-weight:800\">SAFE CITY \u00b7 E-CHALLAN</div>\n  <div style=\"padding:12px;font-size:12px;line-height:1.6\">\n    <div><b>CH-2026-0002</b> \u00b7 LES-5678</div>\n    <div style=\"font-size:20px;font-weight:900;margin:8px 0\">PKR 2,000</div>\n    <div>Wrong-way driving \u00b7 Mall Road</div>\n    <div style=\"margin-top:8px;padding:8px;background:#f3f6fb;border-radius:6px;text-align:center\">[ QR / JazzCash ]</div>\n  </div>\n</div>", "<div style=\"font-family:Inter,Arial,sans-serif;border:2px solid #1d4f7c;border-radius:8px;overflow:hidden;background:#fff\">\n  <div style=\"background:#1d4f7c;color:#fff;padding:12px;font-weight:800\">SAFE CITY \u00b7 E-CHALLAN</div>\n  <div style=\"padding:12px;font-size:12px;line-height:1.6\">\n    <div><b>CH-2026-0002</b> \u00b7 LES-5678</div>\n    <div style=\"font-size:20px;font-weight:900;margin:8px 0\">PKR 2,000</div>\n    <div>Wrong-way driving \u00b7 Mall Road</div>\n    <div style=\"margin-top:8px;padding:8px;background:#f3f6fb;border-radius:6px;text-align:center\">[ QR / JazzCash ]</div>\n  </div>\n</div>"),
        ("Legal Notice 99-A", "<div style=\"font-family:Georgia,serif;border:1px solid #000;padding:14px;background:#fff\">\n  <div style=\"text-align:center;font-weight:900;font-size:14px\">Section 99-A \u00b7 Motor Vehicles Ordinance, 1965</div>\n  <hr>\n  <p style=\"font-size:12px\">Ticket <b>CH-2026-0003</b> against vehicle <b>LES-9999</b> for <b>WRONG WAY</b> at Mall Road on 15-Aug-2026.</p>\n  <p style=\"font-size:12px\">Fine <b>PKR 2,000</b> payable before <b>25-Aug-2026</b> under head C0263A.</p>\n  <div style=\"border:1px dashed #888;padding:8px;text-align:center;font-size:11px;margin-top:8px\">POST OFFICE COPY</div>\n</div>", "<div style=\"font-family:Georgia,serif;border:1px solid #000;padding:14px;background:#fff\">\n  <div style=\"text-align:center;font-weight:900;font-size:14px\">Section 99-A \u00b7 Motor Vehicles Ordinance, 1965</div>\n  <hr>\n  <p style=\"font-size:12px\">Ticket <b>CH-2026-0003</b> against vehicle <b>LES-9999</b> for <b>WRONG WAY</b> at Mall Road on 15-Aug-2026.</p>\n  <p style=\"font-size:12px\">Fine <b>PKR 2,000</b> payable before <b>25-Aug-2026</b> under head C0263A.</p>\n  <div style=\"border:1px dashed #888;padding:8px;text-align:center;font-size:11px;margin-top:8px\">POST OFFICE COPY</div>\n</div>"),
        ("Digital Slip", "<div style=\"font-family:Arial;background:#0a1628;color:#fff;padding:14px;border-radius:10px\">\n  <div style=\"font-size:11px;opacity:.8\">DIGITAL SLIP</div>\n  <div style=\"font-size:18px;font-weight:800;margin:4px 0\">CH-2026-0004</div>\n  <div style=\"font-size:13px\">LES-4321 \u00b7 Wrong Way</div>\n  <div style=\"font-size:22px;font-weight:900;margin:10px 0;color:#7dd3fc\">PKR 2,000</div>\n  <div style=\"font-size:11px;opacity:.85\">Due 25-Aug-2026 \u00b7 Pay via app / bank / post office</div>\n</div>", "<div style=\"font-family:Arial;background:#0a1628;color:#fff;padding:14px;border-radius:10px\">\n  <div style=\"font-size:11px;opacity:.8\">DIGITAL SLIP</div>\n  <div style=\"font-size:18px;font-weight:800;margin:4px 0\">CH-2026-0004</div>\n  <div style=\"font-size:13px\">LES-4321 \u00b7 Wrong Way</div>\n  <div style=\"font-size:22px;font-weight:900;margin:10px 0;color:#7dd3fc\">PKR 2,000</div>\n  <div style=\"font-size:11px;opacity:.85\">Due 25-Aug-2026 \u00b7 Pay via app / bank / post office</div>\n</div>"),
    ]
    templates = list(ChallanTemplate.objects.all().order_by('-created_at')[:50])
    if not templates:
        for name, html, preview in DEFAULT_TEMPLATES:
            obj = ChallanTemplate.objects.create(name=name, html_content=html, uploaded_by=request.user)
        templates = list(ChallanTemplate.objects.all().order_by('-created_at')[:50])
    for obj in templates:
        raw = obj.html_content or ''
        if 'SAFE CITY' in raw and 'Traffic Police Electronic-Challan' in raw and len(raw) > 2000:
            obj.preview_html = "<div style=\"font-family:Helvetica,Arial,sans-serif;font-size:11px;color:#333;border:1.5px solid #000;background:#fff;padding:0;max-width:100%\">\n  <div style=\"display:flex;justify-content:space-between;align-items:center;padding:8px;border-bottom:2px solid #000\">\n    <div><div style=\"font-size:16px;font-weight:900;letter-spacing:1px\">SAFE CITY</div>\n    <div style=\"font-size:10px;font-weight:700\">Traffic Police Electronic-Challan</div></div>\n  </div>\n  <div style=\"display:grid;grid-template-columns:1fr 1fr 1fr 1fr;border-bottom:1.5px solid #000\">\n    <div style=\"padding:6px;border-right:1px solid #000\"><div style=\"font-size:8px;color:#444\">TICKET NO.</div><b>CH-2026-0001</b></div>\n    <div style=\"padding:6px;border-right:1px solid #000\"><div style=\"font-size:8px;color:#444\">REG. NO.</div><b>LES-1234</b></div>\n    <div style=\"padding:6px;border-right:1px solid #000\"><div style=\"font-size:8px;color:#444\">ISSUE DATE</div><b>15-Aug-2026</b></div>\n    <div style=\"padding:6px\"><div style=\"font-size:8px;color:#444\">STATUS</div><b style=\"color:#cc0000\">UNPAID</b></div>\n  </div>\n  <div style=\"padding:8px;background:#f9f9f9;border-bottom:1.5px solid #000\">\n    <div style=\"font-size:8px\">PAYMENT WITHIN DUE DATE</div>\n    <div style=\"font-size:18px;font-weight:900\">PKR 2,000/-</div>\n    <div style=\"font-size:10px\">Due: 25-Aug-2026 \u00b7 Head C0263A</div>\n  </div>\n  <div style=\"background:#e0e0e0;text-align:center;font-weight:900;font-size:9px;padding:4px;border-bottom:1.5px solid #000\">OFFENDER INFORMATION</div>\n  <div style=\"padding:8px\"><b>Ahmed Khan</b> \u00b7 Wrong Way \u00b7 PKR 2,000<br>Location: Main Boulevard</div>\n  <div style=\"background:#e0e0e0;text-align:center;font-weight:900;font-size:9px;padding:4px;border-bottom:1.5px solid #000\">EVIDENCE</div>\n  <div style=\"padding:8px;display:grid;grid-template-columns:1fr 1fr;gap:4px\">\n    <div style=\"height:48px;background:#efefef;border:1px solid #666;font-size:9px;display:flex;align-items:center;justify-content:center\">WIDE ANGLE</div>\n    <div style=\"height:48px;background:#efefef;border:1px solid #666;font-size:9px;display:flex;align-items:center;justify-content:center\">PLATE CROP</div>\n  </div>\n</div>"
        else:
            obj.preview_html = raw
    any_custom_active = any(getattr(t, 'is_active', False) for t in templates)

    active_key = sys_settings.pdf_template or 'modern_a4'

    from django.conf import settings as dj_settings
    from pathlib import Path
    file_templates = []
    fs_dir = Path(dj_settings.BASE_DIR) / 'templates' / 'challan' / 'challan_templates'
    if fs_dir.is_dir():
        for fp in sorted(fs_dir.glob('*.html')):
            if fp.name.lower() == 'readme.md':
                continue
            key = fp.stem
            try:
                raw_html = fp.read_text(encoding='utf-8', errors='ignore')
            except OSError:
                raw_html = ''
            file_templates.append({
                'key': key,
                'name': {
                    'modern_a4': 'Modern A4 — Official Safe City E-Challan',
                    'classic_a4': 'Classic A4 — Government E-Challan with Post Office Copy',
                    'legal_notice_99a': 'Legal Notice 99-A — Motor Vehicles Ordinance 1965',
                    'digital_slip': 'Digital Slip — Modern Compact E-Challan',
                }.get(key, key.replace('_', ' ').title()),
                'blurb': 'Built-in layout file',
                'is_active': (key == active_key),
                'is_file': True,
                'preview_html': raw_html[:4000],
                'html_content': raw_html,
                'thumb_label': key,
            })

    card_templates = []
    for t in templates:
        card_templates.append({
            'key': str(t.id),
            'name': t.name,
            'blurb': 'Database template',
            'is_active': (active_key == f'db:{t.id}'),
            'is_file': False,
            'id': t.id,
            'file_url': (t.file.url if t.file else None),
            'preview_html': getattr(t, 'preview_html', None) or (t.html_content or '')[:4000],
            'html_content': t.html_content or '',
            'thumb_label': t.name,
        })

    return render(request, 'dashboard/it_support/challan_templates.html', {
        'challan_templates': templates,
        'templates': card_templates + file_templates,
        'any_custom_active': any_custom_active,
        'active_template_key': active_key,
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT')
def challan_list(request):
    qs = Challan.objects.all().order_by('-issue_date')
    plate_filter = request.GET.get('plate')
    if plate_filter: qs = qs.filter(plate_number__icontains=plate_filter)
    status_filter = request.GET.get('status')
    if status_filter: qs = qs.filter(payment_status=status_filter)
    return render(request, 'dashboard/dig/challan_list.html', {
        'challans': qs[:200], 'total': qs.count(),
        'plate_filter': plate_filter, 'status_filter': status_filter,
    })


@dig_required
def delete_challan(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    if request.method == 'POST':
        AuditLog.write(request, 'challan.delete', 'Challan', challan.id,
                       ticket_no=challan.ticket_no, plate=challan.plate_number)
        ticket = challan.ticket_no
        challan.delete()
        messages.success(request, f"Challan {ticket} permanently deleted.")
        return redirect('dig:challan_list')
    return render(request, 'dashboard/dig/challan_confirm_delete.html', {'challan': challan})


@dig_required
def edit_challan_fine(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    if request.method == 'POST':
        try:
            new_amount = float(request.POST.get('fine_amount'))
            old_amount = challan.fine_amount
            challan.fine_amount = new_amount
            challan.save()
            AuditLog.write(request, 'challan.fine_edit', 'Challan', challan.id,
                           before=str(old_amount), after=str(new_amount))
            messages.success(request, f"Fine for {challan.ticket_no} updated to PKR {new_amount}.")
        except (ValueError, TypeError):
            messages.error(request, "Invalid fine amount.")
    return redirect('dig:challan_list')


@role_required('DIG', 'IT')
def mark_challan_paid(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    challan.mark_paid()
    AuditLog.write(request, 'challan.mark_paid', 'Challan', challan.id, ticket_no=challan.ticket_no)
    messages.success(request, f"Challan {challan.ticket_no} marked as PAID.")
    return redirect('dig:challan_list')


@role_required('DIG', 'IT')
def mark_challan_unpaid(request, challan_id):
    if request.method != 'POST':
        return redirect('dig:challan_list')
    challan = get_object_or_404(Challan, pk=challan_id)
    challan.payment_status = Challan.UNPAID
    challan.paid_at = None
    challan.save(update_fields=['payment_status', 'paid_at'])
    AuditLog.write(request, 'challan.mark_unpaid', 'Challan', challan.id, ticket_no=challan.ticket_no)
    messages.success(request, f"Challan {challan.ticket_no} marked as UNPAID.")
    return redirect('dig:challan_list')

@dig_required
def bulk_fine_adjust(request):
    if request.method != 'POST':
        return redirect('dig:challan_list')
    selected_ids = request.POST.getlist('selected')
    if len(selected_ids) > 100:
        messages.error(request, "Max 100 challans per bulk action.")
        return redirect('dig:challan_list')
    adjust_type = request.POST.get('adjust_type')
    try:
        value = float(request.POST.get('adjust_value', '0'))
    except ValueError:
        messages.error(request, "Invalid adjustment value.")
        return redirect('dig:challan_list')
    from django.db import transaction
    count = 0
    try:
        with transaction.atomic():
            for cid in selected_ids:
                try:
                    c = Challan.objects.get(pk=cid)
                    old = c.fine_amount
                    if adjust_type == 'percent':
                        c.fine_amount = max(0, old * (1 + value / 100))
                    else:
                        c.fine_amount = max(0, old + value)
                    c.save()
                    count += 1
                except Challan.DoesNotExist:
                    continue
            AuditLog.write(request, 'challan.bulk_fine', 'Challan', None,
                           count=count, type=adjust_type, value=value)
    except Exception as e:
        messages.error(request, f"Bulk fine adjust failed: {e}")
        return redirect('dig:challan_list')
    messages.success(request, f"Bulk fine adjust applied to {count} challan(s).")
    return redirect('dig:challan_list')


@dig_required
def bulk_detections(request):
    if request.method != 'POST':
        return redirect('dig:dashboard')
    action = request.POST.get('bulk_action')
    selected_ids = request.POST.getlist('selected')
    if len(selected_ids) > 100:
        messages.error(request, "Max 100 detections per bulk action.")
        return redirect('dig:dashboard')
    notes = request.POST.get('bulk_notes', f"Bulk {action} by DIG")
    from django.db import transaction
    count = 0
    try:
        with transaction.atomic():
            for det_id in selected_ids:
                try:
                    d = Detection.objects.get(pk=det_id, status=Detection.PENDING)
                    d.status = Detection.CONFIRMED if action == 'confirm' else Detection.REJECTED
                    d.reviewed_by = request.user
                    d.reviewed_at = timezone.now()
                    d.review_notes = notes
                    d.save()
                    if action == 'confirm':
                        from admin.officer_portal.views import _create_challan_from_detection
                        _create_challan_from_detection(d, request.user)
                    count += 1
                except Detection.DoesNotExist:
                    continue
            AuditLog.write(request, f'bulk.{action}', 'Detection', None, count=count)
    except Exception as e:
        messages.error(request, f"Bulk {action} failed: {e}")
        return redirect('dig:dashboard')
    messages.success(request, f"Bulk {action}: {count} detection(s) processed.")
    return redirect('dig:dashboard')


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
def audit_log(request):
    qs = AuditLog.objects.all()
    actor = request.GET.get('actor')
    if actor: qs = qs.filter(actor_id=actor)
    action_filter = request.GET.get('action')
    if action_filter: qs = qs.filter(action__icontains=action_filter)
    date_from = request.GET.get('date_from')
    if date_from: qs = qs.filter(timestamp__date__gte=date_from)
    date_to = request.GET.get('date_to')
    if date_to: qs = qs.filter(timestamp__date__lte=date_to)
    qs = qs[:500]
    users = User.objects.filter(role__in=['DIG', 'OFFICER'])
    return render(request, 'dashboard/dig/audit_log.html', {
        'logs': qs, 'users': users, 'actor': actor, 'action_filter': action_filter,
        'date_from': date_from, 'date_to': date_to,
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
def audit_export(request):
    qs = AuditLog.objects.all()[:100000]
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_log.csv"'
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Actor', 'Action', 'Target Model', 'Target ID', 'IP', 'Details'])
    for log in qs:
        writer.writerow([
            log.timestamp.isoformat(),
            str(log.actor) if log.actor else '',
            log.action, log.target_model, log.target_id or '',
            log.ip_address or '', str(log.details),
        ])
    return response


@dig_required
def escalation_list(request):
    escalated = ChallanAppeal.objects.filter(status=ChallanAppeal.ESCALATED).order_by('-escalated_at')
    return render(request, 'dashboard/dig/escalation_list.html', {'appeals': escalated})


@role_required('DIG', 'SSP', 'SUPV')
def appeal_override(request, appeal_id):
    appeal = get_object_or_404(ChallanAppeal, pk=appeal_id)

    user_role = request.user.role
    stage = appeal.current_stage

    if stage == ChallanAppeal.STAGE_OFFICER and user_role != User.OFFICER and user_role != User.DIG:
        messages.info(request, "This appeal is at Officer review stage. Waiting for an Officer to review first.")
    elif stage == ChallanAppeal.STAGE_SSP and user_role != User.SSP and user_role != User.DIG:
        messages.info(request, "This appeal is at SSP review stage. Waiting for SSP to review.")

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        comment = (request.POST.get('comment') or request.POST.get('dig_comment') or '').strip()
        if len(comment) < 30:
            messages.error(request, "Comment is required (min 30 chars).")
            return redirect('dig:appeal_override', appeal_id=appeal.id)

        from accounts.models import User as _User
        from admin.dig_portal.models import Notification as _Notif
        c = appeal.challan
        detail_msg = (
            f"APPEAL {action.upper()} — Stage: {stage.upper()}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Appeal ID: APL-{appeal.id:06d}\n"
            f"Challan No: {c.ticket_no}\n"
            f"Plate: {c.plate_number}\n"
            f"Violation: {c.get_violation_type_display()}\n"
            f"Fine: PKR {c.fine_amount}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Reviewer: {request.user.display_name} ({request.user.role})\n"
            f"Comment: {comment}\n"
        )

        if action == 'route_to_ssp' and stage == ChallanAppeal.STAGE_OFFICER:
            appeal.advance_to_ssp(comment, request.user)
            AuditLog.write(request, 'appeal.officer_route_ssp', 'ChallanAppeal', appeal.id,
                           challan=c.ticket_no, comment=comment[:100])
            for ssp in _User.objects.filter(role=_User.SSP, is_active=True):
                _Notif.objects.create(recipient=ssp,
                    title=f"Appeal routed to SSP — {c.ticket_no}",
                    message=detail_msg + "\n\nOfficer has routed this appeal to SSP for higher review.",
                    category='appeal_pending',
                    target_url=reverse('dig:appeal_override', args=[appeal.id]))
            messages.success(request, "Appeal routed to SSP. All SSPs notified.")
        elif action == 'route_to_dig' and stage == ChallanAppeal.STAGE_SSP:
            appeal.advance_to_dig(comment, request.user)
            AuditLog.write(request, 'appeal.ssp_route_dig', 'ChallanAppeal', appeal.id,
                           challan=c.ticket_no, comment=comment[:100])
            for dig in _User.objects.filter(role=_User.DIG, is_active=True):
                _Notif.objects.create(recipient=dig,
                    title=f"Appeal escalated to DIG — {c.ticket_no}",
                    message=detail_msg + "\n\nSSP has escalated this appeal to DIG for final decision.",
                    category='appeal_escalated',
                    target_url=reverse('dig:appeal_override', args=[appeal.id]))
            messages.success(request, "Appeal escalated to DIG. DIG notified.")
        elif action in ('approve', 'reject'):
            if appeal.status != ChallanAppeal.PENDING:
                messages.error(request, "This appeal has already been decided.")
                return redirect('dig:appeal_override', appeal_id=appeal.id)
            allowed = (
                (stage == ChallanAppeal.STAGE_DIG and user_role == User.DIG)
                or (stage == ChallanAppeal.STAGE_SSP and user_role == User.SSP)
                or (stage == ChallanAppeal.STAGE_OFFICER and user_role == User.OFFICER)
            )
            if not allowed:
                AuditLog.write(request, 'appeal.decision_denied', 'ChallanAppeal', appeal.id,
                               actor_role=user_role, stage=stage)
                messages.error(request, f"Action '{action}' not valid at stage '{stage}' for your role.")
                return redirect('dig:appeal_override', appeal_id=appeal.id)
            decision = ChallanAppeal.APPROVED if action == 'approve' else ChallanAppeal.REJECTED
            appeal.finalize(decision, comment, request.user)
            if action == 'approve' and appeal.challan.payment_status == Challan.UNPAID:
                appeal.challan.payment_status = Challan.VOIDED
                appeal.challan.save()
            AuditLog.write(request, f'appeal.{stage}_{action}', 'ChallanAppeal', appeal.id,
                           challan=c.ticket_no, comment=comment[:100])
            _Notif.objects.create(recipient=appeal.submitted_by,
                title=f"Appeal {action}d — {c.ticket_no}",
                message=detail_msg + f"\n\nDecision: {action.upper()}\nStage: {stage.upper()}",
                category=f'appeal_{action}d',
                target_url="/portal/")
            messages.success(request, f"Appeal {action}d. Final decision recorded. Citizen notified.")
        else:
            messages.error(request, f"Action '{action}' not valid at stage '{stage}' for your role.")
            return redirect('dig:appeal_override', appeal_id=appeal.id)

        return redirect('dig:escalation_list')
    return render(request, 'dashboard/dig/appeal_override.html', {
        'appeal': appeal,
        'current_stage': stage,
        'stage_display': dict(ChallanAppeal.STAGE_CHOICES).get(stage, stage),
        'can_route_to_ssp': stage == ChallanAppeal.STAGE_OFFICER and user_role == User.OFFICER,
        'can_route_to_dig': stage == ChallanAppeal.STAGE_SSP and user_role == User.SSP,
        'can_finalize': (stage == ChallanAppeal.STAGE_DIG and user_role == User.DIG)
                         or (stage == ChallanAppeal.STAGE_OFFICER and user_role in (User.OFFICER, User.DIG))
                         or (stage == ChallanAppeal.STAGE_SSP and user_role in (User.SSP, User.DIG)),
    })


def csrf_failure(request, reason=""):
    return render(
        request,
        'errors/error_page.html',
        {
            'code': 403,
            'title': 'Session Expired (CSRF)',
            'message': (
                'Your session token expired or was missing, so the form '
                'could not be submitted safely. Please go back to the '
                'previous page and re-submit the form.'
            ),
            'reason': reason,
        },
        status=403,
    )


@senior_staff_required
def vehicle_search(request):
    """Search detections + challans by plate / CNIC / owner. Inputs sanitized."""
    import re
    raw = (request.GET.get('q') or '').strip()
    # Allow plate-like or CNIC-like input only
    q = re.sub(r'[^A-Za-z0-9\- ]', '', raw)[:32].strip()
    detections = []
    challans = []
    if q:
        plate_q = q.upper().replace(' ', '')
        cnic_digits = re.sub(r'\D', '', q)
        det_filter = Q(ai_plate_text__icontains=plate_q)
        detections = list(
            Detection.objects.filter(det_filter)
            .select_related('camera')
            .order_by('-created_at')[:50]
        )
        ch_filter = (
            Q(plate_number__icontains=plate_q)
            | Q(owner_name__icontains=q)
        )
        if len(cnic_digits) >= 5:
            ch_filter = ch_filter | Q(cnic__icontains=cnic_digits)
        challans = list(
            Challan.objects.filter(ch_filter).order_by('-issue_date')[:50]
        )
    return render(request, 'dashboard/dig/vehicle_search.html', {
        'q': q,
        'detections': detections,
        'challans': challans,
    })


@senior_staff_required
def flagged_detections(request):
    flagged = Detection.objects.filter(status=Detection.FLAGGED).order_by('-created_at')[:200]
    return render(request, 'dashboard/dig/flagged_detections.html', {'flagged': flagged})


@senior_staff_required
def payment_list(request):
    payments = Challan.objects.filter(payment_status=Challan.PAID).order_by('-paid_at')[:200]
    return render(request, 'dashboard/dig/payment_list.html', {'payments': payments})


@role_required('DIG', 'IT')
def record_payment(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    if request.method == 'POST':
        amount = request.POST.get('amount')
        method = request.POST.get('method', 'BANK')
        txn_id = request.POST.get('transaction_id', '')
        if amount:
            challan.payment_status = Challan.PAID
            challan.paid_at = timezone.now()
            challan.save()
            AuditLog.write(request, 'challan.record_payment', 'Challan', challan.id,
                           challan=challan.ticket_no, amount=amount, method=method, txn=txn_id)
            messages.success(request, f"Payment of PKR {amount} recorded for {challan.ticket_no}.")
            return redirect('dig:challan_list')
    return render(request, 'dashboard/dig/record_payment.html', {'challan': challan})


@senior_staff_required
def violation_stats(request):
    by_type_qs = (Challan.objects.values('violation_type')
                  .annotate(c=Count('id')).order_by('-c'))
    by_type = {row['violation_type']: row['c'] for row in by_type_qs}
    by_type_display = {dict(Challan.VIOLATION_CHOICES).get(k, k): v for k, v in by_type.items()}

    by_location_qs = (Challan.objects.exclude(location__isnull=True).exclude(location='')
                      .values('location').annotate(c=Count('id'))
                      .order_by('-c')[:15])
    by_location = {row['location'] or 'Unknown': row['c'] for row in by_location_qs}
    unknown_count = Challan.objects.filter(Q(location__isnull=True) | Q(location='')).count()
    if unknown_count:
        by_location.setdefault('Unknown', unknown_count)

    type_max = max(by_type_display.values()) if by_type_display else 1
    loc_max = max(by_location.values()) if by_location else 1
    return render(request, 'dashboard/dig/violation_stats.html', {
        'by_type': by_type_display, 'by_location': by_location,
        'type_max': type_max, 'loc_max': loc_max,
    })


@senior_staff_required
def officer_feedback_list(request):
    feedback = OfficerProfile.objects.all().order_by('-updated_at')
    return render(request, 'dashboard/dig/officer_feedback_list.html', {'feedback': feedback})


@role_required('DIG', 'SSP', 'SUPV', 'IT')
def officer_feedback_add(request):
    officers = User.objects.filter(role=User.OFFICER)
    if request.method == 'POST':
        officer_id = request.POST.get('officer_id')
        rating = int(request.POST.get('rating', 5))
        note = request.POST.get('note', '').strip()
        officer = get_object_or_404(User, pk=officer_id, role=User.OFFICER)
        AuditLog.write(request, 'officer.feedback_add', 'User', officer.id,
                       rating=rating, note=note[:120])
        messages.success(request, f"Feedback recorded for {officer.display_name}.")
        return redirect('dig:officer_feedback_list')
    return render(request, 'dashboard/dig/officer_feedback_add.html', {'officers': officers})


def run_auto_blacklist(plate, request=None):
    if not plate:
        return False
    from .models import SystemSettings, AuditLog as AL
    from challans.models import Challan
    settings = SystemSettings.get()
    cfg = getattr(settings, 'template_config', None) or {}
    if not isinstance(cfg, dict):
        cfg = {}
    if not cfg.get('auto_blacklist_enabled', True):
        return False
    threshold = int(cfg.get('auto_blacklist_threshold') or 5)
    unpaid = Challan.objects.filter(plate_number__iexact=plate, payment_status=Challan.UNPAID).count()
    if unpaid < threshold:
        return False
    already = AL.objects.filter(action='blacklist.add').order_by('-timestamp')[:500]
    for e in already:
        d = e.details if isinstance(e.details, dict) else {}
        if (d.get('plate') or '').upper() == plate.upper():
            return False
    entry, _ = BlacklistEntry.objects.update_or_create(
        plate_number=plate.upper(),
        defaults={
            'reason': f'Auto: {unpaid} unpaid challans (threshold {threshold})',
            'is_active': True,
            'created_by': getattr(request, 'user', None) if request else None,
        },
    )
    AL.write(request, 'blacklist.add', 'BlacklistEntry', entry.id,
             plate=plate.upper(),
             reason=f'Auto: {unpaid} unpaid challans (threshold {threshold})')
    return True

@role_required('DIG', 'SSP', 'SUPV')
def blacklist_list(request):
    settings = SystemSettings.get()
    cfg = getattr(settings, 'template_config', None) or {}
    if not isinstance(cfg, dict):
        cfg = {}
    auto_threshold = int(cfg.get('auto_blacklist_threshold') or 5)

    qs = BlacklistEntry.objects.filter(is_active=True).select_related('created_by').order_by('-created_at')[:200]
    rows = []
    for e in qs:
        rows.append({
            'plate': e.plate_number,
            'value': e.plate_number,
            'type': 'plate',
            'reason': e.reason,
            'is_active': e.is_active,
            'actor': (e.created_by.display_name if e.created_by else '—'),
            'when': e.created_at.strftime('%d %b %Y %H:%M') if e.created_at else '—',
            'created_at': e.created_at,
            'created_by': e.created_by,
        })
    # legacy audit rows fallback if table empty
    if not rows:
        entries = AuditLog.objects.filter(action='blacklist.add').order_by('-timestamp')[:200]
        for e in entries:
            details = e.details if isinstance(e.details, dict) else {}
            plate_val = details.get('plate') or '—'
            rows.append({
                'plate': plate_val,
                'value': plate_val,
                'type': details.get('type') or 'plate',
                'reason': details.get('reason') or e.action,
                'is_active': True,
                'actor': (e.actor.display_name if e.actor else '—'),
                'when': e.timestamp.strftime('%d %b %Y %H:%M') if e.timestamp else '—',
                'created_at': e.timestamp,
                'created_by': e.actor,
            })
    return render(request, 'dashboard/dig/blacklist_list.html', {
        'entries': rows,
        'auto_threshold': auto_threshold,
    })


@role_required('DIG', 'SSP')
def blacklist_add(request):
    if request.method == 'POST':
        btype = (request.POST.get('type') or 'plate').strip().lower()
        value = (request.POST.get('value') or request.POST.get('plate_number') or request.POST.get('plate') or '').strip().upper()
        reason = (request.POST.get('reason') or request.POST.get('notes') or '').strip()
        if btype == 'plate':
            lookup_field = 'plate_number'
            value_for_lookup = value
        elif btype == 'cnic':
            lookup_field = 'plate_number'  # we store as plate_number for now
            value_for_lookup = value
        else:
            messages.error(request, "Type 'phone' / 'chassis' not yet supported for blacklist. Use 'plate' or 'cnic'.")
            return render(request, 'dashboard/dig/blacklist_add.html', {})
        if value_for_lookup and reason:
            obj, created = BlacklistEntry.objects.update_or_create(
                plate_number=value_for_lookup,
                defaults={
                    'reason': reason[:255],
                    'is_active': True,
                    'created_by': request.user if request.user.is_authenticated else None,
                },
            )
            AuditLog.write(request, 'blacklist.add', 'BlacklistEntry', obj.id,
                           plate=value_for_lookup, type=btype, reason=reason[:200])
            messages.success(request, f"{btype.title()} {value_for_lookup} {'added to' if created else 'updated on'} blacklist.")
            if request.GET.get('embed') == '1' or request.POST.get('embed') == '1':
                from django.http import HttpResponse
                return HttpResponse(
                    "<script>try{parent.location.reload();}catch(e){location.href='/portal/dig/blacklist/';}</script>"
                )
            return redirect('dig:blacklist_list')
        messages.error(request, "Value and reason are required.")
    return render(request, 'dashboard/dig/blacklist_add.html', {})


@dig_required
def broadcast_notification(request):
    messages.info(request, "Broadcasting was removed. Use the Alerts Hub for alerts and popup ads.")
    return redirect(_alerts_hub_url('alerts', request))


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


@role_required('DIG', 'IT')
def verify_citizen_payment(request, challan_id):
    from admin.dig_portal.models import Notification, AuditLog as AL
    challan = get_object_or_404(Challan, pk=challan_id)

    txn_ref = ''
    method_name = ''
    try:
        last = (AL.objects
                .filter(action='challan.payment_submitted', target_model='Challan', target_id=challan.id)
                .order_by('-timestamp')
                .first())
        if last and last.details:
            details = last.details if isinstance(last.details, dict) else {}
            txn_ref = details.get('txn_ref') or details.get('txn') or ''
            method_name = details.get('payment_method') or details.get('method') or ''
    except Exception:
        pass

    if request.method == 'POST':
        action = (request.POST.get('action') or 'confirm').strip().lower()
        note = (request.POST.get('note') or '').strip()
        if action == 'confirm':
            if challan.payment_status == Challan.PAID:
                messages.info(request, f"Challan {challan.ticket_no} is already PAID.")
            else:
                challan.mark_paid()
                AuditLog.write(
                    request, 'challan.payment_verified', 'Challan', challan.id,
                    ticket=challan.ticket_no,
                    amount=str(challan.fine_amount),
                    txn_ref=txn_ref or request.POST.get('txn_ref', ''),
                    method=method_name or request.POST.get('method', 'CITIZEN_SUBMITTED'),
                    note=note,
                )
                Notification.objects.filter(
                    category='payment_verification',
                    is_read=False,
                    message__icontains=challan.ticket_no,
                ).update(is_read=True)
                messages.success(
                    request,
                    f"Payment verified. Challan {challan.ticket_no} marked PAID."
                )
        elif action == 'reject':
            AuditLog.write(
                request, 'challan.payment_rejected', 'Challan', challan.id,
                ticket=challan.ticket_no,
                txn_ref=txn_ref or request.POST.get('txn_ref', ''),
                note=note or 'Staff rejected citizen payment submission',
            )
            Notification.objects.filter(
                category='payment_verification',
                is_read=False,
                message__icontains=challan.ticket_no,
            ).update(is_read=True)
            messages.warning(
                request,
                f"Payment submission for {challan.ticket_no} rejected. Challan remains UNPAID."
            )
        return redirect('dig:challan_list')

    return render(request, 'dashboard/dig/verify_payment.html', {
        'challan': challan,
        'txn_ref': txn_ref,
        'method_name': method_name,
    })


@dig_required
def penalty_config(request):
    from .models import SystemSettings
    s = SystemSettings.get()
    cfg = s.template_config or {}

    VIOLATION_TYPES = [
        {'key': 'wrong_way',    'label': 'Wrong Way Driving',    'icon': 'fa-arrow-right-arrow-left',
         'desc': 'Vehicle travelling against the legal direction of traffic',
         'color': 'red',     'default_amount': 500, 'default_points': 3, 'enabled': True},
        {'key': 'no_helmet',    'label': 'No Helmet',            'icon': 'fa-helmet-safety',
         'desc': 'Rider not wearing a helmet on a motorcycle',
         'color': 'amber',   'default_amount': 300, 'default_points': 2, 'enabled': False},
        {'key': 'signal_break', 'label': 'Signal Break',         'icon': 'fa-traffic-light',
         'desc': 'Vehicle crossing a red traffic signal',
         'color': 'purple',  'default_amount': 500, 'default_points': 3, 'enabled': False},
        {'key': 'over_speed',   'label': 'Over Speed',           'icon': 'fa-gauge-high',
         'desc': 'Vehicle exceeding the posted speed limit',
         'color': 'blue',    'default_amount': 800, 'default_points': 4, 'enabled': False},
    ]

    if request.method == 'POST':
        for v in VIOLATION_TYPES:
            k = v['key']
            amt = request.POST.get(f'amount_{k}') or request.POST.get(f'fine_{k}') or request.POST.get(k)
            pts = request.POST.get(f'points_{k}')
            enabled = request.POST.get(f'enabled_{k}')
            if amt:
                try: cfg[f'{k}_amount'] = int(amt)
                except (ValueError, TypeError): pass
            if pts:
                try: cfg[f'{k}_points'] = int(pts)
                except (ValueError, TypeError): pass
            if enabled is not None:
                cfg[f'{k}_enabled'] = (enabled in ('on', '1', 'true', True))
        for key, val in request.POST.items():
            if key.startswith('fine_'):
                vtype = key[5:]
                try:
                    cfg[f'{vtype}_amount'] = int(val)
                except (ValueError, TypeError):
                    pass
        s.template_config = cfg
        fines = dict(SystemSettings.DEFAULT_FINES)
        if isinstance(s.default_fines, dict):
            fines.update(s.default_fines)
        for v in VIOLATION_TYPES:
            k = v['key']
            if f'{k}_amount' in cfg:
                fines[k] = cfg[f'{k}_amount']
        for key, val in cfg.items():
            if key.endswith('_amount'):
                vtype = key[:-7]
                fines[vtype] = val
        s.default_fines = fines
        s.save()
        AuditLog.write(request, 'penalty.config_update', 'SystemSettings', s.id)
        messages.success(request, "Penalty configuration updated.")
        return redirect('dig:penalty_config')

    violations = []
    for v in VIOLATION_TYPES:
        k = v['key']
        violations.append({
            'key': k,
            'label': v['label'],
            'icon': v['icon'],
            'desc': v['desc'],
            'color': v['color'],
            'amount': cfg.get(f'{k}_amount', v['default_amount']),
            'points': cfg.get(f'{k}_points', v['default_points']),
            'enabled': cfg.get(f'{k}_enabled', v['enabled']),
        })
    active_count = sum(1 for v in violations if v['enabled'])
    return render(request, 'dashboard/dig/penalty_config.html', {
        'settings': s,
        'violations': violations,
        'active_count': active_count,
        'total_count': len(violations),
    })


@senior_staff_required
def shift_management(request):
    from .models import Shift
    officers = User.objects.filter(role=User.OFFICER).order_by('first_name')
    shifts = Shift.objects.select_related('officer').order_by('-start_time')[:100]
    return render(request, 'dashboard/dig/shift_management.html', {
        'officers': officers,
        'shifts': shifts,
    })


@dig_required
def shift_add(request):
    from .models import Shift
    from accounts.models import User
    if request.method != 'POST':
        officers = User.objects.filter(role=User.OFFICER, is_active=True).order_by('first_name')
        return render(request, 'dashboard/dig/shift_add.html', {'officers': officers})
    if request.method == 'POST':
        start = request.POST.get('start_time')
        end = request.POST.get('end_time')
        officer_id = request.POST.get('officer_id')
        if not start or not end:
            messages.error(request, "Start and end time are required.")
            return redirect('dig:shift_management')
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone as dj_tz
        from datetime import datetime
        def _parse_dt(val):
            if not val:
                return None
            val = str(val).strip().replace(' ', 'T')
            dt = parse_datetime(val)
            if dt is None:
                for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
                    try:
                        dt = datetime.strptime(val[:19], fmt)
                        break
                    except ValueError:
                        continue
            if dt is None:
                return None
            if dj_tz.is_naive(dt):
                try:
                    dt = dj_tz.make_aware(dt, dj_tz.get_current_timezone())
                except Exception:
                    pass
            return dt
        start_dt = _parse_dt(start)
        end_dt = _parse_dt(end)
        if not start_dt or not end_dt or end_dt <= start_dt:
            messages.error(request, "Invalid shift window.")
            return redirect('dig:shift_management')
        officer = None
        if officer_id:
            officer = User.objects.filter(pk=officer_id, role=User.OFFICER, is_active=True).first()
        if officer is None:
            officer = Shift.auto_assign_officer(start_dt, end_dt) if hasattr(Shift, 'auto_assign_officer') else None
        if officer is None:
            messages.error(request, "No eligible officer available for this slot.")
            return redirect('dig:shift_management')
        Shift.objects.create(
            officer=officer,
            start_time=start_dt,
            end_time=end_dt,
            assigned_by=request.user,
        )
        messages.success(request, f"Shift assigned to {officer.get_full_name() or officer.username}.")
        return redirect('dig:shift_management')
    return redirect('dig:shift_management')


@it_required
def system_health(request):
    from detections.ai import is_models_available, get_model_info
    return render(request, 'dashboard/dig/system_health.html', {
        'db_challans': Challan.objects.count(),
        'db_detections': Detection.objects.count(),
        'db_users': User.objects.count(),
        'db_cameras': Camera.objects.count(),
        'ai_available': is_models_available(),
        'model_info': get_model_info(),
    })


@it_required
def backup_list(request):
    import json
    from pathlib import Path
    from django.core import serializers
    from django.conf import settings as dj_settings

    backup_dir = Path(dj_settings.BASE_DIR) / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)

    if request.method == 'POST':
        action = request.POST.get('action') or ''
        if action == 'create':
            payload = {
                'created_at': timezone.now().isoformat(),
                'created_by': getattr(request.user, 'username', ''),
                'users': json.loads(serializers.serialize('json', User.objects.all())),
                'cameras': json.loads(serializers.serialize('json', Camera.objects.all())),
                'challans': json.loads(serializers.serialize('json', Challan.objects.all()[:5000])),
                'detections': json.loads(serializers.serialize('json', Detection.objects.all()[:5000])),
            }
            fname = f"backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
            fpath = backup_dir / fname
            fpath.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            AuditLog.write(request, 'backup.create', 'Backup', None, file=fname, size=fpath.stat().st_size)
            messages.success(request, f"Backup created: {fname}")
            return redirect(request.path)
        if action == 'import' and request.FILES.get('backup_file'):
            try:
                data = json.loads(request.FILES['backup_file'].read().decode('utf-8'))
                fname = f"import_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{request.FILES['backup_file'].name}"
                (backup_dir / fname).write_text(json.dumps(data, indent=2), encoding='utf-8')
                AuditLog.write(request, 'backup.import', 'Backup', None, file=fname)
                messages.success(request, f"Backup file stored as {fname}. Review before applying restore.")
            except Exception as e:
                messages.error(request, f"Import failed: {e}")
            return redirect(request.path)

    files = []
    for f in sorted(backup_dir.glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True)[:50]:
        files.append({
            'name': f.name,
            'size_kb': round(f.stat().st_size / 1024, 1),
            'mtime': timezone.datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.get_current_timezone()),
        })
    logs = AuditLog.objects.filter(action__startswith='backup.').order_by('-timestamp')[:20]
    return render(request, 'dashboard/it_support/backup_list.html', {'backups': files, 'logs': logs})


@it_required
def backup_download(request, filename):
    from django.http import FileResponse
    from django.conf import settings as dj_settings
    safe = Path(filename).name
    path = Path(dj_settings.BASE_DIR) / 'backups' / safe
    if not path.exists() or path.suffix != '.json':
        messages.error(request, "Backup not found.")
        return redirect('it_support_portal:backup_list')
    return FileResponse(open(path, 'rb'), as_attachment=True, filename=safe)


@dig_required
def generate_report(request):
    fmt = (request.GET.get('format') or '').lower()
    kind = (request.GET.get('kind') or 'all').lower()
    qs = Challan.objects.all().order_by('-issue_date')
    if kind == 'financial':
        qs = qs.filter(payment_status=Challan.PAID)
    if fmt == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="safecity_challan_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Ticket', 'Plate', 'Owner', 'Violation', 'Amount', 'Issue Date', 'Due Date', 'Status', 'Location'])
        for c in qs[:10000]:
            writer.writerow([
                c.ticket_no, c.plate_number, c.owner_name or '',
                c.get_violation_type_display(), c.fine_amount, c.issue_date,
                c.due_date, c.payment_status, c.location or '',
            ])
        return response
    if fmt == 'pdf':
        rows = []
        for c in qs[:2000]:
            rows.append(
                f"<tr><td>{c.ticket_no}</td><td>{c.plate_number}</td>"
                f"<td>{c.get_violation_type_display()}</td><td>{c.fine_amount}</td>"
                f"<td>{c.issue_date}</td><td>{c.payment_status}</td></tr>"
            )
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>SafeCity Challan Report</title>"
            "<style>body{font-family:Arial,sans-serif;font-size:11px;margin:24px}"
            "h1{font-size:18px}table{border-collapse:collapse;width:100%}"
            "th,td{border:1px solid #ccc;padding:6px;text-align:left}"
            "th{background:#f1f5f9}@media print{body{margin:0}}</style></head><body>"
            "<h1>SafeCity FYP — Challan Report</h1>"
            f"<p>Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')} · Rows: {len(rows)}</p>"
            "<table><thead><tr><th>Ticket</th><th>Plate</th><th>Violation</th>"
            "<th>Amount</th><th>Issued</th><th>Status</th></tr></thead><tbody>"
            + "".join(rows) +
            "</tbody></table>"
            "<script>window.onload=function(){window.print();}</script>"
            "</body></html>"
        )
        response = HttpResponse(html, content_type='text/html; charset=utf-8')
        response['Content-Disposition'] = 'inline; filename="safecity_challan_report.pdf.html"'
        return response
    return render(request, 'dashboard/dig/generate_report.html', {})


@senior_staff_required
def reports(request):
    return render(request, 'dashboard/dig/reports.html', {})


@it_required
def camera_assignments(request):
    from realtime.models import CameraAssignment
    officers = User.objects.filter(role=User.OFFICER, is_active=True)
    cameras = Camera.objects.filter(is_active=True)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign':
            camera_id = request.POST.get('camera_id')
            officer_id = request.POST.get('officer_id')
            notes = request.POST.get('notes', '').strip()
            try:
                camera = Camera.objects.get(pk=camera_id)
                officer = User.objects.get(pk=officer_id, role=User.OFFICER)
                # Hard limit: 1 active camera per officer
                existing = CameraAssignment.objects.filter(officer=officer, is_active=True).exclude(camera=camera)
                if existing.exists():
                    messages.error(
                        request,
                        f"{officer.display_name} already has a camera assigned. "
                        "Unassign it first (limit: 1 camera per officer)."
                    )
                    return redirect(request.resolver_match.namespace + ':camera_assignments'
                                    if getattr(request, 'resolver_match', None) else 'dig:camera_assignments')
                assignment, created = CameraAssignment.objects.get_or_create(
                    camera=camera, officer=officer,
                    defaults={
                        'assigned_by': request.user,
                        'is_active': True,
                        'notes': notes or None,
                    }
                )
                if not created:
                    assignment.is_active = True
                    assignment.notes = notes or assignment.notes
                    assignment.save()
                AuditLog.write(request, 'camera.assign', 'CameraAssignment', assignment.id,
                               camera=camera.camera_id, officer=officer.display_name)
                messages.success(request, f"Camera {camera.camera_id} assigned to {officer.display_name}.")
            except (Camera.DoesNotExist, User.DoesNotExist) as e:
                messages.error(request, f"Assignment failed: {e}")
            ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'dig'
            return redirect(f'{ns}:camera_assignments')

        elif action == 'unassign':
            assignment_id = request.POST.get('assignment_id')
            try:
                assignment = CameraAssignment.objects.get(pk=assignment_id)
                assignment.is_active = False
                assignment.save()
                AuditLog.write(request, 'camera.unassign', 'CameraAssignment', assignment.id,
                               camera=assignment.camera.camera_id, officer=assignment.officer.display_name)
                messages.success(request, f"Camera {assignment.camera.camera_id} unassigned from {assignment.officer.display_name}.")
            except CameraAssignment.DoesNotExist:
                messages.error(request, "Assignment not found.")
            return redirect('dig:camera_assignments')

    assignments = CameraAssignment.objects.filter(is_active=True).select_related('camera', 'officer', 'assigned_by')
    return render(request, 'dashboard/dig/camera_assignments.html', {
        'officers': officers, 'cameras': cameras, 'assignments': assignments,
    })


@dig_required
def challan_confirm_delete(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    if request.method == 'POST':
        AuditLog.write(request, 'challan.delete', 'Challan', challan.id, ticket=challan.ticket_no)
        challan.delete()
        messages.success(request, f"Challan {challan.ticket_no} deleted.")
        return redirect('dig:challan_list')
    return render(request, 'dashboard/dig/challan_confirm_delete.html', {'challan': challan})


@any_permission_required('officer_pki', 'officer_profile_manage')
def officer_signatures(request):
    """Manage officer e-signatures centrally. Lists all staff officers + their signature status."""
    from django.db.models import Q
    qs = (User.objects
          .filter(role__in=[User.OFFICER, User.SSP, User.SUPERVISOR, User.DIG])
          .order_by('first_name', 'username'))

    role_filter = (request.GET.get('role') or '').strip()
    if role_filter and role_filter in [User.OFFICER, User.SSP, User.SUPERVISOR, User.DIG]:
        qs = qs.filter(role=role_filter)

    search = (request.GET.get('q') or '').strip()
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search) | Q(last_name__icontains=search) |
            Q(email__icontains=search) | Q(username__icontains=search) |
            Q(staff_id__icontains=search)
        )

    if request.method == 'POST':
        officer_id = request.POST.get('officer_id')
        officer = User.objects.filter(pk=officer_id).first()
        if not officer:
            messages.error(request, "Officer not found.")
            return redirect(request.path)
        action = request.POST.get('action', 'signature')
        if action == 'signature':
            sig = request.FILES.get('signature')
            stamp = request.FILES.get('stamp')
            if sig:
                if not sig.content_type or not sig.content_type.startswith('image/'):
                    messages.error(request, "Signature must be an image (PNG with transparency preferred).")
                    return redirect(request.path + f'?role={role_filter}&q={search}')
                officer.signature = sig
            if stamp:
                if not stamp.content_type or not stamp.content_type.startswith('image/'):
                    messages.error(request, "Stamp must be an image.")
                    return redirect(request.path + f'?role={role_filter}&q={search}')
                officer.signature_stamp = stamp
            officer.signature_name = (request.POST.get('signature_name') or '').strip() or None
            officer.signature_designation = (request.POST.get('signature_designation') or '').strip() or None
            officer.save()
            try:
                AuditLog.write(request, 'officer.signature_update', 'User', officer.id,
                               officer_email=officer.email)
            except Exception:
                pass
            messages.success(request, f"Signature updated for {officer.display_name}.")
        elif action == 'profile':
            officer.first_name = (request.POST.get('first_name') or officer.first_name).strip()
            officer.last_name = (request.POST.get('last_name') or '').strip()
            officer.staff_id = (request.POST.get('staff_id') or officer.staff_id or '').strip() or None
            officer.designation = (request.POST.get('designation') or officer.designation or '').strip() or None
            officer.region = (request.POST.get('region') or officer.region or '').strip() or None
            officer.save()
            messages.success(request, f"Profile updated for {officer.display_name}.")
        return redirect(request.path + f'?role={role_filter}&q={search}')

    # Pagination
    page = max(1, int(request.GET.get('page') or 1))
    from django.core.paginator import Paginator
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(page)

    return render(request, 'dashboard/dig/officer_signatures.html', {
        'page_obj': page_obj,
        'officers': page_obj.object_list,
        'role_filter': role_filter,
        'search': search,
        'has_signature': sum(1 for o in page_obj.object_list if o.signature),
    })


@dig_required
def regional_command(request):
    regions = []
    region_names = ['Central', 'North', 'South', 'East', 'West', 'City Centre']
    for r in region_names:
        cam_count = Camera.objects.filter(location__icontains=r, is_active=True).count()
        cam_online = Camera.objects.filter(location__icontains=r, health_status='online').count()
        viol_count = Challan.objects.filter(location__icontains=r).count()
        officer_count = User.objects.filter(role=User.OFFICER, region__icontains=r).count()
        ssp_count = User.objects.filter(role=User.SSP, region__icontains=r).count()
        regions.append({
            'name': r, 'cameras': cam_count, 'cameras_online': cam_online,
            'violations': viol_count, 'officers': officer_count, 'ssps': ssp_count,
        })
    all_cam = Camera.objects.filter(is_active=True).count()
    all_online = Camera.objects.filter(health_status='online').count()
    all_viol = Challan.objects.count()
    all_officers = User.objects.filter(role=User.OFFICER).count()
    return render(request, 'dashboard/dig/regional_command.html', {
        'regions': regions,
        'total_cameras': all_cam, 'total_online': all_online,
        'total_violations': all_viol, 'total_officers': all_officers,
    })


@staff_required
def camera_health(request):
    cameras = Camera.objects.all().order_by('-installed_date')
    total = cameras.count()
    online = cameras.filter(health_status='online').count()
    offline = cameras.filter(health_status='offline').count()
    unknown = cameras.filter(health_status='unknown').count()
    degraded = 0
    return render(request, 'dashboard/dig/camera_health.html', {
        'cameras': cameras, 'total': total, 'online': online,
        'offline': offline, 'unknown': unknown, 'degraded': degraded,
    })


@dig_required
def compliance(request):
    pending_reviews = Detection.objects.filter(status=Detection.PENDING).count()
    total_challans = Challan.objects.count()
    total_appeals = ChallanAppeal.objects.count()
    audit_entries = AuditLog.objects.count()
    return render(request, 'dashboard/dig/compliance.html', {
        'pending_reviews': pending_reviews, 'total_challans': total_challans,
        'total_appeals': total_appeals, 'audit_entries': audit_entries,
    })


@role_required('DIG', 'AUDIT', 'IT')
def operational_audit(request):
    recent_audit = AuditLog.objects.all().order_by('-timestamp')[:50]
    officer_activity = User.objects.filter(role=User.OFFICER).annotate(
        review_count=Count('reviewed_detections', filter=Q(reviewed_detections__status__in=['confirmed', 'rejected']))
    ).order_by('-review_count')[:20]
    return render(request, 'dashboard/dig/operational_audit.html', {
        'recent_audit': recent_audit, 'officer_activity': officer_activity,
    })


@role_required('DIG', 'AUDIT', 'IT')
def financial_audit(request):
    total_collected = Challan.objects.filter(payment_status=Challan.PAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    total_pending = Challan.objects.filter(payment_status=Challan.UNPAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    total_voided = Challan.objects.filter(payment_status=Challan.VOIDED).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    recent_payments = Challan.objects.filter(payment_status=Challan.PAID).order_by('-paid_at')[:30]
    return render(request, 'dashboard/dig/financial_audit.html', {
        'total_collected': total_collected, 'total_pending': total_pending,
        'total_voided': total_voided, 'recent_payments': recent_payments,
    })


@dig_required


def regional_access(request):
    ssp_users = User.objects.filter(role=User.SSP)
    supervisor_users = User.objects.filter(role=User.SUPERVISOR)
    return render(request, 'dashboard/dig/regional_access.html', {
        'ssp_users': ssp_users, 'supervisor_users': supervisor_users,
    })


@dig_required
def operational_reports(request):
    today = timezone.localdate()
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)
    daily = Challan.objects.filter(issue_date=today).count()
    weekly = Challan.objects.filter(issue_date__gte=week_ago).count()
    monthly = Challan.objects.filter(issue_date__gte=month_ago).count()
    return render(request, 'dashboard/dig/operational_reports.html', {
        'daily': daily, 'weekly': weekly, 'monthly': monthly,
    })


@dig_required
def financial_reports(request):
    today = timezone.localdate()
    month_ago = today - datetime.timedelta(days=30)
    collected = Challan.objects.filter(payment_status=Challan.PAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    pending = Challan.objects.filter(payment_status=Challan.UNPAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    this_month = Challan.objects.filter(paid_at__date__gte=month_ago, payment_status=Challan.PAID).aggregate(
        total=Sum('fine_amount'))['total'] or 0
    return render(request, 'dashboard/dig/financial_reports.html', {
        'collected': collected, 'pending': pending, 'this_month': this_month,
    })


@staff_required
def staff_change_password(request):
    return self_profile(request)


@staff_required
def self_profile(request):
    from django.urls import reverse
    user = request.user
    own_ns = request.resolver_match.namespace or 'dig'
    own_url_name = f'{own_ns}:self_profile'

    if request.method == 'POST':
        action = request.POST.get('action') or 'avatar'
        if action == 'password':
            old_password = request.POST.get('old_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            if not user.check_password(old_password):
                messages.error(request, "Current password is incorrect.")
            elif len(new_password) < 12:
                messages.error(request, "New password must be at least 12 characters.")
            elif new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
            else:
                user.set_password(new_password)
                user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                AuditLog.write(request, 'user.password_change', 'User', user.id)
                messages.success(request, "Password changed successfully.")
            return redirect(own_url_name)
        if action == 'avatar' and request.FILES.get('avatar'):
            avatar = request.FILES['avatar']
            if avatar.content_type and not avatar.content_type.startswith('image/'):
                messages.error(request, "Please upload an image file.")
            else:
                user.avatar = avatar
                user.save(update_fields=['avatar'])
                AuditLog.write(request, 'user.avatar_update', 'User', user.id)
                messages.success(request, "Profile photo updated.")
            return redirect(own_url_name)
        if action == 'profile':
            user.first_name = (request.POST.get('first_name') or user.first_name).strip()
            user.last_name = (request.POST.get('last_name') or '').strip()
            user.email = (request.POST.get('email') or user.email).strip()
            user.phone = (request.POST.get('phone') or user.phone or '').strip() or None
            user.staff_id = (request.POST.get('staff_id') or user.staff_id or '').strip() or None
            user.designation = (request.POST.get('designation') or user.designation or '').strip() or None
            user.department = (request.POST.get('department') or user.department or '').strip() or None
            user.region = (request.POST.get('region') or user.region or '').strip() or None
            user.signature_name = (request.POST.get('signature_name') or '').strip() or None
            user.signature_designation = (request.POST.get('signature_designation') or '').strip() or None
            user.save()
            AuditLog.write(request, 'user.profile_update', 'User', user.id)
            messages.success(request, "Profile details updated.")
            return redirect(own_url_name)
        if action == 'signature':
            sig = request.FILES.get('signature')
            stamp = request.FILES.get('signature_stamp')
            if sig and sig.content_type and not sig.content_type.startswith('image/'):
                messages.error(request, "Signature must be an image (PNG with transparency preferred).")
            elif stamp and stamp.content_type and not stamp.content_type.startswith('image/'):
                messages.error(request, "Stamp must be an image.")
            else:
                if sig:
                    user.signature = sig
                if stamp:
                    user.signature_stamp = stamp
                user.signature_name = (request.POST.get('signature_name') or user.signature_name or '').strip() or None
                user.signature_designation = (request.POST.get('signature_designation') or user.signature_designation or '').strip() or None
                user.save()
                AuditLog.write(request, 'user.signature_update', 'User', user.id)
                messages.success(request, "Signature / stamp updated.")
            return redirect(own_url_name)
        messages.info(request, "Only photo, signature, profile, and password can be changed here.")
        return redirect(own_url_name)

    embed = request.GET.get('embed') == '1'
    if embed:
        template = 'dashboard/dig/self_profile_embed.html'
    else:
        template = 'dashboard/dig/self_profile.html'

    last_login = getattr(user, 'last_login', None)
    date_joined = getattr(user, 'date_joined', None)
    embed_url = reverse(own_url_name) + '?embed=1'
    return render(request, template, {
        'profile_user': user,
        'embed': embed,
        'own_namespace': own_ns,
        'embed_url': embed_url,
        'last_login': last_login,
        'date_joined': date_joined,
        'is_locked': getattr(user, 'is_locked', False),
    })


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


@any_permission_required('camera_feed', 'view_cameras')
def camera_snapshot(request, camera_id):
    from django.http import FileResponse as _FileResponse
    from django.conf import settings as dj_settings
    import os
    camera = get_object_or_404(Camera, pk=camera_id)
    if request.user.role == 'OFFICER':
        from realtime.models import CameraAssignment
        if not CameraAssignment.objects.filter(camera=camera, officer=request.user, is_active=True).exists():
            raise Http404

    latest = Detection.objects.filter(camera=camera).order_by('-created_at').first()
    if latest and latest.raw_image:
        try:
            return _FileResponse(open(latest.raw_image.path, 'rb'), content_type='image/jpeg')
        except Exception:
            pass

    if camera.http_snapshot_url and not camera.http_snapshot_url.startswith(('/media/', 'media/')):
        try:
            import urllib.request
            req = urllib.request.Request(camera.http_snapshot_url, headers={'User-Agent': 'SafeCity/1.0'})
            resp = urllib.request.urlopen(req, timeout=5)
            return HttpResponse(resp.read(), content_type='image/jpeg')
        except Exception:
            pass

    video_url = (camera.rtsp_url or camera.http_snapshot_url or '').strip()
    if video_url:
        media_url = (dj_settings.MEDIA_URL or '/media/').rstrip('/') + '/'
        rel = video_url
        if video_url.startswith(media_url):
            rel = video_url[len(media_url):]
        elif video_url.startswith('/media/'):
            rel = video_url[len('/media/'):]
        elif video_url.startswith('media/'):
            rel = video_url[len('media/'):]
        lower = rel.lower()
        if any(lower.endswith(ext) for ext in ('.mp4', '.avi', '.mkv', '.mov', '.webm', '.m4v')):
            abs_path = os.path.join(dj_settings.MEDIA_ROOT, rel.replace('/', os.sep))
            if os.path.isfile(abs_path):
                try:
                    import cv2
                    cap = cv2.VideoCapture(abs_path)
                    if cap.isOpened():
                        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                        target = max(0, total // 3) if total > 3 else 0
                        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                        ok, frame = cap.read()
                        if not ok:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ok, frame = cap.read()
                        cap.release()
                        if ok and frame is not None:
                            h, w = frame.shape[:2]
                            if w > 960:
                                scale = 960.0 / w
                                frame = cv2.resize(frame, (960, int(h * scale)))
                            ok2, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                            if ok2:
                                return HttpResponse(buf.tobytes(), content_type='image/jpeg')
                except Exception:
                    pass

    return HttpResponse(status=204)


@staff_required
def camera_snapshot_json(request):
    from django.urls import resolve
    try:
        current_ns = resolve(request.path_info).namespace or 'dig'
    except Exception:
        current_ns = 'dig'
    cameras = Camera.objects.filter(is_active=True).order_by('-installed_date')
    data = []
    for cam in cameras:
        latest = Detection.objects.filter(camera=cam).order_by('-created_at').first()
        has_snapshot = bool(latest and latest.raw_image)
        data.append({
            'id': cam.id,
            'camera_id': cam.camera_id,
            'location': cam.location,
            'direction': cam.get_legal_direction_display(),
            'direction_code': cam.legal_direction,
            'health_status': cam.health_status,
            'is_active': cam.is_active,
            'is_streaming': cam.is_streaming,
            'rtsp_url': cam.rtsp_url or '',
            'snapshot_url': reverse(f'{current_ns}:camera_snapshot', args=[cam.id]),
            'has_snapshot': has_snapshot,
            'last_frame_at': cam.last_frame_at.isoformat() if cam.last_frame_at else None,
            'latest_detection_id': latest.id if latest else None,
        })
    return JsonResponse({'cameras': data})


@dig_required

def dashboard_v2(request):
    """Deprecated command-centre view — redirect to primary DIG dashboard."""
    from django.shortcuts import redirect
    return redirect('dig:dashboard')


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT')
def case_escalation_tracker(request):
    """Appeals queue for SSP/DIG: pending at SSP stage + escalated to DIG."""
    from django.db.models import Q
    role = getattr(request.user, 'role', '')
    qs = ChallanAppeal.objects.all().select_related('challan', 'submitted_by')
    if role == 'SSP':
        # SSP sees pending appeals at SSP stage + any escalated they may track
        qs = qs.filter(
            Q(status=ChallanAppeal.PENDING, current_stage=ChallanAppeal.STAGE_SSP)
            | Q(status=ChallanAppeal.ESCALATED)
        )
    elif role == 'DIG':
        qs = qs.filter(
            Q(status=ChallanAppeal.ESCALATED)
            | Q(status=ChallanAppeal.PENDING, current_stage=ChallanAppeal.STAGE_DIG)
        )
    else:
        qs = qs.filter(status__in=[ChallanAppeal.PENDING, ChallanAppeal.ESCALATED])
    appeals = list(qs.order_by('-created_at')[:100])
    escalated_appeals = [a for a in appeals if a.status == ChallanAppeal.ESCALATED]
    pending_appeals = [a for a in appeals if a.status == ChallanAppeal.PENDING]
    flagged = Detection.objects.filter(status=Detection.FLAGGED).order_by('-created_at')[:50]
    return render(request, 'dashboard/dig/case_escalation.html', {
        'escalated_appeals': escalated_appeals,
        'pending_appeals': pending_appeals,
        'appeals': appeals,
        'flagged': flagged,
    })


@dig_required
def regional_heatmap(request):
    """Real Leaflet heatmap: camera GPS points + challan density, with city landmarks fallback."""
    import json
    from cameras.models import Camera

    # Known city landmarks → approximate coords used when a camera has no GPS
    CITY_GEO = {
        'gulberg': (31.5204, 74.3587),
        'model town': (31.4833, 74.3261),
        'johar town': (31.4697, 74.2728),
        'dha': (31.4697, 74.4100),
        'cantt': (31.5050, 74.3530),
        'mall road': (31.5590, 74.3260),
        'liberty': (31.5105, 74.3426),
        'township': (31.4500, 74.3000),
        'walton': (31.4820, 74.3550),
        'iqbal town': (31.5100, 74.2800),
        'bahria': (31.3700, 74.2000),
        'thokar': (31.4700, 74.2400),
        'faisal town': (31.4850, 74.3000),
        'garden town': (31.5000, 74.3200),
        'samanabad': (31.5300, 74.3000),
        'shadman': (31.5400, 74.3300),
        'anarkali': (31.5700, 74.3100),
        'lahore': (31.5204, 74.3587),
    }

    def _guess_coords(location_text):
        if not location_text:
            return None
        t = location_text.lower()
        for key, coords in CITY_GEO.items():
            if key in t:
                return coords
        return (31.5204, 74.3587)  # city centre fallback

    # Heat intensity points: [lat, lng, intensity]
    heat_points = []
    camera_markers = []

    cameras = Camera.objects.filter(is_active=True)
    cam_challan_counts = dict(
        Challan.objects.exclude(camera_id=None)
        .values('camera_id')
        .annotate(c=Count('id'))
        .values_list('camera_id', 'c')
    )

    for cam in cameras:
        lat, lng = cam.latitude, cam.longitude
        if lat is None or lng is None:
            guessed = _guess_coords(cam.location)
            if guessed:
                lat, lng = guessed
        if lat is None or lng is None:
            continue
        intensity = max(1, cam_challan_counts.get(cam.id, 0))
        heat_points.append([float(lat), float(lng), float(intensity)])
        camera_markers.append({
            'id': cam.camera_id,
            'location': cam.location or cam.camera_id,
            'lat': float(lat),
            'lng': float(lng),
            'challans': cam_challan_counts.get(cam.id, 0),
            'status': cam.health_status or 'unknown',
        })

    # Also aggregate challans that only have text location (no camera link)
    loc_counts = list(
        Challan.objects.exclude(location__isnull=True).exclude(location='')
        .values('location').annotate(c=Count('id')).order_by('-c')[:40]
    )
    for row in loc_counts:
        coords = _guess_coords(row['location'])
        if coords:
            heat_points.append([coords[0], coords[1], float(row['c'])])

    max_count = max([p[2] for p in heat_points], default=1)
    return render(request, 'dashboard/dig/heatmap.html', {
        'locations': loc_counts,
        'max_count': max_count,
        'heatmap_data_json': json.dumps(heat_points),
        'camera_markers_json': json.dumps(camera_markers),
        'total_points': len(heat_points),
    })

# Alias so portals that still reference dig_views.heatmap keep working
heatmap = regional_heatmap


@role_required('DIG', 'SSP', 'SUPV', 'IT', 'AUDIT')
def officer_kpi(request):
    officers = User.objects.filter(role='OFFICER')
    kpis = []
    for o in officers:
        reviewed = Detection.objects.filter(reviewed_by=o, status__in=[Detection.CONFIRMED, Detection.REJECTED]).count()
        confirmed = Detection.objects.filter(reviewed_by=o, status=Detection.CONFIRMED).count()
        rejected = Detection.objects.filter(reviewed_by=o, status=Detection.REJECTED).count()
        accuracy = (confirmed / reviewed * 100) if reviewed > 0 else 0
        appeals_handled = ChallanAppeal.objects.filter(reviewed_by=o).count()
        kpis.append({
            'officer': o, 'reviewed': reviewed, 'confirmed': confirmed,
            'rejected': rejected, 'accuracy': round(accuracy, 1),
            'appeals': appeals_handled,
        })
    return render(request, 'dashboard/dig/officer_kpi.html', {'kpis': kpis})


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
def alerts_hub(request):
    alerts = Alert.objects.all().order_by('-created_at')[:50]
    banners = Banner.objects.all().order_by('-created_at')[:50]
    broadcasts = AuditLog.objects.filter(action='broadcast.send').order_by('-timestamp')[:50]
    active_tab = request.GET.get('tab', 'alerts')
    return render(request, 'dashboard/dig/alerts_hub.html', {
        'alerts': alerts,
        'banners': banners,
        'broadcasts': broadcasts,
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
    Alert.objects.create(
        title=title, message=message, severity=severity,
        audience=audience, is_active=is_active,
        expires_at=expires_at,
        created_by=request.user,
    )
    AuditLog.write(request, 'alert.create', 'Alert', 0, title=title[:80])
    messages.success(request, f"Alert '{title}' created. Previous active alerts have been deactivated (max 1 active ticker policy).")
    return redirect(_alerts_hub_url('alerts', request))


@role_required('DIG', 'IT')
def alerts_hub_add_banner(request):
    if request.method != 'POST':
        messages.info(request, "Use the form on the Alerts Hub to create a banner.")
        return redirect(_alerts_hub_url('banners', request))
    title = request.POST.get('title', '').strip()
    banner_type = request.POST.get('banner_type', 'image')
    placement = request.POST.get('placement', 'top')
    audience = request.POST.get('audience', 'all')
    if placement in ('ad', 'psa'):
        placement = 'ad'
        audience = 'all'
    bg_color = request.POST.get('bg_color', '#1F4E79')
    text_color = request.POST.get('text_color', '#FFFFFF')
    html_content = request.POST.get('html_content', '').strip()
    image_link = request.POST.get('image_link', '').strip()
    image = request.FILES.get('image')
    expires_at = request.POST.get('expires_at') or None
    is_active = request.POST.get('is_active') == 'on'
    if not title:
        messages.error(request, "Title is required.")
        return redirect(_alerts_hub_url('banners', request))
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
    banner = Banner.objects.create(
        title=title, banner_type=banner_type,
        placement=placement, audience=audience,
        bg_color=bg_color, text_color=text_color,
        html_content=html_content, image_link=image_link,
        is_active=is_active, expires_at=expires_at,
        created_by=request.user,
    )
    if image and banner_type == 'image':
        banner.image = image
        banner.save()
    AuditLog.write(request, 'banner.create', 'Banner', banner.id, title=title[:80])
    messages.success(request, f"Banner '{title}' created.")
    return redirect(_alerts_hub_url('banners', request))


@role_required('DIG', 'IT')
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


@role_required('DIG', 'IT')
def alerts_hub_edit_banner(request, banner_id):
    banner = get_object_or_404(Banner, pk=banner_id)
    if request.method != 'POST':
        messages.info(request, "Use the edit form on the Alerts Hub to update a banner.")
        return redirect(_alerts_hub_url('banners', request))
    banner.title = request.POST.get('title', banner.title).strip()
    banner.html_content = request.POST.get('html_content', banner.html_content)
    if request.FILES.get('image'):
        banner.image = request.FILES['image']
    banner.placement = request.POST.get('placement', banner.placement)
    banner.audience = request.POST.get('audience', banner.audience)
    banner.banner_type = request.POST.get('banner_type', banner.banner_type)
    banner.show_on_home_only = request.POST.get('show_on_home_only') == 'on'
    banner.is_active = request.POST.get('is_active') == 'on'
    banner.save()
    AuditLog.write(request, 'banner.edit', 'Banner', banner.id, title=(banner.title or '')[:80])
    messages.success(request, f"Banner '{banner.title or banner.id}' updated.")
    return redirect(_alerts_hub_url('banners', request))


@role_required('DIG', 'IT')
def alerts_hub_toggle_banner(request, banner_id):
    banner = get_object_or_404(Banner, pk=banner_id)
    banner.is_active = not banner.is_active
    banner.save()
    AuditLog.write(request, 'banner.toggle', 'Banner', banner.id, active=banner.is_active)
    messages.success(request, f"Banner '{banner.title}' {'activated' if banner.is_active else 'deactivated'}.")
    return redirect(_alerts_hub_url('banners', request))


@role_required('DIG', 'IT')
def alerts_hub_delete_banner(request, banner_id):
    banner = get_object_or_404(Banner, pk=banner_id)
    if request.method == 'POST':
        AuditLog.write(request, 'banner.delete', 'Banner', banner.id, title=banner.title)
        banner.delete()
        messages.success(request, "Banner deleted.")
        return redirect(_alerts_hub_url('banners', request))
    return render(request, 'dashboard/dig/alerts_hub_confirm_delete.html', {
        'kind': 'banner',
        'object': banner,
        'cancel_url': _alerts_hub_url('banners', request),
        'confirm_url': reverse(
            f"{getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'dig'}:alerts_hub_delete_banner",
            args=[banner.id],
        ),
    })


@dig_required

@role_required('DIG', 'IT')
def alerts_hub_delete_broadcast(request, log_id):
    """Delete a broadcast log entry (AuditLog action=broadcast.send)."""
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
def admin_toggle(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if target.role == User.DIG and User.objects.filter(role=User.DIG, is_active=True).count() == 1 and target.is_active:
        messages.error(request, "Cannot deactivate the last active DIG account.")
        return redirect(next_url if next_url.startswith('/') else 'dig:admin_list')
    target.is_active = not target.is_active
    target.save()
    AuditLog.write(request, 'admin.toggle', 'User', target.id, active=target.is_active)
    label = 'Citizen' if target.role == User.USER else 'Admin'
    messages.success(request, f"{label} {target.display_name} {'activated' if target.is_active else 'blocked'}.")
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('dig:citizen_users_list' if target.role == User.USER else 'dig:admin_list')


@senior_staff_required
def admin_delete(request, user_id):
    from accounts.models import User
    from .models import AuditLog
    if getattr(request.user, 'role', None) not in ('DIG',) and not getattr(request.user, 'is_dig', False):
        messages.error(request, "Only DIG can delete staff accounts.")
        return redirect('dig:admin_list')
    target = get_object_or_404(User, pk=user_id)
    if target.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('dig:admin_list')
    if target.role == User.DIG and User.objects.filter(role=User.DIG, is_active=True).count() <= 1:
        messages.error(request, "Cannot delete the last DIG account.")
        return redirect('dig:admin_list')
    next_url = request.POST.get('next') or ''
    uid, email, role = target.id, target.email, target.role
    target.delete()
    try:
        AuditLog.write(request, 'admin.delete', 'User', uid, email=email)
    except Exception:
        pass
    messages.success(request, f"Account deleted ({email}).")
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('dig:citizen_users_list' if role == User.USER else 'dig:admin_list')




PAYMENT_METHOD_DEFAULTS = {
    'jazzcash': {
        'label': 'JazzCash', 'enabled': True,
        'merchant_id': '', 'store_id': '', 'password': '',
        'integrity_salt': '', 'hash_key': '',
        'return_url': '', 'environment': 'sandbox',
    },
    'easypaisa': {
        'label': 'EasyPaisa', 'enabled': True,
        'merchant_id': '', 'store_id': '', 'password': '',
        'integrity_salt': '', 'hash_key': '',
        'return_url': '', 'environment': 'sandbox',
    },
    'stripe': {
        'label': 'Stripe (placeholder)', 'enabled': False,
        'publishable_key': '', 'secret_key': '', 'webhook_secret': '',
        'environment': 'test',
    },
    'bank_transfer': {
        'label': 'Bank Transfer', 'enabled': True,
        'bank_name': 'National Bank of Pakistan',
        'account_title': 'Safe City Authority',
        'account_number': '0000000000000000',
        'iban': 'PK36NBPA0000000000000000',
        'branch': 'Main Branch',
    },
}


def _get_payment_settings():
    settings = SystemSettings.get()
    stored = (settings.payment_config or {}) if hasattr(settings, 'payment_config') else {}
    merged = {}
    for key, default in PAYMENT_METHOD_DEFAULTS.items():
        merged[key] = {**default, **stored.get(key, {})}
    return merged


def _save_payment_settings(merged):
    settings = SystemSettings.get()
    if not hasattr(settings, 'payment_config'):
        return False
    settings.payment_config = merged
    settings.save(update_fields=['payment_config'])
    return True


@it_required
def payment_settings(request):
    if request.method == 'POST':
        merged = {}
        for key, default in PAYMENT_METHOD_DEFAULTS.items():
            cfg = dict(default)
            cfg['enabled'] = request.POST.get(f'{key}_enabled') == 'on'
            for field in default.keys():
                if field in ('label', 'enabled'):
                    continue
                val = request.POST.get(f'{key}_{field}')
                if val is not None:
                    cfg[field] = val.strip()
            merged[key] = cfg
        _save_payment_settings(merged)
        AuditLog.write(request, 'payment_settings.update', 'SystemSettings', None,
                       methods=[k for k, v in merged.items() if v.get('enabled')])
        messages.success(request, "Payment settings updated successfully.")
        return redirect('it_support_portal:payment_settings')

    return render(request, 'dashboard/dig/payment_settings.html', {
        'payment_methods': _get_payment_settings(),
    })


@role_required('DIG', 'IT')
def banner_list(request):
    banners = Banner.objects.all().order_by('-priority', '-created_at')
    return render(request, 'dashboard/dig/banner_list.html', {'banners': banners})


@role_required('DIG', 'IT')
def banner_add(request):
    if request.method == 'POST':
        banner = Banner(
            title=request.POST.get('title', '').strip(),
            banner_type=request.POST.get('banner_type', Banner.BANNER_TYPE_IMAGE),
            html_content=request.POST.get('html_content', ''),
            image_link=request.POST.get('image_link', ''),
            placement=request.POST.get('placement', Banner.PLACEMENT_POPUP),
            audience=request.POST.get('audience', Banner.AUDIENCE_ALL),
            bg_color=request.POST.get('bg_color', '#1F4E79'),
            text_color=request.POST.get('text_color', '#FFFFFF'),
            is_active=request.POST.get('is_active') == 'on',
            priority=int(request.POST.get('priority') or 0),
            show_on_home_only=request.POST.get('show_on_home_only') == 'on',
            auto_hide_after_search=request.POST.get('auto_hide_after_search') == 'on',
            created_by=request.user,
        )
        if request.FILES.get('image'):
            banner.image = request.FILES['image']
        for field in ('start_at', 'expires_at'):
            val = request.POST.get(field, '').strip()
            if val:
                try:
                    from datetime import datetime
                    setattr(banner, field, datetime.strptime(val, '%Y-%m-%dT%H:%M'))
                except ValueError:
                    pass
        banner.save()
        AuditLog.write(request, 'banner.create', 'Banner', banner.id, title=banner.title)
        messages.success(request, f"Banner '{banner.title}' created.")
        return redirect('dig:banner_list')
    return render(request, 'dashboard/dig/banner_edit.html', {
        'banner': None, 'is_add': True,
        'placements': Banner.PLACEMENT_CHOICES,
        'audiences': Banner.AUDIENCE_CHOICES,
        'types': Banner.BANNER_TYPE_CHOICES,
    })


@role_required('DIG', 'IT')
def banner_edit(request, banner_id):
    banner = get_object_or_404(Banner, id=banner_id)
    if request.method == 'POST':
        banner.title = request.POST.get('title', '').strip()
        banner.banner_type = request.POST.get('banner_type', Banner.BANNER_TYPE_IMAGE)
        banner.html_content = request.POST.get('html_content', '')
        banner.image_link = request.POST.get('image_link', '')
        banner.placement = request.POST.get('placement', Banner.PLACEMENT_TOP)
        banner.audience = request.POST.get('audience', Banner.AUDIENCE_ALL)
        banner.bg_color = request.POST.get('bg_color', '#1F4E79')
        banner.text_color = request.POST.get('text_color', '#FFFFFF')
        banner.is_active = request.POST.get('is_active') == 'on'
        banner.priority = int(request.POST.get('priority') or 0)
        banner.show_on_home_only = request.POST.get('show_on_home_only') == 'on'
        banner.auto_hide_after_search = request.POST.get('auto_hide_after_search') == 'on'
        if request.FILES.get('image'):
            banner.image = request.FILES['image']
        for field in ('start_at', 'expires_at'):
            val = request.POST.get(field, '').strip()
            if val:
                try:
                    from datetime import datetime
                    setattr(banner, field, datetime.strptime(val, '%Y-%m-%dT%H:%M'))
                except ValueError:
                    pass
            else:
                setattr(banner, field, None)
        banner.save()
        AuditLog.write(request, 'banner.update', 'Banner', banner.id, title=banner.title)
        messages.success(request, f"Banner '{banner.title}' updated.")
        return redirect('dig:banner_list')
    return render(request, 'dashboard/dig/banner_edit.html', {
        'banner': banner, 'is_add': False,
        'placements': Banner.PLACEMENT_CHOICES,
        'audiences': Banner.AUDIENCE_CHOICES,
        'types': Banner.BANNER_TYPE_CHOICES,
    })


@role_required('DIG', 'IT')
def banner_delete(request, banner_id):
    banner = get_object_or_404(Banner, id=banner_id)
    if request.method == 'POST':
        title = banner.title
        banner.delete()
        AuditLog.write(request, 'banner.delete', 'Banner', banner_id, title=title)
        messages.success(request, f"Banner '{title}' deleted.")
    return redirect('dig:banner_list')


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


@any_permission_required('camera_feed', 'view_cameras')
def camera_stream_url(request, camera_id):
    """Get the best available stream URL for a camera (HTTP snapshot or RTSP)."""
    camera = get_object_or_404(Camera, pk=camera_id)
    if request.user.role == 'OFFICER':
        from realtime.models import CameraAssignment
        if not CameraAssignment.objects.filter(camera=camera, officer=request.user, is_active=True).exists():
            raise Http404

    if camera.http_snapshot_url:
        return JsonResponse({'stream_url': camera.http_snapshot_url, 'type': 'http_snapshot'})

    if camera.rtsp_url:
        return JsonResponse({'stream_url': camera.rtsp_url, 'type': 'rtsp'})

    latest = Detection.objects.filter(camera=camera).order_by('-created_at').first()
    if latest and latest.raw_image:
        return JsonResponse({'stream_url': latest.raw_image.url, 'type': 'detection_snapshot'})

    return JsonResponse({'stream_url': None, 'type': 'none'}, status=404)



@it_required
def challan_template_designer(request):
    """Visual A4 block designer — outputs Django HTML template for PDF."""
    from admin.dig_portal.models import ChallanTemplate
    from admin.dig_portal.models import SystemSettings
    if request.method == 'POST':
        name = (request.POST.get('template_name') or 'Custom A4').strip()
        html = request.POST.get('html_content') or ''
        if len(html) < 50:
            messages.error(request, "Template HTML is too short.")
            return redirect('it_support_portal:challan_template_designer')
        kwargs = {'name': name, 'html_content': html}
        # optional fields
        for fld, val in [('is_active', False), ('uploaded_by', request.user if request.user.is_authenticated else None)]:
            if any(f.name == fld for f in ChallanTemplate._meta.get_fields()):
                kwargs[fld] = val
        try:
            obj = ChallanTemplate.objects.create(**kwargs)
        except TypeError:
            obj = ChallanTemplate.objects.create(name=name, html_content=html)

        if request.POST.get('activate') == '1':
            ChallanTemplate.objects.exclude(pk=obj.pk).update(is_active=False)
            obj.is_active = True
            obj.save(update_fields=['is_active'])
            sys_settings = SystemSettings.get()
            sys_settings.pdf_template = f'db:{obj.id}'
            sys_settings.save(update_fields=['pdf_template'])
        messages.success(request, f"Template '{name}' saved.")
        return redirect('it_support_portal:challan_templates')
    blocks = [
        {'id': 'header', 'label': 'Header (Gov + logos)', 'icon': 'fa-heading'},
        {'id': 'ticket_meta', 'label': 'Ticket / Plate / Status', 'icon': 'fa-barcode'},
        {'id': 'offender', 'label': 'Offender block', 'icon': 'fa-user'},
        {'id': 'vehicle', 'label': 'Vehicle block', 'icon': 'fa-car'},
        {'id': 'evidence', 'label': 'Evidence image', 'icon': 'fa-image'},
        {'id': 'psid', 'label': 'PSID payment box', 'icon': 'fa-qrcode'},
        {'id': 'instructions', 'label': 'Legal instructions', 'icon': 'fa-scale-balanced'},
        {'id': 'slips', 'label': 'Motorist + Bank slips', 'icon': 'fa-copy'},
        {'id': 'footer', 'label': 'Footer', 'icon': 'fa-minus'},
    ]
    return render(request, 'dashboard/it_support/challan_designer.html', {
        'blocks': blocks,
        # The designer JS presets interpolate {{ challan.* }} sample values;
        # without this context variable the template engine raises
        # VariableDoesNotExist while rendering the page.
        'challan': None,
    })


@permission_required('live_tracking')  # H11 FIX: was @role_required('IT','OFFICER') — use permission matrix instead
def live_tracking(request):
    """Shared Live Tracking page for staff portals.

    permission.json grants `live_tracking` to OFFICER + IT Support only —
    DIG/SSP/Supervisor/Audit are intentionally excluded.
    """
    from admin.shared import LiveTrackingService
    from detections.models import Detection
    from django.db.models import Q

    cam_id = request.GET.get('camera_id') or request.GET.get('camera') or ''
    service = LiveTrackingService(
        user=request.user,
        selected_camera_id=cam_id or None,
        plate_query=request.GET.get('plate') or '',
        status_filter=request.GET.get('status') or '',
        limit=80,
    )
    cameras = service.get_available_cameras()
    if not service.selected_camera_id and cameras:
        service.selected_camera_id = str(cameras[0].id)
    recent = service.get_recent_detections()
    latest_detection = recent[0] if recent else None
    stats = service.get_stats(recent)
    return render(request, 'dashboard/shared/live_tracking.html', {
        'cameras': cameras,
        'has_assignment': bool(cameras),
        'selected_camera': service.camera,
        'stream_url': service.resolve_stream_url(),
        'selected_camera_id': service.selected_camera_id or '',
        'camera_not_found': service.camera_not_found,
        'plate_q': service.plate_query,
        'status_q': service.status_filter,
        'recent_detections': recent,
        'latest_detection': latest_detection,
        'live_feeds': [],
        'stat_total': stats['total'],
        'stat_violations': stats['violations'],
        'stat_pending': stats['pending'],
        'stat_unique_plates': stats['unique_plates'],
        'stat_avg_conf': stats['avg_confidence'],
        'status_choices': getattr(Detection, 'STATUS_CHOICES', ()),
    })


@it_required
def camera_test(request, camera_id):
    """IT-only camera diagnostics: verify the configured stream is reachable,
    decodable, and return latency + a snapshot preview (JSON)."""
    import time
    import base64

    cam = get_object_or_404(Camera, pk=camera_id)
    url = (cam.http_snapshot_url or cam.rtsp_url or '').strip()
    if not url:
        return JsonResponse({'ok': False, 'error': 'No stream URL configured for this camera. Edit the camera and set an RTSP or HTTP snapshot URL (or upload a video).'})

    started = time.time()

    def _with_snapshot(payload, frame):
        try:
            import cv2
            h, w = frame.shape[:2]
            small = cv2.resize(frame, (320, max(1, int(320 * h / max(1, w)))))
            ok_enc, buf = cv2.imencode('.jpg', small)
            if ok_enc:
                payload['snapshot'] = 'data:image/jpeg;base64,' + base64.b64encode(buf).decode()
        except Exception:
            pass
        return payload

    if url.lower().startswith('http'):
        try:
            import requests as _rq
            resp = _rq.get(url, timeout=8)
            latency = int((time.time() - started) * 1000)
            if resp.status_code != 200:
                return JsonResponse({'ok': False, 'kind': 'http', 'latency_ms': latency,
                                     'error': f'HTTP {resp.status_code} from stream URL.'})
            try:
                import cv2
                import numpy as np
                arr = np.frombuffer(resp.content, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            except Exception:
                frame = None
            if frame is None:
                return JsonResponse({'ok': False, 'kind': 'http', 'latency_ms': latency,
                                     'error': 'Endpoint reachable but the response is not a decodable image. Use a snapshot JPEG URL.'})
            return JsonResponse(_with_snapshot({
                'ok': True, 'kind': 'http', 'latency_ms': latency,
                'message': f'Snapshot OK — {frame.shape[1]}x{frame.shape[0]}',
            }, frame))
        except Exception as e:
            return JsonResponse({'ok': False, 'kind': 'http', 'error': f'Request failed: {e}'})

    # RTSP — bounded open + single frame grab
    try:
        import cv2
        import os as _os
        _os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        opened = cap.isOpened()
        frame = None
        if opened:
            ok_f, frame = cap.read()
            if not ok_f:
                frame = None
        cap.release()
        latency = int((time.time() - started) * 1000)
        if frame is not None:
            return JsonResponse(_with_snapshot({
                'ok': True, 'kind': 'rtsp', 'latency_ms': latency,
                'message': f'RTSP stream OK — {frame.shape[1]}x{frame.shape[0]}',
            }, frame))
        return JsonResponse({
            'ok': False, 'kind': 'rtsp', 'latency_ms': latency,
            'error': 'Could not open RTSP stream. Check the URL, credentials and network reachability.',
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'kind': 'rtsp', 'error': f'RTSP test failed: {e}'})


# ---------------------------------------------------------------------------
# JSON API endpoints for dashboard charts/tables
# These are consumed by safe-city-charts.js / safe-city-tables.js via fetch().
# All return CSRF-safe JSON via JsonResponse.
# ---------------------------------------------------------------------------

@dig_required
@require_GET
def api_dashboard_kpis(request):
    """Role-aware KPI bundle for the DIG dashboard."""
    from datetime import timedelta
    today = timezone.localdate()
    week_start = today - timedelta(days=7)
    month_start = today - timedelta(days=30)
    return JsonResponse({
        'ts': int(timezone.now().timestamp()),
        'kpis': {
            'total_today': Challan.objects.filter(issue_date=today).count(),
            'total_week': Challan.objects.filter(issue_date__gte=week_start).count(),
            'total_month': Challan.objects.filter(issue_date__gte=month_start).count(),
            'paid_today': Challan.objects.filter(issue_date=today, payment_status=Challan.PAID).count(),
            'paid_month': Challan.objects.filter(issue_date__gte=month_start, payment_status=Challan.PAID).count(),
            'revenue_collected': float(
                Challan.objects.filter(payment_status=Challan.PAID)
                .aggregate(t=Sum('fine_amount'))['t'] or 0
            ),
            'revenue_today': float(
                Challan.objects.filter(issue_date=today, payment_status=Challan.PAID)
                .aggregate(t=Sum('fine_amount'))['t'] or 0
            ),
            'revenue_pending': float(
                Challan.objects.filter(payment_status=Challan.UNPAID)
                .aggregate(t=Sum('fine_amount'))['t'] or 0
            ),
            'active_cameras': Camera.objects.filter(is_active=True, is_streaming=True).count(),
            'online_cameras': Camera.objects.filter(health_status='online').count(),
            'total_cameras': Camera.objects.filter(is_active=True).count(),
            'pending_detections': Detection.objects.filter(status=Detection.PENDING).count(),
            'flagged_detections': Detection.objects.filter(status=Detection.FLAGGED).count(),
            'pending_appeals': ChallanAppeal.objects.filter(status=ChallanAppeal.PENDING).count(),
            'escalated_appeals': ChallanAppeal.objects.filter(status=ChallanAppeal.ESCALATED).count(),
            'total_users': User.objects.filter(role=User.USER).count(),
            'total_officers': User.objects.filter(role=User.OFFICER).count(),
            'active_alerts': Alert.objects.filter(is_active=True)
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).count(),
        },
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
@require_GET
def api_chart_violation_distribution(request):
    """Chart.js-friendly data: viol type → count over the last N days (default 30)."""
    try:
        days = max(1, min(180, int(request.GET.get('days', 30))))
    except (TypeError, ValueError):
        days = 30
    since = timezone.now() - datetime.timedelta(days=days)
    rows = (
        Challan.objects.filter(issue_date__gte=since.date())
        .values('violation_type')
        .annotate(c=Count('id'))
        .order_by('-c')
    )
    labels = [r['violation_type'] or 'Unknown' for r in rows]
    counts = [r['c'] for r in rows]
    return JsonResponse({
        'labels': labels,
        'datasets': [{
            'label': 'Violations',
            'data': counts,
            'backgroundColor': '#0a1a3a',
            'borderColor': '#0a1a3a',
        }],
        'meta': {'days': days, 'total': sum(counts)},
    })


@dig_required
@permission_required('view_analytics')
@require_GET
def api_chart_location_distribution(request):
    """Top-10 violation hotspots as a horizontal-bar dataset."""
    rows = (
        Challan.objects.exclude(location__isnull=True).exclude(location='')
        .values('location').annotate(c=Count('id')).order_by('-c')[:10]
    )
    return JsonResponse({
        'labels': [r['location'] for r in rows],
        'datasets': [{
            'label': 'Challans',
            'data': [r['c'] for r in rows],
            'backgroundColor': '#dc2626',
        }],
    })


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT', 'IT')
@require_GET
def api_chart_activity_trend(request):
    """7-day activity trend (detections vs challans) for the area chart."""
    from datetime import timedelta
    rows = []
    for d in range(6, -1, -1):
        day = timezone.now() - timedelta(days=d)
        ds = day.replace(hour=0, minute=0, second=0, microsecond=0)
        de = ds + timedelta(days=1)
        rows.append({
            'date': ds.strftime('%b %d'),
            'detections': Detection.objects.filter(created_at__gte=ds, created_at__lt=de).count(),
            'challans': Challan.objects.filter(created_at__gte=ds, created_at__lt=de).count(),
        })
    return JsonResponse({
        'labels': [r['date'] for r in rows],
        'datasets': [
            {'label': 'Detections', 'data': [r['detections'] for r in rows], 'borderColor': '#0a1a3a', 'backgroundColor': 'rgba(10,26,58,0.15)', 'tension': 0.3, 'fill': True},
            {'label': 'Challans',   'data': [r['challans']   for r in rows], 'borderColor': '#dc2626', 'backgroundColor': 'rgba(220,38,38,0.15)', 'tension': 0.3, 'fill': True},
        ],
    })


@dig_required
@permission_required('view_detections')
@require_GET
def api_table_recent_detections(request):
    """DataTables server-side endpoint for recent detections."""
    try:
        draw   = int(request.GET.get('draw', 1))
        start  = int(request.GET.get('start', 0))
        length = max(1, min(200, int(request.GET.get('length', 25))))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid DataTables params'}, status=400)

    qs = Detection.objects.select_related('camera').order_by('-created_at')
    total = qs.count()
    qs = qs[start:start + length]
    data = [{
        'id':         d.id,
        'camera':     d.camera.camera_id if d.camera else (f'#{d.camera_id}' if d.camera_id else '—'),
        'plate':      d.effective_plate or '—',
        'confidence': round(float(d.ai_confidence or 0) * 100, 1),
        'status':     d.get_status_display(),
        'created_at': d.created_at.strftime('%Y-%m-%d %H:%M'),
    } for d in qs]
    return JsonResponse({
        'draw':            draw,
        'recordsTotal':    total,
        'recordsFiltered': total,
        'data':            data,
    })


@dig_required
@require_GET
def api_chart_officer_kpi(request):
    """Per-officer accuracy/confirmation count, for the bar chart on the dashboard."""
    rows = (
        Detection.objects.filter(reviewed_by__isnull=False)
        .values('reviewed_by__username')
        .annotate(
            confirmed=Count('id', filter=Q(status=Detection.CONFIRMED)),
            rejected=Count('id', filter=Q(status=Detection.REJECTED)),
        )
        .order_by('-confirmed')[:10]
    )
    labels = [r['reviewed_by__username'] or 'Officer' for r in rows]
    return JsonResponse({
        'labels': labels,
        'datasets': [
            {'label': 'Confirmed', 'data': [r['confirmed'] for r in rows], 'backgroundColor': '#16a34a'},
            {'label': 'Rejected',  'data': [r['rejected']  for r in rows], 'backgroundColor': '#dc2626'},
        ],
    })


# =============================================================================
# Admin Password Reset (DIG-mediated flow)
# =============================================================================

def _client_ip(request):
    """Extract client IP, honouring X-Forwarded-For."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@dig_required
def admin_reset_request_list(request):
    """List all pending admin password reset requests — DIG only."""
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
    """Form for DIG to set a new password on behalf of an admin."""
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

            # Log audit trail
            AuditLog.write(request, 'admin.password_reset', 'User', target.id)

            req.status = AdminPasswordResetRequest.STATUS_RESOLVED
            req.resolved_at = timezone.now()
            req.resolved_by = request.user
            req.save(update_fields=['status', 'resolved_at', 'resolved_by'])

            # Mark related notifications as read
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
