

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0019_challantemplate_design_json'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='auditlog',
            name='device',
            field=models.CharField(blank=True, default='', help_text='Human-readable device summary (browser / OS / type).', max_length=120),
        ),
        migrations.AddField(
            model_name='auditlog',
            name='user_agent',
            field=models.CharField(blank=True, default='', max_length=400),
        ),
        migrations.CreateModel(
            name='LoginEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username_attempted', models.CharField(max_length=150)),
                ('portal', models.CharField(choices=[('admin', 'Staff Portal'), ('citizen', 'Citizen Portal')], default='admin', max_length=10)),
                ('success', models.BooleanField(default=False)),
                ('failure_reason', models.CharField(blank=True, default='', max_length=120)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, default='', max_length=400)),
                ('browser', models.CharField(blank=True, default='', max_length=120)),
                ('os', models.CharField(blank=True, default='', max_length=120)),
                ('device_type', models.CharField(blank=True, default='', max_length=30)),
                ('device_brand', models.CharField(blank=True, default='', max_length=80)),
                ('device_summary', models.CharField(blank=True, default='', max_length=160)),
                ('session_key', models.CharField(blank=True, default='', max_length=64)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='login_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'sc_login_events',
                'ordering': ['-timestamp'],
                'indexes': [models.Index(fields=['user', 'timestamp'], name='sc_login_ev_user_id_f10b16_idx'), models.Index(fields=['success', 'timestamp'], name='sc_login_ev_success_e858bb_idx'), models.Index(fields=['ip_address', 'timestamp'], name='sc_login_ev_ip_addr_6e57f0_idx')],
            },
        ),
    ]

