from django.db import models
from django.conf import settings
from django.utils import timezone
from challans.models import Challan


class ChallanAppeal(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    STATUS_CHOICES = [
        (PENDING, 'Pending'), (APPROVED, 'Approved'), (REJECTED, 'Rejected'),
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

    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='appeals_reviewed')
    reviewed_at = models.DateTimeField(null=True, blank=True)

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
        return f"Appeal on {self.challan.ticket_no} | {self.status}"

    @classmethod
    def has_active_appeal(cls, challan):
        return cls.objects.filter(challan=challan, status=cls.PENDING).exists()

    def finalize(self, decision, comment, reviewer):
        valid = {code for code, _ in self.STATUS_CHOICES}
        if decision not in valid:
            raise ValueError(f"Invalid appeal decision {decision!r}. Must be one of {sorted(valid)}.")

        now = timezone.now()
        self.ssp_comment = comment
        self.ssp_reviewed_by = reviewer
        self.ssp_reviewed_at = now
        self.reviewed_by = reviewer
        self.reviewed_at = now
        self.status = decision
        self.save()

        if decision == self.APPROVED:
            challan = self.challan
            if challan.payment_status != Challan.PAID:
                challan.payment_status = Challan.VOIDED
                challan.save(update_fields=['payment_status'])
