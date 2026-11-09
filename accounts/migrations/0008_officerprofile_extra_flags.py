from django.db import migrations, models


def add_officer_extra_flags(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor
    table = 'sc_officer_profiles'
    columns = [
        ('can_live_tracking', True),
        ('can_live_monitor', False),
        ('can_record_payment', False),
        ('can_manage_blacklist', False),
        ('can_add_manual_challan', True),
        ('can_view_own_performance', True),
        ('can_flag_for_dig', True),
        ('can_add_internal_notes', True),
    ]

    with connection.cursor() as cursor:
        if vendor == 'sqlite':
            cursor.execute(f'PRAGMA table_info("{table}")')
            existing = {row[1] for row in cursor.fetchall()}
        else:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = %s",
                [table],
            )
            existing = {row[0] for row in cursor.fetchall()}

        for name, default in columns:
            if name in existing:
                continue
            if vendor == 'sqlite':
                default_sql = '1' if default else '0'
                sql = f'ALTER TABLE "{table}" ADD COLUMN "{name}" boolean DEFAULT {default_sql} NOT NULL'
                cursor.execute(sql)
                continue
            default_sql = 'TRUE' if default else 'FALSE'
            sql = (
                f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS '
                f'{name} boolean DEFAULT {default_sql} NOT NULL'
            )
            try:
                cursor.execute('SAVEPOINT officer_flag_sp')
                cursor.execute(sql)
                cursor.execute('RELEASE SAVEPOINT officer_flag_sp')
            except Exception:
                cursor.execute('ROLLBACK TO SAVEPOINT officer_flag_sp')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_role_profiles'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='officerprofile',
                    name='can_live_tracking',
                    field=models.BooleanField(default=True),
                ),
                migrations.AddField(
                    model_name='officerprofile',
                    name='can_live_monitor',
                    field=models.BooleanField(default=False),
                ),
                migrations.AddField(
                    model_name='officerprofile',
                    name='can_record_payment',
                    field=models.BooleanField(default=False),
                ),
                migrations.AddField(
                    model_name='officerprofile',
                    name='can_manage_blacklist',
                    field=models.BooleanField(default=False),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_officer_extra_flags, migrations.RunPython.noop),
            ],
        ),
    ]
