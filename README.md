# Safe City — AI Traffic E-Challan Enforcement System

Django-based automated traffic-violation enforcement platform: a public E-Challan
lookup portal, a multi-role command dashboard, live AI camera detection, and a
fully automated enforcement pipeline.

## Enforcement Pipeline

```
DETECTION  →  FRAME TRACKING  →  EVIDENCE (5 hard security checks)  →  CHALLAN
```

1. **Detection** — ONNX plate detector + side classifier run on camera frames
   (live cameras and uploaded videos).
2. **Frame tracking** — the plate is matched across the camera's recent frames
   to build a corroborated vehicle track. Videos are processed with a
   **90fps-density burst sampler**: on a candidate violation frame the
   processor reads consecutive frames and verifies the plate **one-by-one in
   at least 3 frames** before evidence is accepted.
3. **Evidence** — five hard security checks must ALL pass before any challan
   can be issued:
   | # | Check | Requirement |
   |---|-------|-------------|
   | 1 | `plate_readability` | strict Pakistan plate format `AAA-1234` + HD OCR confidence ≥ 0.60 |
   | 2 | `frame_consistency` | **3-frame evidence verified one-by-one** (same full plate in every frame), consistency ≥ 0.80 |
   | 3 | `violation_logic` | side classification matches the camera's violation side (conf ≥ 0.60) + **strict car-only gate** |
   | 4 | `image_evidence` | full frame + **complete plate crop (no half / edge-cut plates)**, crop height ≥ 18 px |
   | 5 | `chain_integrity` | SHA-256 chain digest over camera/plate/images/checks + no duplicate challan for the same plate on the same camera within 24 h |

   Failures never issue a challan: hard failures are rejected, ambiguous cases
   are parked in the review queue for DIG oversight. There is **no manual or
   officer annotation anywhere** — every challan is issued exclusively by this
   pipeline. The five check results, track metadata and the chain digest are
   stored on the detection record and printed on the challan PDF.
4. **Challan** — auto-issued e-challan with PDF (five government layouts),
   PSID payment ID, QR payload, Excise/NADRA owner lookup, email notification,
   audit log. Layouts are controlled by **IT Support in the Challan Studio**
   (create / edit / duplicate / redesign / activate); the **DIG selects** the
   active layout for every challan.

## Roles & Login

| Role | Login URL | Identifier |
|------|-----------|------------|
| DIG / SSP / Supervisor / Officer / Audit / IT Support | `/auth/admin/login/` | **Email** |
| Citizen | `/auth/citizen/login/` | **CNIC** |

- Citizens self-register at `/auth/citizen/signup/`
- Staff accounts are created by DIG / IT Support via the Staff Directory
- Bootstrap the first DIG admin: `python manage.py create_dig_admin`
- Optional demo accounts for development: `python manage.py seed_demo_accounts --yes`

## Challan Studio & Audit Documents

- **Challan Studio** (`/portal/it/challan-studio/`) — Canva-style block editor
  for challan print layouts. IT Support has full studio access; the DIG portal
  has a select-only page (`/portal/dig/challan-template-select/`).
- **Audit Studio** (`/portal/it/audit-studio/`) — same studio engine for audit
  document layouts (5 built-in government templates: Audit Summary Report,
  Compliance Certificate, Financial Audit Statement, Security & Authentication
  Incident Report, Operational Review Letter). DIG selects the active audit
  layout at `/portal/dig/audit-template-select/`.
- Auditors generate signed audit documents (auditor signature + DIG
  countersignature + SHA-256 digest) at `/portal/audit/generate-document/`.

## Audit & Accountability

Every authentication attempt (account, portal, outcome, **IP address and full
device fingerprint** — browser, OS, device type) is recorded in the login
events ledger (`/portal/audit/login-events/`). Every upload (videos with
tamper-evident SHA-256 digests, template changes) is audited at
`/portal/audit/uploads/`. All staff mutations are written to the audit log
with actor, IP and device.

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
python manage.py create_dig_admin
python manage.py runserver
```

Full reset (destructive): `python launcher.py fresh`

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

## Tests

```bash
python manage.py test detections accounts auth_portal challans video_processor
```

Covers the full pipeline (all-pass issuance, each failing check, duplicate
blocking, tamper-evident hashing), RBAC and portal isolation for every role,
IDOR scoping, PII masking, payment integrity, XSS/SQLi/CSRF hardening, and an
end-to-end video dry run.

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
default; configure live endpoints in IT Support → System Settings. Payment
settlement only happens through the signed gateway webhook or the
CSRF-protected checkout — no view can mark a challan PAID on its own.

## Project Layout

```
accounts/        Users, roles, permissions, profiles
admin/           DIG / SSP / Supervisor / Officer / Audit / IT portals
appeals/         Challan appeal workflow
auth_portal/     Login / signup / password reset
camera_worker/   RTSP camera enrollment & worker daemon
cameras/         Camera registry & health
challans/        E-challan lifecycle, PDF service, public portal
citizen/         Citizen portal
detections/      AI engine, enforcement pipeline, evidence chain
integrations/    Excise / NADRA / payment gateways
models/          ONNX AI models
payments/        Payment webhooks & checkout
realtime/        Live tracking JSON APIs + shared chart endpoints
static/          Design system + per-page CSS/JS (no inline styles)
templates/       All UI templates
video_processor/ Batch video upload & processing
wrongway_system/ Django project settings & security
```

## Security

See [SECURITY.md](SECURITY.md). Highlights: Argon2 password hashing, rate
limits on auth and public search, RBAC driven by `permission.json`, portal
isolation middleware, PII masking for anonymous visitors, signed links for
public challan PDFs, and server-side settlement of every payment.
