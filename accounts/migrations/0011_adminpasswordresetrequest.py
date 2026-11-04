from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0010_user_signature_user_signature_designation_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminPasswordResetRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('requested_by_email', models.EmailField(max_length=254)),
                ('token', models.CharField(db_index=True, max_length=64, unique=True)),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'Pending DIG Action'),
                        ('RESOLVED', 'Resolved'),
                        ('CANCELLED', 'Cancelled'),
                    ],
                    default='PENDING',
                    max_length=12,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('reason_note', models.CharField(blank=True, default='', max_length=255)),
                ('resolved_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.SET_NULL,
                    related_name='admin_resets_performed',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('target_user', models.ForeignKey(
                    on_delete=models.CASCADE,
                    related_name='admin_reset_requests',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'sc_admin_password_reset_requests',
                'ordering': ['-created_at'],
            },
        ),
    ]
