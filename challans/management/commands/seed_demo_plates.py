"""Seed demo challans for public search testing."""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Seed demo plate/CNIC challans for public search testing"

    def handle(self, *args, **options):
        from challans.models import Challan
        samples = [
            {"plate_number": "LEA-1100", "cnic": "35202-1234567-1", "fine_amount": 2000},
            {"plate_number": "LEO-826", "cnic": "35202-7654321-9", "fine_amount": 1500},
            {"plate_number": "ACR-597", "cnic": "37405-1111222-3", "fine_amount": 3000},
            {"plate_number": "ABC-0001", "cnic": "42101-9988776-5", "fine_amount": 1000},
        ]
        created = 0
        field_names = {f.name for f in Challan._meta.fields}
        for i, s in enumerate(samples):
            ticket = "DEMO-%s-%s" % (s["plate_number"].replace("-", ""), i + 1)
            defaults = {
                "plate_number": s["plate_number"],
                "cnic": s["cnic"],
                "fine_amount": s["fine_amount"],
                "issue_date": timezone.localdate() - timedelta(days=i),
                "due_date": timezone.localdate() + timedelta(days=30 - i),
                "payment_status": getattr(Challan, "UNPAID", "UNPAID"),
            }
            if "violation_type" in field_names:
                defaults["violation_type"] = "WRONG_WAY"
            if "location" in field_names:
                defaults["location"] = "Demo Zone"
            obj, was = Challan.objects.get_or_create(ticket_no=ticket, defaults=defaults)
            if was:
                created += 1
                self.stdout.write(self.style.SUCCESS("Created %s plate=%s" % (obj.ticket_no, obj.plate_number)))
            else:
                self.stdout.write("Exists %s" % obj.ticket_no)
        self.stdout.write(self.style.SUCCESS("Done. New=%s. Try search: LEA-1100 or LEA1100" % created))
