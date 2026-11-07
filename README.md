# Safe City - AI Traffic E-Challan Enforcement System

Django-based automated traffic-violation enforcement platform: a public E-Challan
lookup portal, a multi-role command dashboard, live AI camera detection, and a
fully automated enforcement pipeline.

## Enforcement Pipeline

```
DETECTION  →  FRAME TRACKING  →  EVIDENCE (5 hard security checks)  →  CHALLAN
```

1. **Detection** - ONNX plate detector + side classifier run on camera frames
   (live cameras and uploaded videos).
2. **Frame tracking** - the plate is matched across the camera's recent frames
   to build a corroborated vehicle track (same plate in ≥ 2 frames, or a
   single frame with ≥ 0.90 plate confidence).
3. **Evidence** - five hard security checks must ALL pass before any challan
   can be issued:
   | # | Check | Requirement |
   |---|-------|-------------|
   | 1 | `plate_readability` | strict Pakistan plate format `AAA-1234` + HD OCR confidence ≥ 0.60 |
   | 2 | `frame_consistency` | **3-frame evidence verified one-by-one** (same full plate in every frame), consistency ≥ 0.80 |
   | 3 | `violation_logic` | side classification matches the camera's violation side (conf ≥ 0.60) + **strict car-only gate** |
   | 4 | `image_evidence` | full frame + **complete plate crop (no half / edge-cut plates)**, crop height ≥ 18 px |
   | 5 | `chain_integrity` | SHA-256 chain digest over camera/plate/images/checks + no duplicate challan for the same plate on the same camera within 24 h |

   Failures never issue a challan: hard failures are rejected, ambiguous cases
   are parked in the OFFICER PORTAL review queue for human triage. There is **no manual or
   officer annotation anywhere** - every challan is issued exclusively by this
   pipeline. The five check results, track metadata and the chain digest are
   stored on the detection record and printed on the challan PDF.
4. **Challan** - auto-issued e-challan with PDF (seven layouts), PSID payment
   ID, QR payload, Excise/NADRA owner lookup, email notification, audit log.

The pipeline also captures a **3-frame sequential evidence burst** (consecutive
frames around the violation, verified one-by-one): officers review all three
frames in the triage viewer, while the challan PDF displays exactly **ONE large
annotated evidence frame** (violation box, plate box, direction arrow) and is
guaranteed to fit a **single A4 page** (page-count verified with pypdf).

## Roles & Login

| Role | Login URL | Identifier |
|------|-----------|------------|
| DIG / SSP / Supervisor / Officer / Audit / IT Support | `/auth/admin/login/` | **Email** |
| Citizen | `/auth/citizen/login/` | **CNIC** |

- Citizens self-register at `/auth/citizen/signup/`
- Staff accounts are created by DIG / IT Support via the Staff Directory
- Bootstrap the first DIG admin: `python manage.py create_dig_admin`
- Optional demo accounts for development: `python manage.py seed_demo_accounts --yes`

## Advertising & Notification Channels

Four audience-scoped channels, managed by IT Support in the **Ads Studio**
(`/portal/it/ads-studio/`); DIG only selects serving state and priority
(`/portal/dig/ads/select/`):

| Channel | Where it appears |
| --- | --- |
| Static post ads | public home, hidden staging section below the search card (slot index `-100`, never rendered) |
| Popup ads | public home only, once per browser session |
| Ticker ads | every staff portal + the public home |
| Push notifications | every staff portal (bell menu + browser notifications, 45s feed) |

## Public Portal Redesign

All public pages (`home`, `detail`, `guest_pay`, `pay_redirect`,
`signed_link_expired`, `_public_ads`) share `templates/public_base.html`
and a lean design system (`static/css/public-shell.css`) matching the login
pages: deep navy background with overlay, glass cards, Inter typography.
The home page carries the navbar brand, the citizen sign-in button, two labelled inputs (plate + CNIC), the search button and the footer.

## Performance

Tuned for ~60 req/s per 2-vCPU node (9 ms median home, 49 ms p99 search).

## Challan Studio & Audit Documents

- **Challan Studio** (`/portal/it/challan-studio/`) - Canva-style block editor
  for challan print layouts. IT Support has full studio access; the DIG portal
  has a select-only page (`/portal/dig/challan-template-select/`).
