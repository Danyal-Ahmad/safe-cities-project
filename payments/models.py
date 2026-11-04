from django.db import models
from django.utils import timezone


class PaymentTransaction(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    ticket_no = models.CharField(max_length=30, db_index=True)
    challan = models.ForeignKey(
        'challans.Challan',
        on_delete=models.CASCADE,
        related_name='transactions',
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=50, default='demo', help_text="e.g. JazzCash, EasyPaisa, Card, Demo")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    txn_ref = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    gateway_ref = models.CharField(max_length=100, null=True, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_payment_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket_no', 'status']),
            models.Index(fields=['txn_ref']),
        ]

    def __str__(self):
        return f"{self.ticket_no} — {self.provider} — {self.amount} ({self.status})"

    def mark_success(self, gateway_ref=None, raw_data=None):
        self.status = self.STATUS_SUCCESS
        if gateway_ref:
            self.gateway_ref = gateway_ref
        if raw_data:
            self.raw_response = raw_data
        self.save(update_fields=['status', 'gateway_ref', 'raw_response', 'updated_at'])
        if self.challan:
            self.challan.mark_paid(txn_ref=self.txn_ref, payment_method=self.provider)
