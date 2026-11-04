"""Drop orphan custom_permissions column.

Runs on PostgreSQL (production) and SQLite (USE_SQLITE_DRY_RUN / CI sandbox).
Table-existence checks and DDL are branched per-vendor since SQLite has no
information_schema and no "DROP COLUMN IF EXISTS" support.
"""
from django.db import migrations


def _table_exists(cur, vendor, table):
    if vendor == 'sqlite':
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=%s",
            [table],
        )
    else:
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = %s",
            [table],
        )
    return cur.fetchone() is not None


def _column_exists(cur, vendor, table, column):
    if vendor == 'sqlite':
        cur.execute(f'PRAGMA table_info("{table}")')
        return any(row[1] == column for row in cur.fetchall())
    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = %s AND column_name = %s",
        [table, column],
    )
    return cur.fetchone() is not None


def forward_drop_custom_permissions(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cur:
        for table in ('sc_users', 'accounts_user'):
            if not _table_exists(cur, vendor, table):
                continue
            if not _column_exists(cur, vendor, table, 'custom_permissions'):
                continue
            if vendor == 'sqlite':
                # SQLite (>=3.35) supports DROP COLUMN but not IF EXISTS.
                cur.execute(f'ALTER TABLE "{table}" DROP COLUMN "custom_permissions";')
            else:
                cur.execute(
                    f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS custom_permissions;'
                )


def reverse_add_custom_permissions(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cur:
        for table in ('sc_users', 'accounts_user'):
            if not _table_exists(cur, vendor, table):
                continue
            if _column_exists(cur, vendor, table, 'custom_permissions'):
                continue
            if vendor == 'sqlite':
                cur.execute(f'ALTER TABLE "{table}" ADD COLUMN "custom_permissions" text NULL;')
            else:
                cur.execute(
                    f'ALTER TABLE "{table}" '
                    f'ADD COLUMN IF NOT EXISTS custom_permissions text NULL;'
                )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_passwordresettoken'),
    ]

    operations = [
        migrations.RunPython(
            forward_drop_custom_permissions,
            reverse_add_custom_permissions,
        ),
    ]
