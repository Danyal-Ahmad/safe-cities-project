from django.db import models
from django.conf import settings
from challans.models import Challan


class ChallanAppeal(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    ESCALATED = 'escalated'
    STATUS_CHOICES = [
        (PENDING, 'Pending'), (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'), (ESCALATED, 'Escalated to DIG'),
    ]

    STAGE_OFFICER = 'officer'
    STAGE_SSP = 'ssp'
    STAGE_DIG = 'dig'
    STAGE_CHOICES = [
        (STAGE_OFFICER, 'Officer Review'),
        (STAGE_SSP, 'SSP Review'),
        (STAGE_DIG, 'DIG Review'),
    ]

    challan = models.ForeignKey(Challan, on_delete=models.CASCADE, related_name='appeals')
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='appeals_submitted',
        help_text='Null when submitted as guest via public search (CNIC matched).',
    )
    guest_cnic = models.CharField(max_length=15, blank=True, default='')
    guest_name = models.CharField(max_length=120, blank=True, default='')
    reason = models.TextField()
    evidence_file = models.ImageField(upload_to='appeals/evidence/%Y/%m/%d/', null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)

    current_stage = models.CharField(max_length=10, choices=STAGE_CHOICES, default=STAGE_SSP)

    officer_comment = models.TextField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='appeals_reviewed')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    is_escalated = models.BooleanField(default=False)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(null=True, blank=True)
    dig_comment = models.TextField(null=True, blank=True)
    dig_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='appeals_escalated')
    dig_reviewed_at = models.DateTimeField(null=True, blank=True)

    ssp_comment = models.TextField(null=True, blank=True)
    ssp_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='appeals_ssp_reviewed')
    ssp_reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_challan_appeals'
        ordering = ['-created_at']

    def __str__(self):
        return f"Appeal on {self.challan.ticket_no} — {self.status} ({self.current_stage})"

    @classmethod
    def has_active_appeal(cls, challan):
        return cls.objects.filter(challan=challan, status__in=[cls.PENDING, cls.ESCALATED]).exists()

    def advance_to_ssp(self, officer_comment, reviewer):
        self.officer_comment = officer_comment
        self.reviewed_by = reviewer
        self.reviewed_at = __import__('django.utils.timezone', fromlist=['now']).now()
        self.current_stage = self.STAGE_SSP
        self.status = self.PENDING
        self.save()

    def advance_to_dig(self, ssp_comment, reviewer):
        self.ssp_comment = ssp_comment
        self.ssp_reviewed_by = reviewer
        self.ssp_reviewed_at = __import__('django.utils.timezone', fromlist=['now']).now()
        self.current_stage = self.STAGE_DIG
        self.status = self.ESCALATED
        self.is_escalated = True
        self.escalated_at = __import__('django.utils.timezone', fromlist=['now']).now()
        self.save()

    def finalize(self, decision, comment, reviewer):
        """Finalise the appeal at the current stage with *decision*, *comment* and *reviewer*.

        H5 FIX: Write to stage-appropriate fields so SSP decisions don't bleed
        into DIG columns and vice-versa.

        H1 FIX: When the final decision is APPROVED, void the underlying challan
        so citizens are not double-billed while the appeal is pending.
        """
        from django.utils import timezone as tz
        valid = {code for code, _ in self.STATUS_CHOICES}
        if decision not in valid:
            raise ValueError(
                f"Invalid appeal decision {decision!r}. Must be one of {sorted(valid)}."
            )

        now = tz.now()

        # H5 FIX: Route comment and reviewer to the correct stage-specific fields.
        if self.current_stage == self.STAGE_SSP:
            self.ssp_comment = comment
            self.ssp_reviewed_by = reviewer
            self.ssp_reviewed_at = now
        elif self.current_stage == self.STAGE_DIG:
            self.dig_comment = comment
            self.dig_reviewed_by = reviewer
            self.dig_reviewed_at = now
        else:
            # STAGE_OFFICER or any future stage
            self.officer_comment = comment
            self.reviewed_by = reviewer
            self.reviewed_at = now

        self.status = decision
        self.save()

        # H1 FIX: Void the challan when the appeal is approved so the citizen
        # is not expected to pay a challan that has been officially dismissed.
        if decision == self.APPROVED:
            try:
                challan = self.challan
                from challans.models import Challan
                if challan.payment_status != Challan.PAID:
                    challan.payment_status = Challan.VOIDED
                    challan.save(update_fields=['payment_status'])
            except Exception:
                pass

