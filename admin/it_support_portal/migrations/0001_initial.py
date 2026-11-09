from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text="Display name (e.g. 'JazzCash', 'EasyPaisa', 'Bank Transfer').", max_length=100, unique=True)),
                ('provider', models.CharField(help_text='Payment provider / bank name (e.g. JazzCash, NBP).', max_length=100)),
                ('type', models.CharField(choices=[('wallet', 'Mobile Wallet'), ('card', 'Card Payment'), ('bank', 'Bank Transfer'), ('gateway', 'Payment Gateway')], default='wallet', max_length=20)),
                ('status', models.CharField(choices=[('active', 'Active'), ('disabled', 'Disabled'), ('maintenance', 'Maintenance')], default='disabled', max_length=20)),
                ('config', models.JSONField(blank=True, default=dict, help_text='Provider-specific config: merchant_id, password, integrity_salt, publishable_key, secret_key, account_number, IBAN, etc. Stored as JSON.')),
                ('transaction_settings', models.JSONField(blank=True, default=dict, help_text='Min/max amount, currency, return_url, environment (sandbox/live), settlement period, etc.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, blank=True, on_delete=models.SET_NULL, related_name='payment_methods_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
                'indexes': [
                    models.Index(fields=['status'], name='it_support_status_idx'),
                    models.Index(fields=['type'], name='it_support_type_idx'),
                ],
            },
        ),
    ]

