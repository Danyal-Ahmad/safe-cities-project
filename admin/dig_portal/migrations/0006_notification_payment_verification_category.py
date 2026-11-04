"""AUDIT-BACKEND: Add 'payment_verification' to Notification.category choices.

The citizen pay_challan flow (citizen_portal/views.py) creates Notification
records with category='payment_verification' to alert staff that a payment
needs verification. Previously this value was NOT in Notification.CATEGORY_CHOICES,
which violated the model's schema definition (Django doesn't enforce choices at
the DB level, but the schema mismatch was still a bug). This migration aligns
the schema with the actual data being written.

This is a safe AlterField — max_length is unchanged (20), only the choices
metadata is updated. No data is modified or deleted.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0005_alter_banner_options_banner_auto_hide_after_search_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='category',
            field=models.CharField(
                choices=[
                    ('appeal_submit', 'Appeal Submitted'),
                    ('appeal_pending', 'Appeal Pending Review'),
                    ('appeal_approved', 'Appeal Approved'),
                    ('appeal_rejected', 'Appeal Rejected'),
                    ('appeal_escalated', 'Appeal Escalated'),
                    ('camera', 'Camera Event'),
                    ('challan', 'Challan Event'),
                    ('payment_verification', 'Payment Verification'),
                    ('system', 'System Event'),
                    ('other', 'Other'),
                ],
                default='other',
                max_length=20,
            ),
        ),
    ]
