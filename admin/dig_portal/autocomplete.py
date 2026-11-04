import re
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from accounts.models import User, VehicleRegistration
from challans.models import Challan
from cameras.models import Camera


CNIC_RE = re.compile(r'^\d{5}-\d{7}-\d$')
PHONE_RE = re.compile(r'^(\+92|0)?3\d{2}[-\s]?\d{7}$')
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
PLATE_RE = re.compile(r'^[A-Z]{2,3}-?\d{1,4}$', re.IGNORECASE)


def _validate(field_type, value):
    if not value:
        return 'invalid'
    if field_type == 'cnic':
        return 'valid' if CNIC_RE.match(value) else 'invalid'
    if field_type == 'phone':
        return 'valid' if PHONE_RE.match(value) else 'invalid'
    if field_type == 'email':
        return 'valid' if EMAIL_RE.match(value) else 'invalid'
    if field_type == 'plate':
        return 'valid' if PLATE_RE.match(value) else 'invalid'
    return 'valid'


def _status_for(field_type, value, exists_count):
    validity = _validate(field_type, value)
    if validity == 'invalid':
        return 'invalid'
    if exists_count > 1:
        return 'duplicate'
    if exists_count == 1:
        return 'existing'
    return 'new'


def _search_cnic(q):
    results = []
    users = User.objects.filter(cnic__icontains=q).select_related('officer_profile')[:8]
    for u in users:
        exists_count = User.objects.filter(cnic=u.cnic).count() + Challan.objects.filter(cnic=u.cnic).count()
        results.append({
            'value': u.cnic,
            'label': u.cnic,
            'sub': f"{u.display_name} · {u.get_role_display()}",
            'status': _status_for('cnic', u.cnic, exists_count),
            'icon': '<i class="fa-solid fa-id-card"></i>',
            'fill': {
                'id_owner_name': u.display_name,
                'id_phone': u.phone or '',
                'id_email': u.email or '',
            }
        })
    challans = Challan.objects.filter(cnic__icontains=q).exclude(cnic='').values('cnic', 'owner_name', 'phone').distinct()[:8]
    for c in challans:
        if any(r['value'] == c['cnic'] for r in results):
            continue
        exists_count = Challan.objects.filter(cnic=c['cnic']).count()
        results.append({
            'value': c['cnic'],
            'label': c['cnic'],
            'sub': f"{c.get('owner_name') or 'Unknown'} · from challan records",
            'status': _status_for('cnic', c['cnic'], exists_count),
            'icon': '<i class="fa-solid fa-file-invoice"></i>',
            'fill': {
                'id_owner_name': c.get('owner_name') or '',
                'id_phone': c.get('phone') or '',
            }
        })
    return results


def _search_phone(q):
    results = []
    users = User.objects.filter(phone__icontains=q)[:8]
    for u in users:
        exists_count = User.objects.filter(phone=u.phone).count() + Challan.objects.filter(phone=u.phone).count()
        results.append({
            'value': u.phone,
            'label': u.phone,
            'sub': f"{u.display_name} · {u.get_role_display()}",
            'status': _status_for('phone', u.phone, exists_count),
            'icon': '<i class="fa-solid fa-phone"></i>',
            'fill': {
                'id_owner_name': u.display_name,
                'id_email': u.email or '',
                'id_cnic': u.cnic or '',
            }
        })
    challans = Challan.objects.filter(phone__icontains=q).exclude(phone='').values('phone', 'owner_name', 'cnic').distinct()[:8]
    for c in challans:
        if any(r['value'] == c['phone'] for r in results):
            continue
        exists_count = Challan.objects.filter(phone=c['phone']).count()
        results.append({
            'value': c['phone'],
            'label': c['phone'],
            'sub': f"{c.get('owner_name') or 'Unknown'} · from challan records",
            'status': _status_for('phone', c['phone'], exists_count),
            'icon': '<i class="fa-solid fa-file-invoice"></i>',
            'fill': {
                'id_owner_name': c.get('owner_name') or '',
                'id_cnic': c.get('cnic') or '',
            }
        })
    return results


def _search_email(q):
    results = []
    users = User.objects.filter(email__icontains=q)[:8]
    for u in users:
        exists_count = User.objects.filter(email=u.email).count()
        results.append({
            'value': u.email,
            'label': u.email,
            'sub': f"{u.display_name} · {u.get_role_display()}",
            'status': _status_for('email', u.email, exists_count),
            'icon': '<i class="fa-solid fa-envelope"></i>',
            'fill': {
                'id_owner_name': u.display_name,
                'id_phone': u.phone or '',
            }
        })
    return results


