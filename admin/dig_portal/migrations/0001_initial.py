from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('default_fines', models.JSONField(blank=True, default=dict)),
                ('template_config', models.JSONField(blank=True, default=dict)),
                ('email_template', models.JSONField(blank=True, default=dict)),
                ('due_date_days', models.IntegerField(default=30)),
                ('email_enabled', models.BooleanField(default=False)),
                ('ai_confidence_threshold', models.FloatField(default=0.95)),
                ('pdf_logo', models.ImageField(blank=True, null=True, upload_to='settings/')),
                ('excise_api_url', models.CharField(blank=True, max_length=255, null=True)),
                ('excise_api_key', models.CharField(blank=True, max_length=255, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.user')),
            ],
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=80)),
                ('target_model', models.CharField(max_length=50)),
                ('target_id', models.IntegerField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_entries', to='accounts.user')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['actor', 'timestamp'], name='dig_portal_aud_actor_time_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['action', 'timestamp'], name='dig_portal_aud_acti_time_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['target_model', 'target_id'], name='dig_portal_aud_targ_mod_idx'),
        ),
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('severity', models.CharField(choices=[('info', 'Info'), ('success', 'Success'), ('warning', 'Warning'), ('danger', 'Danger')], default='info', max_length=10)),
                ('audience', models.CharField(choices=[('all', 'Everyone'), ('staff', 'All Staff'), ('citizens', 'All Citizens'), ('dig', 'DIG only'), ('ssp', 'SSP only'), ('supervisor', 'Supervisors only'), ('officer', 'Officers only'), ('audit', 'Audit Officers only'), ('it', 'IT Support only')], default='all', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, help_text='Optional expiry timestamp', null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alerts_created', to='accounts.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['is_active', 'audience'], name='dig_portal_ale_is_act_aud_idx'),
        ),
        migrations.CreateModel(
            name='Banner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Internal title for management', max_length=200)),
                ('html_content', models.TextField(help_text='Raw HTML content of the banner (DIG is trusted)')),
                ('placement', models.CharField(choices=[('top', 'Top of page'), ('bottom', 'Bottom of page'), ('ad', 'Home page ad slot')], default='top', max_length=10)),
                ('audience', models.CharField(choices=[('all', 'Everyone'), ('staff', 'All Staff'), ('citizens', 'All Citizens')], default='all', max_length=20)),
                ('bg_color', models.CharField(default='#1F4E79', help_text='CSS color for banner background', max_length=20)),
                ('text_color', models.CharField(default='#FFFFFF', help_text='CSS color for banner text', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='banners_created', to='accounts.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

