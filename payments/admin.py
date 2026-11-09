from django.contrib import admin
from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('ticket_no', 'provider', 'amount', 'status', 'txn_ref', 'created_at')
    list_filter = ('status', 'provider', 'created_at')
    search_fields = ('ticket_no', 'txn_ref', 'gateway_ref')
    readonly_fields = ('created_at', 'updated_at')
