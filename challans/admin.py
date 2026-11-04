from django.contrib import admin
from .models import Challan


@admin.register(Challan)
class ChallanAdmin(admin.ModelAdmin):
    list_display = ('ticket_no', 'plate_number', 'owner_name', 'violation_type',
                    'fine_amount', 'payment_status', 'issue_date', 'due_date')
    list_filter = ('payment_status', 'violation_type', 'issue_date')
    search_fields = ('ticket_no', 'plate_number', 'cnic', 'owner_name')
    date_hierarchy = 'issue_date'

