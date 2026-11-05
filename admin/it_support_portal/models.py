from django.db import models
from django.conf import settings


class PaymentMethod(models.Model):
    TYPE_WALLET = 'wallet'
    TYPE_CARD = 'card'
    TYPE_GATEWAY = 'gateway'
    TYPE_CHOICES = [
        (TYPE_WALLET,  'Mobile Wallet'),
        (TYPE_CARD,    'Card Payment'),
        (TYPE_GATEWAY, 'Payment Gateway'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_DISABLED = 'disabled'
    STATUS_MAINTENANCE = 'maintenance'
    STATUS_CHOICES = [
        (STATUS_ACTIVE,      'Active'),
        (STATUS_DISABLED,    'Disabled'),
        (STATUS_MAINTENANCE, 'Maintenance'),
    ]

    name = models.CharField(
        max_length=100, unique=True,
        help_text="Display name (e.g. 'JazzCash', 'EasyPaisa', 'Card')."
    )
    provider = models.CharField(
        max_length=100,
        help_text="Payment provider (e.g. 'JazzCash', 'EasyPaisa')."
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_WALLET)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DISABLED)

    config = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Provider-specific config: merchant_id, password, integrity_salt, "
            "publishable_key, secret_key, account_number, IBAN, etc. Stored as JSON."
        )
    )

    transaction_settings = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Min/max amount, currency, return_url, environment (sandbox/live), "
            "settlement period, etc."
        )
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payment_methods_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sc_payment_methods'
        ordering = ['name']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.provider}) | {self.status}"

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    @property
    def environment(self):
        return (self.transaction_settings or {}).get('environment', 'sandbox')

    @classmethod
    def active_for_citizens(cls):
        from django.db.models import Q
        return (
            cls.objects.filter(status=cls.STATUS_ACTIVE)
            .exclude(type__in=['bank', 'cash'])
            .exclude(
                Q(name__iexact='cash')
                | Q(provider__iexact='cash')
                | Q(name__icontains='bank transfer')
                | Q(provider__icontains='bank transfer')
            )
            .order_by('name')
        )

    @classmethod
    def get_default_config(cls, type_code):
        if type_code == cls.TYPE_WALLET:
            return {
                'merchant_id': '',
                'password': '',
                'integrity_salt': '',
                'return_url': '',
            }
        if type_code == cls.TYPE_CARD:
            return {
                'publishable_key': '',
                'secret_key': '',
                'webhook_secret': '',
            }
        if type_code == cls.TYPE_GATEWAY:
            return {
                'api_key': '',
                'api_secret': '',
                'webhook_url': '',
                'return_url': '',
            }
        return {}

    @classmethod
    def get_default_tx_settings(cls):
        return {
            'currency': 'PKR',
            'min_amount': 100,
            'max_amount': 1000000,
            'environment': 'sandbox',
            'settlement_days': 2,
        }

