from django.contrib import messages
from django.conf import settings as dj_settings

from accounts.models import User, OfficerProfile
from detections.models import Detection, DetectionReviewNote
from appeals.models import ChallanAppeal
from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from accounts.decorators import _safe_redirect
from accounts.decorators import any_permission_required
from accounts.decorators import dig_required
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from accounts.decorators import role_required
from accounts.decorators import senior_staff_required


@dig_required
def penalty_config(request):
    from ..models import SystemSettings
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
    from ..models import Shift
    officers = User.objects.filter(role=User.OFFICER).order_by('first_name')
    shifts = Shift.objects.select_related('officer').order_by('-start_time')[:100]
    return render(request, 'dashboard/dig/shift_management.html', {
        'officers': officers,
        'shifts': shifts,
    })


@role_required('DIG', 'SSP', 'SUPV')
def shift_add(request):
    from ..models import Shift
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


@role_required('DIG', 'SSP', 'SUPV')
def officer_activity(request, officer_id=None):
    if not officer_id:
        officer = (
            User.objects.filter(role=User.OFFICER, is_active=True)
            .order_by('-last_login')
            .first()
        )
        if officer is None:
            messages.info(request, "No active officers to report on yet.")
            return _safe_redirect(request)
        ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'dig'
        return redirect(f'{ns}:officer_activity', officer.pk)
    officer = get_object_or_404(User, pk=officer_id, role=User.OFFICER)
    recent_actions = Detection.objects.filter(reviewed_by=officer).order_by('-reviewed_at')[:20]
    appeals_handled = ChallanAppeal.objects.filter(reviewed_by=officer).order_by('-reviewed_at')[:20]
    notes_added = DetectionReviewNote.objects.filter(author=officer).order_by('-created_at')[:20]
    stats = {
        'total_reviewed': Detection.objects.filter(reviewed_by=officer).count(),
        'total_appeals': ChallanAppeal.objects.filter(reviewed_by=officer).count(),
        'total_notes': DetectionReviewNote.objects.filter(author=officer).count(),
    }
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None) or 'dig'
    return render(request, 'dashboard/dig/officer_activity.html', {
        'officer': officer, 'recent_actions': recent_actions,
        'appeals_handled': appeals_handled, 'notes_added': notes_added,
        'stats': stats, 'portal_ns': ns,
    })


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


@any_permission_required('officer_pki', 'officer_profile_manage')
def officer_signatures(request):
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
