

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0015_rename_dig_portal__is_acti_a586ab_idx_sc_alerts_is_acti_8d2e41_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='audit_pdf_template',
            field=models.CharField(blank=True, default='government_classic', help_text="Active audit report PDF template key. Built-in = filename under templates/audit_templates/ without .html. DB template = 'db:<AuditPDFTemplate id>'.", max_length=100),
        ),
        migrations.CreateModel(
            name='AuditPDFTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('description', models.CharField(blank=True, default='', max_length=255)),
                ('html_content', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'sc_audit_pdf_templates',
                'ordering': ['-created_at'],
            },
        ),
    ]

