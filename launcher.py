from __future__ import annotations

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

VENV_DIR = ROOT / '.venv'
REQUIREMENTS = ROOT / 'requirements.txt'
MANAGE_PY = ROOT / 'manage.py'
ENV_FILE = ROOT / '.env'
ENV_EXAMPLE = ROOT / '.env.example'
SETTINGS_MODULE = 'wrongway_system.settings'

MIN_PY = (3, 10)

PG_DB = os.environ.get('PG_DB', 'SAFE_CITIES_PROJECT')
PG_USER = os.environ.get('PG_USER', 'postgres')
PG_PASSWORD = os.environ.get('PG_PASSWORD', 'Admin@2026')
PG_HOST = os.environ.get('PG_HOST', '127.0.0.1')
PG_PORT = os.environ.get('PG_PORT', '5432')


DEFAULT_ENV_EXAMPLE = """# ===== Safe Cities Project -- Environment Configuration =====

DEBUG=True
SECRET_KEY=safe-cities-project-demo-CHANGE-THIS-IN-PRODUCTION-2026
ALLOWED_HOSTS=*

PG_DB=SAFE_CITIES_PROJECT
PG_USER=postgres
PG_PASSWORD=Admin@2026
PG_HOST=127.0.0.1
PG_PORT=5432

ACCOUNT_LOCKOUT_THRESHOLD=5
ACCOUNT_LOCKOUT_DURATION=900

EMAIL_NOTIFICATIONS_ENABLED=False
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@safecities.project
"""


def banner(msg: str, char: str = '=') -> None:
    print(char * 70)
    print('  ' + msg)
    print(char * 70)


def step(msg: str) -> None:
    print('\n>>> ' + msg)


def info(msg: str) -> None:
    print('    ' + msg)


def ok(msg: str) -> None:
    print('    [OK] ' + msg)


def warn(msg: str) -> None:
    print('    [WARN] ' + msg)


def fail(msg: str) -> None:
    print('    [ERROR] ' + msg)


def check_python_version() -> None:
    v = sys.version_info
    if (v.major, v.minor) < MIN_PY:
        print(f'[ERROR] Python {MIN_PY[0]}.{MIN_PY[1]}+ required, '
              f'got {v.major}.{v.minor}.{v.micro}')
        print(f'        Current interpreter: {sys.executable}')
        print('        Install Python 3.10+ from https://www.python.org/downloads/')
        sys.exit(1)
    print(f'[OK] Python {v.major}.{v.minor}.{v.micro} '
          f'({platform.system()} {platform.machine()})')


def venv_python() -> Path | None:
    if os.name == 'nt':
        py = VENV_DIR / 'Scripts' / 'python.exe'
    else:
        py = VENV_DIR / 'bin' / 'python'
    return py if py.exists() else None