- **Audit Studio** (`/portal/it/audit-studio/`) - same studio engine for audit
  document layouts (5 built-in government templates: Audit Summary Report,
  Compliance Certificate, Financial Audit Statement, Security & Authentication
  Incident Report, Operational Review Letter). DIG selects the active audit
  layout at `/portal/dig/audit-template-select/`.
- Auditors generate signed audit documents (auditor signature + DIG
  countersignature + SHA-256 digest) at `/portal/audit/generate-document/`.

## Audit & Accountability

Every authentication attempt (account, portal, outcome, **IP address and full
device fingerprint** - browser, OS, device type) is recorded in the login
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
PG_DB=SAFE_CITIES_PROJECT
PG_USER=postgres
PG_PASSWORD=<your password>
PG_HOST=127.0.0.1
PG_PORT=5432
```

Government integrations (Excise, NADRA, payments) run in **sandbox mode** by
default; configure live endpoints in IT Support → System Settings. Payment
settlement only happens through the signed gateway webhook or the
CSRF-protected checkout - no view can mark a challan PAID on its own.

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
limits on auth and public search, RBAC driven by `accounts/permissions.py`, portal
isolation middleware, PII masking for anonymous visitors, signed links for
public challan PDFs, and server-side settlement of every payment.

## What's New (V14 overhaul)

### Enforcement and evidence
- **3-frame sequential evidence (90FPS-style burst)**: video uploads capture the two consecutive frames after every plate hit and verify the plate read frame-by-frame; officers see all three frames in the triage viewer and the capture wall.
- **One A4 page per challan (hard guarantee)**: PDFs are page-count-verified with pypdf; overflow re-renders through the compact layout.
- **One annotated evidence image per challan**: court-ready frame with vehicle box, plate box, wrong-way arrow, camera/area/timestamp telemetry strip.
- **Retrained side classifier**: the original INT8 export was dead (constant output); replaced with a ResNet18 transfer-learned model (94% validation accuracy) with the same NHWC [-1,1] ONNX contract.
- **Duplicate-issuance guard**: `Challan.detection` is now a OneToOneField, enforced at the database level.

### Documents
- **7 challan templates** (modern A4, classic form, legal notice 99-A, digital slip, command brief, secure instrument, Urdu executive) - each single-page, payment channels as ICONS, logos on one side with `|` separator, English-or-Urdu policy (Urdu template is Urdu-primary with English captions; every template carries one small Urdu accessibility hint). The violation type is always the analyzed conclusion from the detection record; the three 2026-11 layouts (command brief, secure instrument, Urdu executive) also show the evidence photo at its natural aspect and add a direction-analysis diagram, a bank-grade security band with tear-off counterfoil, and a Nastaliq executive layout.
- **8 audit report templates** (government classic, executive summary, financial ledger, compliance matrix, incident report, statistical digest, legal affidavit, field inspection) with signature blocks and stamped footers; PDF export for every audit page.
- **IT Support** has full template control (challan studio + audit template manager); **DIG** is select-only.

### Operations
- **CCTV command wall** (DIG/SSP/Supervisor): borderless grid tiles with camera number, area, direction config, status LED, live clock; server-side search by area; double-click opens the video review console with -20s/-10s/+10s/+20s seek, scrub bar and speed control.
- **Officer live capture wall**: every pending capture as a CCTV channel with the full 3-frame sequence, plate overlay and violation banner.
- **Socket.IO realtime push** (`/ws/socket.io`, uvicorn single-worker): new detections, challan events and portal notifications broadcast to role rooms.
- **Portal announcement ticker** driven by the Alerts system (audience-targeted), plus popup and static ads on the public home.
- **Tailwind CSS layered alongside Bootstrap** (preflight off, brand tokens) with bridge component classes (`.tw-table`, `.tw-card`, ...).

### Security
- CSP tightened (no `unsafe-eval`, per-request nonce infrastructure, `object-src 'none'`, `base-uri 'self'`), rate limits on every API endpoint (enroll 5/h, ingest 300/min, heartbeat 120/min, webhook 60/min, PDF 20/min), upload validation (extension + magic-byte/PIL sniff), banner HTML sanitization at the model layer, officer camera-scoping on detection detail, race-condition guards on payments and password resets.
- **Console/DevTools guard** on every page (right-click, F12, Ctrl+Shift+I/J/C/U, console silencing in production) - defense-in-depth on top of the server-side enforcement.

