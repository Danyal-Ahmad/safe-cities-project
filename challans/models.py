import datetime
from django.db import models
from django.conf import settings
from django.utils import timezone
from cameras.models import Camera
from detections.models import Detection


class ChallanManager(models.Manager):
    def generate_ticket_no(self, plate_series=None):
        """Auto challan number (numeric), not plate-based.
        Format: 8+ digit number, sequential (e.g. 20019776).
        """
        last = (
            self.filter(ticket_no__regex=r'^[0-9]+$')
            .order_by('-id')
            .values_list('ticket_no', flat=True)
            .first()
        )
        if last:
            try:
                n = int(last) + 1
            except ValueError:
                n = None
        else:
            n = None
        if n is None:
            year = timezone.localdate().year
            base = year * 100000  # e.g. 202600000
            n = base + self.count() + 1
        while self.filter(ticket_no=str(n)).exists():
            n += 1
        return str(n)


class Challan(models.Model):
    WRONG_WAY = 'wrong_way'
    NO_HELMET = 'no_helmet'
    SIGNAL_BREAK = 'signal_break'
    OVER_SPEED = 'over_speed'
    OTHER = 'other'

    VIOLATION_CHOICES = [
        (WRONG_WAY, 'Wrong Way'),
        (NO_HELMET, 'No Helmet'),
        (SIGNAL_BREAK, 'Signal Break'),
        (OVER_SPEED, 'Over Speed'),
        (OTHER, 'Other'),
    ]

    # Catalog of violation types. Multiple types exist; only the types listed
    # in ENABLED_VIOLATIONS are live for enforcement. The violation type on a
    # challan is always the conclusion of the detection analysis, never a
    # default assigned at write time.
    ENABLED_VIOLATIONS = [WRONG_WAY]

    # Limited targeted translation of the violation catalog for Urdu-primary
    # documents. English remains the primary label via get_violation_type_display.
    VIOLATION_LABELS_URDU = {
        WRONG_WAY: 'غلط سمت میں گاڑی چلانا',
        NO_HELMET: 'ہیلمٹ کے بغیر دو پہیہ والی گاڑی چلانا',
        SIGNAL_BREAK: 'ٹریفک سگنل کی خلاف ورزی',
        OVER_SPEED: 'حد سے زیادہ رفتار',
        OTHER: 'دیگر ٹریفک خلاف ورزی',
    }
    UNPAID = 'UNPAID'
    PAID = 'PAID'
    VOIDED = 'VOIDED'
    PAYMENT_CHOICES = [(UNPAID, 'Unpaid'), (PAID, 'Paid'), (VOIDED, 'Voided')]

    detection = models.OneToOneField(Detection, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='challans',
                                     help_text='One detection can produce at most one challan (DB-enforced).')
    ticket_no = models.CharField(max_length=30, unique=True, editable=False)
    plate_number = models.CharField(max_length=20)
    province = models.CharField(max_length=10, null=True, blank=True)

    owner_name = models.CharField(max_length=255, null=True, blank=True)
    cnic = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)

    vehicle_type = models.CharField(max_length=20, null=True, blank=True)
    make_year = models.CharField(max_length=4, null=True, blank=True)
    color = models.CharField(max_length=20, null=True, blank=True)
    chassis_no = models.CharField(max_length=50, null=True, blank=True)

    violation_type = models.CharField(max_length=20, choices=VIOLATION_CHOICES)
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    location = models.CharField(max_length=255, null=True, blank=True)
    camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, null=True, blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)
    moving_direction = models.CharField(max_length=10, null=True, blank=True)
    legal_direction = models.CharField(max_length=10, null=True, blank=True)

    issue_date = models.DateField(default=datetime.date.today)
    due_date = models.DateField()
    payment_status = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default=UNPAID)
    paid_at = models.DateTimeField(null=True, blank=True)
    txn_ref = models.CharField(max_length=100, null=True, blank=True, help_text="Transaction reference from payment gateway")
    payment_method = models.CharField(max_length=50, null=True, blank=True, help_text="Payment method used (e.g. JazzCash, EasyPaisa, Card)")
    pdf_file = models.FileField(upload_to='challans/pdfs/%Y/%m/%d/', null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name='challans_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ChallanManager()

    class Meta:
        db_table = 'sc_challans'
        ordering = ['-issue_date', '-created_at']
        indexes = [
            models.Index(fields=['cnic']),
            models.Index(fields=['plate_number']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['issue_date']),
            models.Index(fields=['txn_ref']),
        ]

    def __str__(self):
        return f"{self.ticket_no} | {self.plate_number} ({self.payment_status})"

    @property
    def violation_type_display_urdu(self):
        """Limited targeted Urdu label for the analyzed violation type."""
        return self.VIOLATION_LABELS_URDU.get(self.violation_type, self.violation_type or '-')

    @property
    def confidence_percent(self):
        """ai_confidence normalized to a 0-100 percent scale for display."""
        v = self.ai_confidence
        if v is None:
            return None
        return round(v * 100, 2) if v <= 1.0 else round(v, 2)

    @property
    def is_overdue(self):
        if self.payment_status == self.UNPAID:
            return timezone.localdate() > self.due_date
        return False

    @property
    def psid(self):
        """Numeric Payment System ID only (digits). Stable per challan."""
        tid = str(self.ticket_no or self.pk or 0)
        digits = ''.join(ch for ch in tid if ch.isdigit()) or str(self.pk or 0)
        core = digits[-12:].zfill(12)
        total = 0
        for i, ch in enumerate(reversed(core)):
            n = int(ch)
            if i % 2 == 0:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        check = (10 - (total % 10)) % 10
        return f"{core}{check}"


    @property
    def payment_qr_payload(self):
        """Payload encoded in QR for mobile banking apps / agent counters."""
        return (
            f"SAFECITY|PSID:{self.psid}|TKT:{self.ticket_no}|"
            f"PLT:{self.plate_number}|AMT:{self.fine_amount}|STS:{self.payment_status}"
        )

    def mark_paid(self, txn_ref=None, payment_method=None):
        from django.utils import timezone
        self.payment_status = self.PAID
        self.paid_at = timezone.now()
        update_fields = ['payment_status', 'paid_at', 'updated_at']
        if txn_ref:
            self.txn_ref = txn_ref
            update_fields.append('txn_ref')
        if payment_method:
            self.payment_method = payment_method
            update_fields.append('payment_method')
        self.save(update_fields=update_fields)

