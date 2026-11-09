from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dig_portal', '0012_systemsettings_pdf_template'),
    ]

    operations = [
        migrations.CreateModel(
            name='BlacklistEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plate_number', models.CharField(db_index=True, max_length=20, unique=True)),
                ('reason', models.CharField(max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='blacklist_entries_created', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name_plural': 'Blacklist entries',
                'db_table': 'sc_blacklist',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AlterModelTable(name='systemsettings', table='sc_system_settings'),
        migrations.AlterModelTable(name='auditlog', table='sc_audit_logs'),
        migrations.AlterModelTable(name='alert', table='sc_alerts'),
        migrations.AlterModelTable(name='banner', table='sc_banners'),
        migrations.AlterModelTable(name='notification', table='sc_notifications'),
        migrations.AlterModelTable(name='shift', table='sc_shifts'),
        migrations.AlterModelTable(name='challantemplate', table='sc_challan_templates'),
    ]
