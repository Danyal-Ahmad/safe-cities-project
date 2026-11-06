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
