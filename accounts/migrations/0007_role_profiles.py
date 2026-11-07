from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_professional_table_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='officerprofile',
            name='badge_number',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='officerprofile',
            name='belt_number',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='officerprofile',
            name='rank',
            field=models.CharField(blank=True, default='Enforcement Officer', max_length=60),
        ),
        migrations.AddField(
            model_name='officerprofile',
            name='unit',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='officerprofile',
            name='station',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='officerprofile',
            name='shift_preference',
            field=models.CharField(
                blank=True, choices=[('DAY', 'Day'), ('NIGHT', 'Night'), ('ROTATING', 'Rotating')],
                default='DAY', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='officerprofile',
            name='joining_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='officerprofile',
            name='is_field_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='officerprofile',
            name='max_daily_challans',
            field=models.PositiveIntegerField(default=50),
        ),
        migrations.AddField(
            model_name='officerprofile',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.CreateModel(
            name='DigProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('badge_number', models.CharField(blank=True, default='', max_length=40)),
                ('rank', models.CharField(blank=True, default='Deputy Inspector General', max_length=80)),
                ('command_region', models.CharField(blank=True, default='Central', max_length=100)),
                ('office_address', models.CharField(blank=True, default='', max_length=255)),
                ('office_phone', models.CharField(blank=True, default='', max_length=30)),
                ('authority_level', models.CharField(
                    choices=[('FULL', 'Full command'), ('ACTING', 'Acting'), ('LIMITED', 'Limited')],
                    default='FULL', max_length=20,
                )),
                ('can_manage_all_staff', models.BooleanField(default=True)),
                ('can_override_appeals', models.BooleanField(default=True)),
                ('can_purge_data', models.BooleanField(default=True)),
                ('can_edit_system_settings', models.BooleanField(default=True)),
                ('appointment_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    limit_choices_to={'role': 'DIG'}, on_delete=django.db.models.deletion.CASCADE,
                    related_name='dig_profile', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'sc_dig_profiles', 'verbose_name': 'DIG profile', 'verbose_name_plural': 'DIG profiles'},
        ),
        migrations.CreateModel(
            name='SspProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('badge_number', models.CharField(blank=True, default='', max_length=40)),
                ('rank', models.CharField(blank=True, default='Senior Superintendent of Police', max_length=80)),
                ('division', models.CharField(blank=True, default='', max_length=100)),
                ('district', models.CharField(blank=True, default='', max_length=100)),
                ('region', models.CharField(blank=True, default='Central Region', max_length=100)),
                ('office_address', models.CharField(blank=True, default='', max_length=255)),
                ('office_phone', models.CharField(blank=True, default='', max_length=30)),
                ('can_review_high_value', models.BooleanField(default=True)),
                ('can_approve_escalations', models.BooleanField(default=True)),
                ('can_view_regional_analytics', models.BooleanField(default=True)),
                ('high_value_threshold', models.PositiveIntegerField(default=5000)),
                ('appointment_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    limit_choices_to={'role': 'SSP'}, on_delete=django.db.models.deletion.CASCADE,
                    related_name='ssp_profile', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'sc_ssp_profiles', 'verbose_name': 'SSP profile', 'verbose_name_plural': 'SSP profiles'},
        ),
        migrations.CreateModel(
            name='SupervisorProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('badge_number', models.CharField(blank=True, default='', max_length=40)),
                ('rank', models.CharField(blank=True, default='Shift Supervisor', max_length=80)),
                ('team_name', models.CharField(blank=True, default='', max_length=100)),
                ('region', models.CharField(blank=True, default='', max_length=100)),
                ('station', models.CharField(blank=True, default='', max_length=100)),
                ('max_team_size', models.PositiveIntegerField(default=12)),
                ('can_assign_shifts', models.BooleanField(default=True)),
                ('can_view_team_performance', models.BooleanField(default=True)),
                ('can_reassign_cameras', models.BooleanField(default=False)),
                ('shift_type', models.CharField(
                    blank=True, choices=[('DAY', 'Day'), ('NIGHT', 'Night'), ('ROTATING', 'Rotating')],
                    default='ROTATING', max_length=20,
                )),
                ('appointment_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    limit_choices_to={'role': 'SUPV'}, on_delete=django.db.models.deletion.CASCADE,
                    related_name='supervisor_profile', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'sc_supervisor_profiles', 'verbose_name': 'Supervisor profile', 'verbose_name_plural': 'Supervisor profiles'},
        ),
        migrations.CreateModel(
            name='ItProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('employee_id', models.CharField(blank=True, default='', max_length=40)),
                ('rank', models.CharField(blank=True, default='IT Support Engineer', max_length=80)),
                ('specialization', models.CharField(blank=True, default='Infrastructure', max_length=100)),
                ('department', models.CharField(blank=True, default='IT Wing', max_length=100)),
                ('can_manage_cameras', models.BooleanField(default=True)),
                ('can_edit_pdf_settings', models.BooleanField(default=True)),
                ('can_manage_payment_methods', models.BooleanField(default=True)),
                ('can_run_backups', models.BooleanField(default=True)),
                ('can_view_system_health', models.BooleanField(default=True)),
                ('can_live_tracking', models.BooleanField(default=True)),
                ('on_call', models.BooleanField(default=False)),
                ('appointment_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    limit_choices_to={'role': 'IT'}, on_delete=django.db.models.deletion.CASCADE,
                    related_name='it_profile', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'sc_it_profiles', 'verbose_name': 'IT profile', 'verbose_name_plural': 'IT profiles'},
        ),
        migrations.CreateModel(
            name='AuditorProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('employee_id', models.CharField(blank=True, default='', max_length=40)),
                ('rank', models.CharField(blank=True, default='Internal Audit Officer', max_length=80)),
                ('audit_scope', models.CharField(blank=True, default='Full system', max_length=100)),
                ('department', models.CharField(blank=True, default='Internal Audit', max_length=100)),
                ('can_view_financial_audit', models.BooleanField(default=True)),
                ('can_view_operational_audit', models.BooleanField(default=True)),
                ('can_export_audit_logs', models.BooleanField(default=True)),
                ('can_view_anomalies', models.BooleanField(default=True)),
                ('can_view_user_activity', models.BooleanField(default=True)),
                ('clearance_level', models.CharField(
                    choices=[('STANDARD', 'Standard'), ('ELEVATED', 'Elevated'), ('FULL', 'Full')],
                    default='STANDARD', max_length=20,
                )),
                ('appointment_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    limit_choices_to={'role': 'AUDIT'}, on_delete=django.db.models.deletion.CASCADE,
                    related_name='auditor_profile', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'sc_auditor_profiles', 'verbose_name': 'Auditor profile', 'verbose_name_plural': 'Auditor profiles'},
        ),
        migrations.CreateModel(
            name='CitizenProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('father_name', models.CharField(blank=True, default='', max_length=120)),
                ('address', models.CharField(blank=True, default='', max_length=255)),
                ('city', models.CharField(blank=True, default='', max_length=80)),
                ('province', models.CharField(blank=True, default='', max_length=80)),
                ('postal_code', models.CharField(blank=True, default='', max_length=20)),
                ('preferred_language', models.CharField(
                    choices=[('en', 'English'), ('ur', 'Urdu')], default='en', max_length=10,
                )),
                ('notification_email', models.BooleanField(default=True)),
                ('notification_sms', models.BooleanField(default=True)),
                ('is_verified', models.BooleanField(default=False)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('total_challans', models.PositiveIntegerField(default=0)),
                ('total_paid', models.PositiveIntegerField(default=0)),
                ('total_unpaid', models.PositiveIntegerField(default=0)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    limit_choices_to={'role': 'USER'}, on_delete=django.db.models.deletion.CASCADE,
                    related_name='citizen_profile', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'sc_citizen_profiles', 'verbose_name': 'Citizen profile', 'verbose_name_plural': 'Citizen profiles'},
        ),
    ]