def _search_plate(q):
    results = []
    vehicles = VehicleRegistration.objects.filter(plate_number__icontains=q).select_related('owner')[:8]
    for v in vehicles:
        exists_count = Challan.objects.filter(plate_number__iexact=v.plate_number).count()
        results.append({
            'value': v.plate_number,
            'label': v.plate_number,
            'sub': f"{v.owner.display_name} · {v.make or v.vehicle_type}",
            'status': _status_for('plate', v.plate_number, exists_count),
            'icon': '<i class="fa-solid fa-car-side"></i>',
            'fill': {
                'id_owner_name': v.owner.display_name,
                'id_cnic': v.owner.cnic or '',
                'id_phone': v.owner.phone or '',
                'id_vehicle_type': v.vehicle_type or '',
                'id_make_year': v.year or '',
                'id_color': v.color or '',
            }
        })
    challans = Challan.objects.filter(plate_number__icontains=q).values('plate_number', 'owner_name', 'cnic', 'phone', 'vehicle_type', 'color').distinct()[:8]
    for c in challans:
        if any(r['value'].upper() == c['plate_number'].upper() for r in results):
            continue
        exists_count = Challan.objects.filter(plate_number__iexact=c['plate_number']).count()
        results.append({
            'value': c['plate_number'],
            'label': c['plate_number'],
            'sub': f"{c.get('owner_name') or 'Unknown'} · from challan records",
            'status': _status_for('plate', c['plate_number'], exists_count),
            'icon': '<i class="fa-solid fa-file-invoice"></i>',
            'fill': {
                'id_owner_name': c.get('owner_name') or '',
                'id_cnic': c.get('cnic') or '',
                'id_phone': c.get('phone') or '',
                'id_vehicle_type': c.get('vehicle_type') or '',
                'id_color': c.get('color') or '',
            }
        })
    return results


def _search_officer(q):
    results = []
    staff = User.objects.filter(
        Q(role__in=['DIG', 'SSP', 'SUPV', 'OFFICER', 'AUDIT', 'IT']) &
        (Q(first_name__icontains=q) | Q(last_name__icontains=q) |
         Q(staff_id__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))
    ).distinct()[:10]
    for u in staff:
        results.append({
            'value': str(u.id),
            'label': u.display_name,
            'sub': f"{u.get_role_display()} · {u.staff_id or u.public_id} · {u.region or ''}",
            'status': 'existing',
            'icon': '<i class="fa-solid fa-user-shield"></i>',
            'fill': {
                'id_officer_id': str(u.id),
                'id_officer_name': u.display_name,
                'id_officer_role': u.role,
                'id_officer_phone': u.phone or '',
                'id_officer_email': u.email or '',
            }
        })
    return results


def _search_camera(q):
    results = []
    cams = Camera.objects.filter(
        Q(camera_id__icontains=q) | Q(location__icontains=q)
    )[:10]
    for c in cams:
        results.append({
            'value': c.camera_id,
            'label': c.camera_id,
            'sub': c.location,
            'status': 'existing',
            'icon': '<i class="fa-solid fa-video"></i>',
            'fill': {
                'id_camera_id': c.camera_id,
                'id_location': c.location,
            }
        })
    return results


SEARCH_DISPATCH = {
    'cnic': _search_cnic,
    'phone': _search_phone,
    'email': _search_email,
    'plate': _search_plate,
    'vehicle': _search_plate,
    'officer': _search_officer,
    'camera': _search_camera,
}


@require_GET
@login_required
def autocomplete(request):
    field_type = request.GET.get('type', '').strip().lower()
    q = request.GET.get('q', '').strip()

    if not q or len(q) < 2:
        return JsonResponse({'results': [], 'status': None, 'hint': None})

    search_fn = SEARCH_DISPATCH.get(field_type)
    if not search_fn:
        return JsonResponse({'results': [], 'status': None, 'hint': None})

    results = search_fn(q)

    overall_status = 'new'
    if results:
        overall_status = results[0].get('status', 'new')
    else:
        validity = _validate(field_type, q)
        if validity == 'invalid':
            overall_status = 'invalid'

    hints = {
        'existing':  'Existing record found in database — fields auto-filled.',
        'new':       'New information — will be added as a new record.',
        'duplicate': 'Possible duplicate detected — review before saving.',
        'invalid':   'Invalid format — please verify the value.',
    }

    return JsonResponse({
        'results': results,
        'status': overall_status,
        'hint': hints.get(overall_status),
    })


@require_GET
@login_required
def check_duplicate(request):
    field_type = request.GET.get('type', '').strip().lower()
    value = request.GET.get('value', '').strip()

    if not value:
        return JsonResponse({'duplicate': False, 'count': 0, 'matches': []})

    if field_type == 'cnic':
        qs = list(User.objects.filter(cnic__iexact=value).values('id', 'display_name', 'role', 'cnic'))
        qs += list(Challan.objects.filter(cnic__iexact=value).values('id', 'owner_name', 'ticket_no'))
    elif field_type == 'phone':
        qs = list(User.objects.filter(phone__iexact=value).values('id', 'display_name', 'role', 'phone'))
        qs += list(Challan.objects.filter(phone__iexact=value).values('id', 'owner_name', 'ticket_no'))
    elif field_type == 'email':
        qs = list(User.objects.filter(email__iexact=value).values('id', 'display_name', 'role', 'email'))
    elif field_type in ('plate', 'vehicle'):
        qs = list(Challan.objects.filter(plate_number__iexact=value).values('id', 'owner_name', 'ticket_no', 'cnic', 'phone'))
        qs += list(VehicleRegistration.objects.filter(plate_number__iexact=value).values('id', 'plate_number'))
    else:
        qs = []

    return JsonResponse({
        'duplicate': len(qs) > 0,
        'count': len(qs),
        'matches': qs[:5],
    })

