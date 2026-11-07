from django.contrib import messages
from django.utils import timezone
from django.conf import settings as dj_settings
from pathlib import Path

from cameras.models import Camera
from challans.models import Challan
from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from detections.models import Detection
from accounts.models import User
from accounts.decorators import it_required
from django.shortcuts import redirect
from django.shortcuts import render
from accounts.decorators import staff_required


@it_required
def settings_edit(request):
    if getattr(request.user, 'role', '') == 'DIG':
        from django.contrib import messages as _m
        _m.info(request, 'Administrative form selection is managed under Staff workflows. System configuration is handled by IT Support.')
        return redirect('dig:dashboard')

    from ..models import ChallanTemplate
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
        'account_title': 'Safe Cities Project',
        'account_number': '0000000000000000',
        'iban': 'PK36NBPA0000000000000000',
        'branch': 'Main Branch',
    },
}


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

