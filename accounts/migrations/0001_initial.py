"""accounts migration 0001 — User + OfficerProfile + VehicleRegistration models.

This migration was regenerated after the project restructure.
"""
import django.contrib.auth.models
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(max_length=150, unique=True)),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(max_length=254, blank=True)),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('role', models.CharField(choices=[('DIG', 'DIG (Super Admin)'), ('SSP', 'SSP — Senior Superintendent'), ('SUPV', 'Supervisor'), ('OFFICER', 'Officer'), ('AUDIT', 'Audit Officer'), ('IT', 'IT Support'), ('USER', 'Registered Citizen')], default='USER', max_length=10)),
                ('phone', models.CharField(blank=True, help_text='E.164 format, e.g. +923001234567', max_length=20, null=True, unique=True)),
                ('cnic', models.CharField(blank=True, help_text='Optional. Used only for challan matching, never for login.', max_length=20, null=True)),
                ('is_guest_verified', models.BooleanField(default=False)),
                ('avatar_color', models.CharField(default='#0EA5E9', max_length=20)),
                ('failed_login_attempts', models.IntegerField(default=0)),
                ('locked_until', models.DateTimeField(blank=True, null=True)),
                ('last_login_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('staff_id', models.CharField(blank=True, help_text='Official police staff ID, e.g. PSC-2026-DIG-001', max_length=30, null=True)),
                ('region', models.CharField(blank=True, help_text="Operational region for SSP/Supervisor (e.g. 'Lahore Central')", max_length=60, null=True)),
                ('designation', models.CharField(blank=True, help_text="Official designation (e.g. 'Deputy Inspector General')", max_length=100, null=True)),
                ('department', models.CharField(blank=True, help_text="Department name (e.g. 'Traffic Police Punjab')", max_length=100, null=True)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='OfficerProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('can_review_detections', models.BooleanField(default=True)),
                ('can_review_appeals', models.BooleanField(default=True)),
                ('can_flag_for_dig', models.BooleanField(default=True)),
                ('can_add_manual_challan', models.BooleanField(default=True)),
                ('can_view_own_performance', models.BooleanField(default=True)),
                ('can_add_internal_notes', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('officer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='officer_profile', to='accounts.user')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='officer_profiles_created', to='accounts.user')),
            ],
        ),
        migrations.CreateModel(
            name='VehicleRegistration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plate_number', models.CharField(help_text='e.g. LRN-795', max_length=20)),
                ('vehicle_type', models.CharField(default='car', max_length=20)),
                ('make', models.CharField(blank=True, help_text='e.g. Honda Civic', max_length=50, null=True)),
                ('year', models.CharField(blank=True, max_length=4, null=True)),
                ('color', models.CharField(blank=True, max_length=20, null=True)),
                ('is_primary', models.BooleanField(default=False, help_text='Primary vehicle for notifications')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registered_vehicles', to='accounts.user')),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('owner', 'plate_number')},
            },
        ),
    ]
