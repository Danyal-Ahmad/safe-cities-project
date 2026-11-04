# Security Model

This document describes the hardening applied across the system and the
guarantees each layer provides.

## Enforcement pipeline integrity

- A challan can **only** be created by `detections.pipeline.process_detection`
  after all five evidence checks pass. No view, officer, or admin can issue a
  challan by hand — the manual-challan and annotation surfaces were removed.
- Every issued challan carries a tamper-evident SHA-256 chain digest over the
  camera, plate, both evidence images and the check results. Altering any
  input changes the digest stored on the detection record.
- A duplicate challan for the same plate on the same camera within 24 h fails
  `chain_integrity` and is parked for review instead of issuing.

## Authentication & sessions

- Argon2 password hashing (PBKDF2 fallbacks), 12-char minimum via Django
  validators, similarity/common-password checks.
- Account lockout after 5 failed logins (15 min), enforced by middleware and
  the auth backend.
- Sessions: 8 h sliding, HttpOnly, SameSite=Lax, Secure in production.
- Rate limits: 8/min per IP on login/forgot POSTs, 120/min on portal POSTs,
  20/min on the public challan search, plus `django-ratelimit` on auth views.

## Password reset flows

- **Citizens** submit their CNIC; if an account exists a single-use token is
  created and the reset link is **sent to the registered email only**. The
  token is never rendered into any response, and the result message is
  identical whether or not the account exists (anti-enumeration). Tokens
  expire after 2 h and are single-use.
- **Staff** cannot self-reset: a request is created and DIG is notified
  in-app; DIG performs the reset from the admin-reset screen. The previous
  unauthenticated twin endpoint was removed.
- Tests cover: token never in response body, email carries the link, used
  tokens rejected, generic messaging for unknown CNICs.

## Public portal (no login)

- Search results partially mask owner names for anonymous visitors.
- Challan detail pages **mask PII in memory** for guests: owner name is
  shortened, CNIC/phone are dotted out, addresses/chassis are truncated. The
  database rows are never modified by masking.
- Guest appeals require the 13-digit CNIC linked to the challan — which is no
  longer displayed, so an attacker must already know it.
- Challan PDFs require either an authenticated owner/staff session or a
  **signed (HMAC) token**. Ticket numbers and numeric IDs are not accepted
  as tokens.
- Anonymous visitors are rate limited on search (bypass-resistant defaults;
  trusted-proxy XFF handling is required before deploying behind a proxy).

## Payments

- Settlement happens in exactly two places: the HMAC-verified gateway webhook,
  or the demo checkout when the visitor explicitly confirms — and the demo
  checkout only settles a **pending PaymentTransaction** whose reference was
  issued by `initiate_payment`. Forged references are rejected, references
  are single-use, and every settlement is audit-logged.
- `guest_pay` never marks a challan PAID. `guest_pay_done` is display-only.
- Cash and bank-transfer methods are excluded from online payment.

## RBAC & isolation

- `permission.json` is the single source of truth; `accounts/permissions.py`
  mirrors it (auto-generated). Roles: DIG > SSP > Supervisor > Officer,
  plus Audit and IT (staff), and USER (citizen).
- Every view is decorated with role/permission checks; payment operations are
  DIG+IT; appeal decisions are bound to stage + role + pending status; camera
  snapshots/streams are limited to the officer's assigned cameras.
- `PortalIsolationMiddleware` hard-locks each `/portal/<role>/` prefix to that
  exact role, defense-in-depth on top of the view decorators.
- Cross-portal JSON endpoints (charts, KPIs) live under `/realtime/` with
  staff-level decorators so portal isolation never blocks legitimate
  cross-portal fetches, while citizens are excluded.
- Officers see only detections/challans from cameras assigned to them; DIG,
  SSP and supervisors see everything (rank hierarchy).

## Transport & headers

Production (`DEBUG=False`) enables: HSTS (1 year, preload), SSL redirect,
secure cookies, CSP with `frame-ancestors 'none'`, nosniff, X-Frame-Options
SAMEORIGIN, Referrer-Policy and Permissions-Policy headers. A strong
`SECRET_KEY` and a non-wildcard `ALLOWED_HOSTS` are enforced at boot.

## Input handling

- All ORM access is parameterized (no string-built SQL).
- Public search inputs are sanitized server-side (plate/CNIC character
  classes, length caps) and auto-escaped by the template engine.
- File uploads: size caps per route (5 MB default, 50 MB media, 200 MB
  videos), content-type checks on camera ingest, upload paths constrained
  to their directories (path traversal guarded — covered by tests).
- `RequestSizeLimitMiddleware` rejects oversized bodies before parsing.

## Known deployment requirements

- Run behind a TLS-terminating proxy only with `TRUST_PROXY` awareness for
  X-Forwarded-For; the in-sandbox rate limiter uses the socket peer address.
- `locmem` rate limiting is per-process; switch
  `RATELIMIT_USE_CACHE`/`CACHES` to Redis for multi-worker deployments.
- Backups (IT portal) serialize model data including password hashes —
  restrict backup downloads to trusted IT staff and store them encrypted.
