# Idempotent Shift table - works whether user table is accounts_user or sc_users

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


SQL = r"""
DO $$
DECLARE
  user_table text;
BEGIN
  IF to_regclass('public.sc_users') IS NOT NULL THEN
    user_table := 'sc_users';
  ELSIF to_regclass('public.accounts_user') IS NOT NULL THEN
    user_table := 'accounts_user';
  ELSE
    RAISE EXCEPTION 'Neither sc_users nor accounts_user exists - run accounts migrations first';
  END IF;

  CREATE TABLE IF NOT EXISTS dig_portal_shift (
    id BIGSERIAL PRIMARY KEY
  );

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'dig_portal_shift' AND column_name = 'start_time'
  ) THEN
    ALTER TABLE dig_portal_shift ADD COLUMN start_time timestamptz NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'dig_portal_shift' AND column_name = 'end_time'
  ) THEN
    ALTER TABLE dig_portal_shift ADD COLUMN end_time timestamptz NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'dig_portal_shift' AND column_name = 'created_at'
  ) THEN
    ALTER TABLE dig_portal_shift ADD COLUMN created_at timestamptz NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'dig_portal_shift' AND column_name = 'officer_id'
  ) THEN
    ALTER TABLE dig_portal_shift ADD COLUMN officer_id bigint NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'dig_portal_shift' AND column_name = 'assigned_by_id'
  ) THEN
    ALTER TABLE dig_portal_shift ADD COLUMN assigned_by_id bigint NULL;
  END IF;

  UPDATE dig_portal_shift SET start_time = NOW() WHERE start_time IS NULL;
  UPDATE dig_portal_shift SET end_time = NOW() WHERE end_time IS NULL;
  UPDATE dig_portal_shift SET created_at = NOW() WHERE created_at IS NULL;

  BEGIN
    ALTER TABLE dig_portal_shift ALTER COLUMN start_time SET NOT NULL;
  EXCEPTION WHEN others THEN NULL;
  END;
  BEGIN
    ALTER TABLE dig_portal_shift ALTER COLUMN end_time SET NOT NULL;
  EXCEPTION WHEN others THEN NULL;
  END;

  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'dig_portal_shift_assigned_by_id_fkey') THEN
    ALTER TABLE dig_portal_shift DROP CONSTRAINT dig_portal_shift_assigned_by_id_fkey;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'dig_portal_shift_officer_id_fkey') THEN
    ALTER TABLE dig_portal_shift DROP CONSTRAINT dig_portal_shift_officer_id_fkey;
  END IF;

  EXECUTE format(
    'ALTER TABLE dig_portal_shift ADD CONSTRAINT dig_portal_shift_assigned_by_id_fkey
     FOREIGN KEY (assigned_by_id) REFERENCES %I(id) DEFERRABLE INITIALLY DEFERRED',
    user_table
  );
  EXECUTE format(
    'ALTER TABLE dig_portal_shift ADD CONSTRAINT dig_portal_shift_officer_id_fkey
     FOREIGN KEY (officer_id) REFERENCES %I(id) DEFERRABLE INITIALLY DEFERRED',
    user_table
  );

  CREATE INDEX IF NOT EXISTS dig_portal__officer_6deeb1_idx
    ON dig_portal_shift (officer_id, start_time);
  CREATE INDEX IF NOT EXISTS dig_portal__start_t_d31604_idx
    ON dig_portal_shift (start_time, end_time);
END $$;
"""


def _run_postgres_shift_sql(apps, schema_editor):
    """The DDL above is PL/pgSQL and only valid on PostgreSQL (production),
    where it idempotently merges/upgrades a possibly-preexisting shift table.
    On other backends (e.g. SQLite in USE_SQLITE_DRY_RUN / CI) there is no
    legacy table to merge, so just create the table the normal Django way."""
    if schema_editor.connection.vendor != 'postgresql':
        # Non-PostgreSQL path (USE_SQLITE_DRY_RUN / CI only). Create the table
        # with exactly the columns state_operations.CreateModel declares above,
        # named to match what the later 0013 rename migration expects
        # ('dig_portal_shift' -> its eventual db_table).
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                'CREATE TABLE IF NOT EXISTS "dig_portal_shift" ('
                '"id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, '
                '"start_time" datetime NOT NULL, '
                '"end_time" datetime NOT NULL, '
                '"created_at" datetime NOT NULL, '
                '"assigned_by_id" integer NULL, '
                '"officer_id" integer NOT NULL'
                ')'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS "dig_portal__officer_6deeb1_idx" '
                'ON "dig_portal_shift" ("officer_id", "start_time")'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS "dig_portal__start_t_d31604_idx" '
                'ON "dig_portal_shift" ("start_time", "end_time")'
            )
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0006_notification_payment_verification_category'),
        ('accounts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Shift',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('start_time', models.DateTimeField()),
                        ('end_time', models.DateTimeField()),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('assigned_by', models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            related_name='shifts_assigned',
                            to=settings.AUTH_USER_MODEL,
                        )),
                        ('officer', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='shifts',
                            to=settings.AUTH_USER_MODEL,
                        )),
                    ],
                    options={
                        'ordering': ['-start_time'],
                        'indexes': [
                            models.Index(fields=['officer', 'start_time'], name='dig_portal__officer_6deeb1_idx'),
                            models.Index(fields=['start_time', 'end_time'], name='dig_portal__start_t_d31604_idx'),
                        ],
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    _run_postgres_shift_sql,
                    migrations.RunPython.noop,
                ),
            ],
        ),
    ]
