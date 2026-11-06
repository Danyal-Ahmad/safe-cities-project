from django.contrib import messages
from django.utils import timezone
from django.conf import settings as dj_settings

from challans.models import Challan
from ..models import SystemSettings, AuditLog, Alert, Banner, Notification, BlacklistEntry
from django.db.models import Count
from detections.models import Detection
from django.db.models import Q
from accounts.decorators import dig_required
from django.shortcuts import get_object_or_404
from accounts.decorators import it_required
from django.shortcuts import redirect
from django.shortcuts import render
from accounts.decorators import role_required
from accounts.decorators import senior_staff_required


@role_required('DIG', 'SSP', 'SUPV', 'AUDIT')
def challan_list(request):
    qs = Challan.objects.all().order_by('-issue_date')
    plate_filter = request.GET.get('plate')
    if plate_filter: qs = qs.filter(plate_number__icontains=plate_filter)
    status_filter = request.GET.get('status')
    if status_filter: qs = qs.filter(payment_status=status_filter)
    search = (request.GET.get('search') or '').strip()
    if search:
        qs = qs.filter(Q(location__icontains=search) | Q(plate_number__icontains=search) | Q(ticket_no__icontains=search))
    return render(request, 'dashboard/dig/challan_list.html', {
        'challans': qs[:200], 'total': qs.count(),
        'plate_filter': plate_filter, 'status_filter': status_filter, 'search': search,
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
def challan_confirm_delete(request, challan_id):
    challan = get_object_or_404(Challan, pk=challan_id)
    if request.method == 'POST':
        AuditLog.write(request, 'challan.delete', 'Challan', challan.id, ticket=challan.ticket_no)
        challan.delete()
        messages.success(request, f"Challan {challan.ticket_no} deleted.")
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
def payment_list(request):
    payments = Challan.objects.filter(payment_status=Challan.PAID).order_by('-paid_at')[:200]
    return render(request, 'dashboard/dig/payment_list.html', {'payments': payments})


@role_required('DIG', 'IT', 'SSP')
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


@senior_staff_required
def vehicle_search(request):
    import re
    raw = (request.GET.get('q') or '').strip()
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
def violation_stats(request):
    by_type_qs = (Challan.objects.values('violation_type')
                  .annotate(c=Count('id')).order_by('-c'))
    by_type_display = {dict(Challan.VIOLATION_CHOICES).get(row['violation_type'], row['violation_type']): row['c']
                       for row in by_type_qs}

    by_location_qs = (Challan.objects.exclude(location__isnull=True).exclude(location='')
                      .values('location').annotate(c=Count('id'))
                      .order_by('-c')[:15])
    by_location = {row['location'] or 'Unknown': row['c'] for row in by_location_qs}
    unknown_count = Challan.objects.filter(Q(location__isnull=True) | Q(location='')).count()
    if unknown_count:
        by_location.setdefault('Unknown', unknown_count)

    type_max = max(by_type_display.values()) if by_type_display else 0
    loc_max = max(by_location.values()) if by_location else 0
    type_rows = [{'label': label, 'count': count,
                  'pct': round(count / type_max * 100) if type_max else 0}
                 for label, count in by_type_display.items()]
    loc_rows = [{'label': label, 'count': count,
                 'pct': round(count / loc_max * 100) if loc_max else 0}
                for label, count in by_location.items()]
    return render(request, 'dashboard/dig/violation_stats.html', {
        'type_rows': type_rows, 'loc_rows': loc_rows,
        'type_max': type_max, 'loc_max': loc_max,
        'by_type': by_type_display, 'by_location': by_location,
    })


def run_auto_blacklist(plate, request=None):
    if not plate:
        return False
    from ..models import SystemSettings, AuditLog as AL
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
            'actor': (e.created_by.display_name if e.created_by else '-'),
            'when': e.created_at.strftime('%d %b %Y %H:%M') if e.created_at else '-',
            'created_at': e.created_at,
            'created_by': e.created_by,
        })
    if not rows:
        entries = AuditLog.objects.filter(action='blacklist.add').order_by('-timestamp')[:200]
        for e in entries:
            details = e.details if isinstance(e.details, dict) else {}
            plate_val = details.get('plate') or '-'
            rows.append({
                'plate': plate_val,
                'value': plate_val,
                'type': details.get('type') or 'plate',
                'reason': details.get('reason') or e.action,
                'is_active': True,
                'actor': (e.actor.display_name if e.actor else '-'),
                'when': e.timestamp.strftime('%d %b %Y %H:%M') if e.timestamp else '-',
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
            value_for_lookup = value
        elif btype == 'cnic':
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


@it_required
def challan_templates_manage(request):
    from ..models import ChallanTemplate
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
                sys_settings.pdf_template = 'standard_a4'
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


    templates = list(ChallanTemplate.objects.all().order_by('-created_at')[:50])
    for obj in templates:
        obj.preview_html = (obj.html_content or '')[:4000]
    any_custom_active = any(getattr(t, 'is_active', False) for t in templates)

    from challans.pdf_service import TEMPLATE_MAP
    active_key = sys_settings.pdf_template or 'modern_a4'
    if active_key not in TEMPLATE_MAP and not active_key.startswith('db:'):
        active_key = 'modern_a4'
        sys_settings.pdf_template = active_key
        sys_settings.save(update_fields=['pdf_template'])

    from django.conf import settings as dj_settings
    from pathlib import Path
    file_templates = []
    fs_dir = Path(dj_settings.BASE_DIR) / 'templates' / 'challan' / 'challan_templates'
    if fs_dir.is_dir():
        for key in TEMPLATE_MAP:
            fp = fs_dir / f'{key}.html'
            if not fp.is_file():
                continue
            try:
                raw_html = fp.read_text(encoding='utf-8', errors='ignore')
            except OSError:
                raw_html = ''
            file_templates.append({
                'key': key,
                'name': {
                    'modern_a4': 'Modern A4 | Official Safe City E-Challan',
                    'classic_a4': 'Classic A4 | Government-Style Form',
                    'legal_notice_99a': 'Legal Notice 99-A | Motor Vehicles Ordinance 1965',
                    'digital_slip': 'Digital Slip | Modern Compact E-Challan',
                    'command_brief': 'Command Brief | Executive Enforcement Layout',
                    'secure_instrument': 'Secure Instrument | Bank-Grade Counterfoil',
                    'urdu_executive': 'Urdu Executive | Nastaliq RTL Layout',
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


@it_required
def challan_template_designer(request):
    from admin.dig_portal.models import ChallanTemplate
    from admin.dig_portal.models import SystemSettings
    if request.method == 'POST':
        name = (request.POST.get('template_name') or 'Custom A4').strip()
        html = request.POST.get('html_content') or ''
        if len(html) < 50:
            messages.error(request, "Template HTML is too short.")
            return redirect('it_support_portal:challan_template_designer')
        kwargs = {'name': name, 'html_content': html}
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
        'challan': None,
    })


@role_required('DIG')
def challan_template_select(request):
    from ..models import ChallanTemplate
    from challans.pdf_service import TEMPLATE_MAP
    import pathlib
    from django.conf import settings as dj_settings
    from django.template import Context, Template

    sys_settings = SystemSettings.get()
    active_key = sys_settings.pdf_template or 'modern_a4'

    if request.method == 'POST':
        action = request.POST.get('action') or ''
        if action == 'set_active':
            tid = (request.POST.get('template_key') or '').strip()
            if tid.startswith('db:'):
                obj = ChallanTemplate.objects.filter(pk=tid[3:]).first()
                if obj:
                    ChallanTemplate.objects.exclude(pk=obj.pk).update(is_active=False)
                    obj.is_active = True
                    obj.save()
                    sys_settings.pdf_template = f'db:{obj.id}'
                    sys_settings.save(update_fields=['pdf_template'])
                    AuditLog.write(request, 'challan_template.select', 'ChallanTemplate', obj.id, name=obj.name)
                    messages.success(request, f"Active challan template set to '{obj.name}'.")
            elif tid in TEMPLATE_MAP:
                ChallanTemplate.objects.update(is_active=False)
                sys_settings.pdf_template = tid
                sys_settings.save(update_fields=['pdf_template'])
                AuditLog.write(request, 'challan_template.select_file', 'ChallanTemplateFile', 0, key=tid)
                messages.success(request, f"Active challan template set to '{tid}'.")
            else:
                messages.error(request, "Unknown template.")
            return redirect('dig:challan_template_select')

    def _sample_context():
        import datetime as _dt
        return {
            'challan': type('SampleChallan', (), {
                'ticket_no': '202600001', 'plate_number': 'LEA-1234', 'province': 'LEA',
                'owner_name': 'Sample Owner', 'cnic': '35202-1234567-1',
                'address': 'Sample Address', 'phone': '0300-1234567',
                'vehicle_type': 'Car', 'make_year': '2022', 'color': 'White',
                'violation_type': 'wrong_way', 'fine_amount': 500,
                'location': 'Main Boulevard', 'ai_confidence': 0.93,
                'legal_direction': 'north', 'moving_direction': 'south',
                'issue_date': _dt.date.today(), 'due_date': _dt.date.today() + _dt.timedelta(days=10),
                'payment_status': 'UNPAID', 'is_overdue': False, 'psid': '0002026000014',
                'camera': None, 'detection': None, 'locale': 'en',
            })(),
            'evidence_summary': {'checks': [{'check': c, 'passed': True} for c in
                                ('plate_readability', 'frame_consistency', 'violation_logic',
                                 'image_evidence', 'chain_integrity')],
                                'passed': 5, 'total': 5, 'all_passed': True, 'hash': 'ab12cd34' * 8,
                                'track_id': 'TRK-1-LEA-0001', 'track_frames': 3, 'track_consistency': 1.0},
            'payment_icons': [], 'barcode_svg': None, 'qr_svg': None,
            'logo_left_path': str(dj_settings.BASE_DIR / 'static' / 'img' / 'project_logo.png'),
            'logo_right_path': str(dj_settings.BASE_DIR / 'static' / 'img' / 'university_logo.png'),
            'needs_nadra_excise': False,
        }

    TEMPLATE_META = {
        'modern_a4': ('Modern A4 | Official E-Challan', 'Modern layout with KPI band, evidence frame and PSID strip'),
        'classic_a4': ('Classic A4 | Government-Style Form', 'Bordered bureaucratic form with sections A to D'),
        'legal_notice_99a': ('Legal Notice 99-A', 'Serif legal notice under Section 99-A, Motor Vehicles Ordinance 1965'),
        'digital_slip': ('Digital Slip', 'Dark digital challan slip with barcode strip'),
        'command_brief': ('Command Brief', 'Executive enforcement layout with direction analysis and hero fine block'),
        'secure_instrument': ('Secure Instrument', 'Bank-grade secure print with tear-off payment counterfoil'),
        'urdu_executive': ('Urdu Executive | Urdu-Primary', 'Nastaliq right-to-left executive layout with English captions'),
    }
    sample_ctx = Context(_sample_context())
    layouts = []
    fs_dir = pathlib.Path(dj_settings.BASE_DIR) / 'templates' / 'challan' / 'challan_templates'
    for key in TEMPLATE_MAP:
        fp = fs_dir / f'{key}.html'
        if not fp.is_file():
            continue
        try:
            preview = Template(fp.read_text(encoding='utf-8', errors='ignore')).render(sample_ctx)
        except Exception:
            preview = ''
        name, blurb = TEMPLATE_META.get(key, (key, ''))
        layouts.append({'key': key, 'name': name, 'blurb': blurb,
                        'is_active': (key == active_key), 'preview_html': preview})
    for t in ChallanTemplate.objects.order_by('-created_at'):
        try:
            preview = Template(t.html_content or '').render(sample_ctx) if t.html_content else ''
        except Exception:
            preview = ''
        layouts.append({'key': f'db:{t.id}', 'name': t.name,
                        'blurb': 'Studio design by IT Support', 'is_active': (active_key == f'db:{t.id}'),
                        'preview_html': preview})
    return render(request, 'dashboard/dig/challan_template_select.html', {
        'layouts': layouts,
        'active_key': active_key,
    })
