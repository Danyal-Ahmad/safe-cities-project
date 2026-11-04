# Safe City — AI Traffic E-Challan Enforcement System

Django-based automated traffic-violation enforcement platform: a public E-Challan
lookup portal, a multi-role command dashboard, live AI camera detection, and a
four-stage evidence pipeline (DETECTION → TRACKING → EVIDENCE → CHALLAN).

## Roles & Login

| Role | Login URL | Identifier |
|------|-----------|------------|
| DIG / SSP / Supervisor / Officer / Audit / IT Support | `/auth/admin/login/` | **Email** |
| Citizen | `/auth/citizen/login/` | **CNIC** |

- Citizens self-register at `/auth/citizen/signup/`
- Staff accounts are created by DIG / IT Support via the Staff Directory
- The first superuser: `python manage.py createsuperuser`

## Quick Start

### Requirements
- Python 3.10+
- PostgreSQL running locally

### Setup (Windows)
```bat
setup.bat     :: creates .venv, installs deps, runs migrations
run.bat       :: starts the dev server at http://127.0.0.1:8000/
```

### Setup (Linux / macOS)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit DB credentials
python manage.py migrate
python manage.py runserver
```

## AI Pipeline

`DETECTION → TRACKING → EVIDENCE (5-step validation) → CHALLAN`

1. **Detection** — ONNX vehicle/plate models run on live camera frames
2. **Tracking** — per-camera violation tracking with frame timelines
3. **Evidence** — 5-step validation (plate readability, direction, confidence
   gate, deduplication cooldown, rate limiting) before a challan is drafted
4. **Challan** — auto-generated e-challan with PDF evidence sheet, PSID payment
   ID, appeals and online payment integration

Model files live in `models/` (ONNX, int8 quantized).

## URL Map

| Path | Purpose |
|------|---------|
| `/` | Public challan search (plate / CNIC) |
| `/auth/admin/login/` | Staff sign-in |
| `/auth/citizen/login/` | Citizen sign-in |
| `/portal/dig/` | DIG command center |
| `/portal/ssp/` | SSP dashboard |
| `/portal/supervisor/` | Supervisor dashboard |
| `/portal/officer/` | Officer review queue & live tracking |
| `/portal/audit/` | Audit portal |
| `/portal/it/` | IT support & system settings |
| `/portal/citizen/` | Citizen E-challan dashboard |
| `/video/` | Video upload & batch processing |
| `/realtime/` | Realtime JSON APIs |

## Configuration

Copy `.env.example` to `.env` and set:

```
DEBUG=True
SECRET_KEY=<generate a strong key>
ALLOWED_HOSTS=127.0.0.1,localhost
PG_DB=SAFE_CITY_FYP
PG_USER=postgres
PG_PASSWORD=<your password>
PG_HOST=127.0.0.1
PG_PORT=5432
```

Government integrations (Excise, NADRA, payments) run in **sandbox mode** by
default; configure live endpoints in IT Support → System Settings.

## Project Layout

```
accounts/        Users, roles, permissions, profiles
admin/           DIG / SSP / Supervisor / Officer / Audit / IT portals
appeals/         Challan appeal workflow
auth_portal/     Login / signup / password reset
camera_worker/   RTSP camera enrollment & worker daemon
cameras/         Camera registry & health
challans/        E-challan lifecycle, PDF service, payments
citizen/         Citizen portal
detections/      AI detection engine & evidence validation
integrations/    Excise / NADRA / payment gateways
models/          ONNX AI models
payments/        Payment webhooks & APIs
realtime/        Live tracking JSON APIs
static/          Design system (CSS/JS/img)
templates/       All UI templates
video_processor/ Batch video upload & processing
wrongway_system/ Django project settings & security
```

## Security Notes

- Argon2 password hashing, rate-limited public search and auth
- Role-based access control driven by `permission.json`
- Signed, expiring links for public challan views
- All payment webhooks verified server-side