def system_python() -> str | None:
    candidates = ['python', 'python3', 'py',
                  'python3.13', 'python3.12', 'python3.11', 'python3.10']
    fallback: str | None = None
    for cmd in candidates:
        try:
            r = subprocess.run([cmd, '--version'],
                               capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                continue
            if fallback is None:
                fallback = cmd
            out = (r.stdout or r.stderr or '').strip()
            parts = out.split()
            if len(parts) < 2:
                continue
            ver_parts = parts[1].split('.')
            if len(ver_parts) < 2:
                continue
            try:
                major, minor = int(ver_parts[0]), int(ver_parts[1])
            except ValueError:
                continue
            if (major, minor) >= MIN_PY:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return fallback


def safe_run(cmd: list, *, label: str = 'command', check: bool = False,
             capture: bool = False, env: dict | None = None,
             timeout: int | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, cwd=str(ROOT),
            check=check,
            capture_output=capture,
            text=capture,
            env=env,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        fail(f'{label}: executable not found -- {e}')
        print('        Hint: ensure Python 3.10+ is installed and on PATH.')
        if os.name == 'nt':
            print('        On Windows, re-run the Python installer and tick '
                  '"Add python.exe to PATH".')
        sys.exit(1)
    except subprocess.TimeoutExpired:
        fail(f'{label}: timed out after {timeout or "(default)"} seconds.')
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        fail(f'{label}: exit code {e.returncode}')
        if capture and e.stderr:
            print('        stderr:')
            for line in str(e.stderr).strip().splitlines()[:25]:
                print('          ' + line)
        sys.exit(1)
    except OSError as e:
        fail(f'{label}: OS error -- {e}')
        sys.exit(1)


def create_venv() -> Path:
    py = venv_python()
    if py:
        return py
    sys_py = system_python()
    if not sys_py:
        fail('Python 3.10+ not found on PATH.')
        print('        Install from https://www.python.org/downloads/ and re-run.')
        sys.exit(1)
    step(f'Creating venv with: {sys_py}')
    safe_run([sys_py, '-m', 'venv', str(VENV_DIR)],
             label='venv creation', check=True)
    py = venv_python()
    if not py:
        fail('venv creation reported success but python executable not found.')
        sys.exit(1)
    return py


def pip_install(py: Path, *args: str) -> subprocess.CompletedProcess:
    return safe_run([str(py), '-m', 'pip', 'install', *args],
                    label='pip install ' + ' '.join(args))


def is_django_installed(py: Path) -> bool:
    r = subprocess.run([str(py), '-c', 'import django'],
                       capture_output=True, cwd=str(ROOT))
    return r.returncode == 0


def manage(py: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    label = f'manage.py {args[0] if args else ""}'.strip()
    return safe_run([str(py), 'manage.py', *args],
                    label=label, check=check)


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return
    step(f'Generating {ENV_FILE.relative_to(ROOT)}')
    if not ENV_EXAMPLE.exists():
        ENV_EXAMPLE.write_text(DEFAULT_ENV_EXAMPLE, encoding='utf-8')
        info(f'Created {ENV_EXAMPLE.relative_to(ROOT)}')
    try:
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        ok(f'Copied -> {ENV_FILE.relative_to(ROOT)}')
    except OSError as e:
        warn(f'Could not write {ENV_FILE}: {e}')


def load_dotenv() -> None:
    if not ENV_FILE.exists():
        return
    try:
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError as e:
        warn(f'Could not read {ENV_FILE}: {e}')


def refresh_pg_config() -> None:
    global PG_DB, PG_USER, PG_PASSWORD, PG_HOST, PG_PORT
    PG_DB = os.environ.get('PG_DB', PG_DB)
    PG_USER = os.environ.get('PG_USER', PG_USER)
    PG_PASSWORD = os.environ.get('PG_PASSWORD', PG_PASSWORD)
    PG_HOST = os.environ.get('PG_HOST', PG_HOST)
    PG_PORT = os.environ.get('PG_PORT', PG_PORT)


def reset_db_schema(py: Path) -> None:
    script = (
        "import os, django; "
        f"os.environ.setdefault('DJANGO_SETTINGS_MODULE','{SETTINGS_MODULE}'); "
        "django.setup(); "
        "from django.db import connection; "
        "c = connection.cursor(); "
        "c.execute('DROP SCHEMA IF EXISTS public CASCADE;'); "
        "c.execute('CREATE SCHEMA public;'); "
        "c.execute('GRANT ALL ON SCHEMA public TO postgres;'); "
        "c.execute('GRANT ALL ON SCHEMA public TO public;')"
    )
    safe_run([str(py), '-c', script], label='reset_db_schema', check=True)


_PREFLIGHT_SCRIPT = r'''
import os, sys
try:
    import psycopg2
except ImportError:
    print("NO_PSYCOPG2", flush=True)
    sys.exit(2)

try:
    conn = psycopg2.connect(
        host=os.environ["PG_HOST"], port=os.environ["PG_PORT"],
        dbname=os.environ["PG_DB"], user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"], connect_timeout=5,
    )
    conn.close()
    print("OK", flush=True)
    sys.exit(0)
except psycopg2.OperationalError as e:
    print("ERR:" + str(e), flush=True)
    sys.exit(1)
'''


_CREATE_DB_SCRIPT = r'''
import os, sys
from psycopg2 import sql

try:
    import psycopg2
except ImportError:
    print("NO_PSYCOPG2", flush=True)
    sys.exit(2)

PG_HOST = os.environ["PG_HOST"]
PG_PORT = os.environ["PG_PORT"]
PG_DB = os.environ["PG_DB"]
PG_USER = os.environ["PG_USER"]
PG_PASSWORD = os.environ["PG_PASSWORD"]

last_err = None
for db_attempt in ["postgres", "template1"]:
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=db_attempt,
                                user=PG_USER, password=PG_PASSWORD,
                                connect_timeout=5)
        conn.autocommit = True
        cur = conn.cursor()

        try:
            cur.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(PG_USER)),
                (PG_PASSWORD,),
            )
            print("[OK] Created PostgreSQL user: " + PG_USER, flush=True)
        except psycopg2.Error as e:
            msg = str(e).lower()
            if "already exists" not in msg:
                print("[WARN] CREATE USER skipped: " + str(e), flush=True)

        try:
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(PG_DB), sql.Identifier(PG_USER)))
            print("[OK] Created PostgreSQL database: " + PG_DB, flush=True)
        except psycopg2.Error as e:
            msg = str(e).lower()
            if "already exists" in msg:
                print("[OK] Database already exists: " + PG_DB, flush=True)
            else:
                print("[WARN] CREATE DATABASE failed: " + str(e), flush=True)

        cur.close()
        conn.close()
        sys.exit(0)
    except psycopg2.OperationalError as e:
        last_err = e
        continue

print("ERR:" + str(last_err), flush=True)
sys.exit(1)
'''


def _pg_env() -> dict:
    env = os.environ.copy()
    env.update({
        'PG_HOST': PG_HOST,
        'PG_PORT': str(PG_PORT),
        'PG_DB': PG_DB,
        'PG_USER': PG_USER,
        'PG_PASSWORD': PG_PASSWORD,
        'DJANGO_SETTINGS_MODULE': SETTINGS_MODULE,
    })
    return env


def postgres_preflight(py: Path) -> bool:
    step('PostgreSQL preflight')
    r = safe_run([str(py), '-c', _PREFLIGHT_SCRIPT],
                 label='psycopg2 preflight',
                 capture=True, env=_pg_env(), timeout=30)
    out = (r.stdout or '').strip()

    if r.returncode == 0 and out.splitlines()[-1:] == ['OK']:
        ok(f'Connected: {PG_DB}@{PG_HOST}:{PG_PORT} as {PG_USER}')
        return True

    if 'NO_PSYCOPG2' in out:
        warn('psycopg2 not installed in venv -- run setup first.')
        return False

    err_lines = [ln for ln in out.splitlines() if ln.startswith('ERR:')]
    err = err_lines[-1][len('ERR:'):].strip() if err_lines else out
    err_low = err.lower()

    if 'does not exist' in err_low and 'database' in err_low:
        info(f'Database "{PG_DB}" not found -- attempting auto-create...')
        return create_database_if_missing(py)

    if 'password' in err_low or 'authentication' in err_low:
        fail('PostgreSQL authentication failed.')
        masked = '*' * len(PG_PASSWORD) if PG_PASSWORD else '(empty)'
        print(f'        Configured: user={PG_USER} password={masked} '
              f'host={PG_HOST} port={PG_PORT}')
        print('        Remediation:')
        print('          1) Set the postgres user password:')
        print("             sudo -u postgres psql -c "
              "\"ALTER USER postgres WITH PASSWORD 'Admin@2026';\"")
        print('          2) Or edit wrongway_system/.env to match your '
              'local PostgreSQL credentials.')
        print('          3) On Windows, open psql as the postgres user and '
              'run the ALTER USER statement above.')
        return False

    if ('could not connect' in err_low or 'connection refused' in err_low
            or 'timed out' in err_low or 'no route' in err_low
            or 'network is unreachable' in err_low):
        fail('Cannot reach PostgreSQL server.')
        print(f'        Target: {PG_HOST}:{PG_PORT}')
        print('        Remediation:')
        if os.name == 'nt':
            print('          1) Start the PostgreSQL service:')
            print('             net start postgresql-x64-15   '
                  '(adjust version as needed)')
            print('             -- OR open Services.msc and start the '
                  'PostgreSQL service.')
            print('          2) Or run via the pg_ctl binary bundled with the '
                  'installer:')
            print('             "C:\\Program Files\\PostgreSQL\\15\\bin\\'
                  'pg_ctl.exe" start -D "C:\\Program Files\\PostgreSQL\\15\\data"')
        else:
            print('          1) Start the PostgreSQL service:')
            print('             sudo systemctl start postgresql     '
                  '# systemd (Ubuntu/Debian/RHEL)')
            print('             sudo service postgresql start       '
                  '# SysV init')
            print('             pg_ctl -D /var/lib/postgresql/data start   '
                  '# manual')
            print('             brew services start postgresql       # macOS Homebrew')
            print('          2) Verify it is listening:')
            print('             ss -tlnp | grep 5432   # Linux')
            print('             lsof -iTCP:5432 -sTCP:LISTEN   # macOS')
            print('          3) Or run PostgreSQL in Docker:')
            print('             docker run -d --name pg -p 5432:5432 '
                  '-e POSTGRES_PASSWORD=Admin@2026 '
                  '-e POSTGRES_DB=safe_cities_project postgres:15')
        return False

    warn(f'PostgreSQL preflight issue: {err}')
    return False


def create_database_if_missing(py: Path) -> bool:
    r = safe_run([str(py), '-c', _CREATE_DB_SCRIPT],
                 label='auto-create DB+user',
                 capture=True, env=_pg_env(), timeout=60)
    out = (r.stdout or '').strip()

    for line in out.splitlines():
        if line.strip():
            info(line)

    if r.returncode != 0:
        err_out = out
        if err_out.startswith('ERR:'):
            err_out = err_out[len('ERR:'):].strip()
        fail('Auto-create failed: ' + err_out)
        print('        Common causes:')
        print('          1) The postgres superuser password is not '
              f'"{PG_PASSWORD}".')
        print('          2) PostgreSQL is configured with peer auth '
              '(no password accepted).')
        print('        Manual remediation:')
        print(f'          sudo -u postgres psql -c "CREATE DATABASE {PG_DB};"')
        print(f'          sudo -u postgres psql -c '
              f'"CREATE USER {PG_USER} WITH PASSWORD \'{PG_PASSWORD}\';"')
        print(f'          sudo -u postgres psql -c '
              f'"GRANT ALL PRIVILEGES ON DATABASE {PG_DB} TO {PG_USER};"')
        return False

    r2 = safe_run([str(py), '-c', _PREFLIGHT_SCRIPT],
                  label='post-create verify',
                  capture=True, env=_pg_env(), timeout=30)
    if r2.returncode == 0:
        ok(f'Verified: {PG_DB} is now reachable.')
        return True
    warn('DB create reported success but verify failed.')
    return False


def setup() -> None:
    banner('SAFE CITIES PROJECT -- Setup')
    check_python_version()

    ensure_env_file()
    load_dotenv()
    refresh_pg_config()

    step('Virtualenv')
    py = create_venv()
    ok(f'venv: {py}')

    step('Pip upgrade')
    pip_install(py, '--upgrade', 'pip')

    step('Dependencies')
    if is_django_installed(py):
        ok('Django already installed -- skipping pip install -r')
    else:
        r = pip_install(py, '-r', 'requirements.txt')
        if r.returncode != 0:
            fail('pip install failed. See output above.')
            sys.exit(1)

    pg_ok = postgres_preflight(py)

    if pg_ok:
        step('Schema reset')
        try:
            reset_db_schema(py)
            ok('public schema dropped + recreated')
        except SystemExit:
            raise
        except Exception as e:
            warn(f'Schema reset skipped: {e}')
    else:
        print('\n[WARN] PostgreSQL not reachable -- skipping schema reset, '
              'migrate, collectstatic, and seed.')
        print('       Fix PostgreSQL (see hints above), then re-run:')
        print('           python launcher.py setup')

    if pg_ok:
        step('Migrate')
        r = manage(py, 'migrate')
        if r.returncode != 0:
            fail('Migration failed. Check PostgreSQL is running and '
                 'credentials are correct (see wrongway_system/.env).')
            sys.exit(1)

        step('Collect static files')
        r = manage(py, 'collectstatic', '--noinput')
        if r.returncode != 0:
            warn('collectstatic failed -- server will still run, but static '
                 'assets may be missing.')
        else:
            ok('Static files collected')

        step('Seed DIG admin')
        r = manage(py, 'create_dig_admin')
        if r.returncode != 0:
            warn('create_dig_admin returned non-zero -- check output above '
                 '(may be safe to ignore if admin already exists).')

    banner('SETUP COMPLETE')
    print('  Next: python launcher.py run    (or .\\run.bat on Windows)')


def _env_flag(name: str) -> bool:
    return os.environ.get(name, '').strip().lower() in ('1', 'true', 'yes', 'on', 'y', 't')


def uvicorn_available(py: Path) -> bool:
    try:
        r = subprocess.run([str(py), '-c', 'import uvicorn'],
                           capture_output=True, cwd=str(ROOT))
    except OSError:
        return False
    return r.returncode == 0


def run_server(realtime: bool = False) -> None:
    banner('SAFE CITY FYP -- Run server')
    check_python_version()

    ensure_env_file()
    load_dotenv()
    refresh_pg_config()

    py = venv_python()
    if not py:
        print('[INFO] venv not found -- running setup first...')
        setup()
        py = venv_python()
        if not py:
            fail('Setup completed but venv still missing.')
            sys.exit(1)

    if not is_django_installed(py):
        print('[INFO] Django not installed -- installing dependencies...')
        r = pip_install(py, '-r', 'requirements.txt')
        if r.returncode != 0:
            fail('pip install failed.')
            sys.exit(1)

    postgres_preflight(py)

    step('Migrate (idempotent)')
    manage(py, 'migrate')

    step('Collect static (idempotent)')
    manage(py, 'collectstatic', '--noinput')

    # Realtime mode (--realtime flag or REALTIME=1 env): serve the ASGI app
    # (Django + Socket.IO at /ws/socket.io) with uvicorn. SINGLE WORKER is
    # REQUIRED: the pipeline emits Socket.IO events in-process, so the
    # server and the emits must share one process (Socket.IO requires a single shared process).
    if realtime or _env_flag('REALTIME'):
        if uvicorn_available(py):
            port = os.environ.get('PORT', '').strip() or '8000'
            banner(f'Realtime server (uvicorn ASGI, 1 worker) -- http://127.0.0.1:{port}/')
            print('  Socket.IO endpoint : /ws/socket.io')
            print('  Single worker is REQUIRED for in-process Socket.IO emits.')
            print('  Press CTRL+C to stop.\n')

            safe_run(
                [str(py), '-m', 'uvicorn', 'wrongway_system.asgi:application',
                 '--host', '0.0.0.0', '--port', str(port),
                 '--workers', '1', '--log-level', 'info'],
                label='uvicorn realtime server',
            )
            return
        warn('uvicorn not installed -- falling back to the Django dev server.')
        print('        Enable realtime later with: '
              'pip install uvicorn  (then: python launcher.py realtime)')

    banner('Starting Django dev server -- http://127.0.0.1:8000/')
    print('  Press CTRL+C to stop.\n')

    safe_run([str(py), 'manage.py', 'runserver'], label='runserver')


def auto() -> None:
    setup()
    print('\n')
    run_server()


def fresh() -> None:
    banner('FRESH RESET -- DESTRUCTIVE', char='!')
    print('  This will:')
    print(f'    - DELETE {VENV_DIR.relative_to(ROOT)}/  '
          '(virtualenv + all installed packages)')
    print('    - DROP the public schema in PostgreSQL '
          '(ALL DATA WILL BE LOST)')
    print('    - Re-create schema, run migrations, seed DIG admin')
    print()

    try:
        answer = input(
            'This will delete venv/ and DROP the public schema. '
            'Continue? [y/N] '
        ).strip().lower()
    except EOFError:
        answer = ''

    if answer not in ('y', 'yes'):
        print('Aborted. No changes made.')
        sys.exit(0)

    ensure_env_file()
    load_dotenv()
    refresh_pg_config()

    if VENV_DIR.exists():
        print(f'\n>>> Deleting {VENV_DIR.relative_to(ROOT)}/ ...')
        shutil.rmtree(VENV_DIR, ignore_errors=True)
        ok('venv removed')

    py = create_venv()
    pip_install(py, '--upgrade', 'pip')
    pip_install(py, '-r', 'requirements.txt')

    pg_ok = postgres_preflight(py)

    if pg_ok:
        try:
            reset_db_schema(py)
            ok('public schema dropped + recreated')
        except SystemExit:
            raise
        except Exception as e:
            warn(f'Schema reset failed: {e}')

        r = manage(py, 'migrate')
        if r.returncode != 0:
            fail('Migration failed.')
            sys.exit(1)

        manage(py, 'collectstatic', '--noinput')
        manage(py, 'create_dig_admin')

    banner('FRESH SETUP COMPLETE')
    print('  Next: python launcher.py run')


def show_help() -> None:
    print("""Safe City launcher

Usage: python launcher.py <command>

Commands:
  run          Start the stack (PostgreSQL check, migrations, collectstatic, runserver)
  setup        Full fresh setup (venv packages, DB create, migrations, seed admin)
  migrate      Apply database migrations
  seedadmin    Create the default DIG admin account
  static       Collect static files
  test         Run the Django test suite
  status       Show stack status (DB + server)
  help         Show this help
""")


def main() -> None:
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    mode = sys.argv[1].lower().lstrip('-')
    if mode == 'setup':
        setup()
    elif mode in ('run', 'start', 'serve'):
        run_server()
    elif mode in ('realtime', 'run-realtime'):
        run_server(realtime=True)
    elif mode in ('auto', 'all'):
        auto()
    elif mode in ('fresh', 'reset'):
        fresh()
    elif mode in ('help', 'h', '?'):
        show_help()
    else:
        print(f'Unknown mode: {sys.argv[1]}')
        print('Try: python launcher.py --help')
        sys.exit(1)


if __name__ == '__main__':
    main()

