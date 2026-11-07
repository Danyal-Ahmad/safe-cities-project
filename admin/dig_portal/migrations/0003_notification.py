from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0002_banner_enhancements'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('category', models.CharField(
                    max_length=20,
                    choices=[
                        ('appeal_submit', 'Appeal Submitted'),
                        ('appeal_pending', 'Appeal Pending Review'),
                        ('appeal_approved', 'Appeal Approved'),
                        ('appeal_rejected', 'Appeal Rejected'),
                        ('appeal_escalated', 'Appeal Escalated'),
                        ('camera', 'Camera Event'),
                        ('challan', 'Challan Event'),
                        ('system', 'System Event'),
                        ('other', 'Other'),
                    ],
                    default='other',
                )),
                ('target_url', models.CharField(blank=True, default='', max_length=500,
                                                 help_text="URL to navigate to when clicked")),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', 'is_read'], name='dig_portal_notif_recip_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['category'], name='dig_portal_notif_cat_idx'),
        ),
    ]

