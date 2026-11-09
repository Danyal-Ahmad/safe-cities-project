from django.core.management.base import BaseCommand
from admin.it_support_portal.models import PaymentMethod

METHODS = [
    {
        "name": "JazzCash",
        "provider": "JazzCash",
        "type": PaymentMethod.TYPE_WALLET,
        "status": PaymentMethod.STATUS_ACTIVE,
        "config": {
            "merchant_id": "",
            "password": "",
            "integrity_salt": "",
            "environment": "sandbox",
            "post_url": "",
        },
        "transaction_settings": {"environment": "sandbox", "currency": "PKR", "min_amount": 100},
    },
    {
        "name": "EasyPaisa",
        "provider": "EasyPaisa",
        "type": PaymentMethod.TYPE_WALLET,
        "status": PaymentMethod.STATUS_ACTIVE,
        "config": {
            "store_id": "",
            "hash_key": "",
            "environment": "sandbox",
            "post_url": "",
        },
        "transaction_settings": {"environment": "sandbox", "currency": "PKR", "min_amount": 100},
    },
]


class Command(BaseCommand):
    help = "Seed digital payment methods only (JazzCash, EasyPaisa, Card). No cash or bank transfer."

    def handle(self, *args, **options):
        for m in METHODS:
            try:
                status = m["status"]
            except Exception:
                status = PaymentMethod.STATUS_ACTIVE
            obj, created = PaymentMethod.objects.update_or_create(
                name=m["name"],
                defaults={
                    "provider": m["provider"],
                    "type": m["type"],
                    "status": status,
                    "config": m["config"],
                    "transaction_settings": m["transaction_settings"],
                },
            )
            self.stdout.write(f"  {'Created' if created else 'Updated'}: {obj.name} ({obj.status})")
        from django.db.models import Q
        n = PaymentMethod.objects.filter(
            Q(type='bank') | Q(type='cash')
            | Q(name__icontains='cash') | Q(name__icontains='Bank Transfer')
        ).update(status=PaymentMethod.STATUS_DISABLED)
        if n:
            self.stdout.write(f"  Disabled {n} legacy bank/cash method(s).")
        self.stdout.write(self.style.SUCCESS("Payment methods ready. Fill merchant credentials in IT → Payment Methods."))
