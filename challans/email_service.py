import logging
from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import TimestampSigner
from django.urls import reverse

logger = logging.getLogger('wrongway.email')


def generate_signed_view_link(challan, request=None):
    signer = TimestampSigner()
    token = signer.sign(challan.id)
    if request:
        return request.build_absolute_uri(reverse('challans:challan_detail_signed', args=[token]))
    return f"/challan/view/{token}/"


def send_challan_notification(challan, request=None):
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        logger.info("Email notifications disabled - skipping for %s", challan.ticket_no)
        return False
    recipient_email = getattr(challan, 'owner_email', None) or None
    if not recipient_email:
        if challan.cnic:
            from accounts.models import User
            try:
                citizen = User.objects.get(cnic=challan.cnic, role=User.USER)
                recipient_email = citizen.email
            except User.DoesNotExist:
                pass
    if not recipient_email:
        logger.info("Owner has no email - skipping for %s", challan.ticket_no)
        return False
    view_link = generate_signed_view_link(challan, request)
    subject = f"New E-Challan Issued | {challan.ticket_no}"
    body = (
        f"A new e-challan has been issued for vehicle {challan.plate_number}.\n\n"
        f"Challan No: {challan.ticket_no}\n"
        f"Violation: {challan.get_violation_type_display()}\n"
        f"Fine Amount: PKR {challan.fine_amount}\n"
        f"Due Date: {challan.due_date}\n"
        f"Location: {challan.location}\n\n"
        f"View your challan (link valid for 30 days):\n{view_link}\n\n"
        f"Safe City | Traffic Enforcement"
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient_email])
        logger.info("Email sent for %s", challan.ticket_no)
        return True
    except Exception as e:
        logger.warning("Email send failed for %s: %s (challan still created)", challan.ticket_no, e)
        return False

