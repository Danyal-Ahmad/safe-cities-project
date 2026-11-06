# SAFE CITIES PROJECT — Security Audit & Hardening Report

**Target:** `/home/z/my-project/safe-cities-project` — traffic-violation e-challan platform
(Django 5.0, PostgreSQL, ASGI + Socket.IO realtime layer)
**Pass:** 2026 hardening pass (black-hat audit → defensive fix cycle)
**Auditor posture:** offensive review of every public and authenticated surface,
followed by fixes restricted to the file set owned by this pass.
**Regression tooling:** `python3 scripts/pen_test.py` (44 assertions, exit code
0/1) and `python3 manage.py test challans accounts auth_portal --keepdb`.

---

## 1. Methodology

1. **Recon** — full read of URL routing (`wrongway_system/urls.py` + 9 app
   url modules), middleware stack, settings, template inventory, static JS.
2. **Threat modelling** (§2) — assets, actors, entry points.
3. **Attack-pattern sweep**, one class at a time: IDOR, injection (SQL / XSS /
   template), auth & token lifecycle, upload handling, mass assignment, SSRF,
   clickjacking, information leakage, race conditions (TOCTOU), enumeration.
4. **Fix** — changes confined to the owned file list; every fix cross-checked
   against the existing verified security controls (Argon2, lockout, HMAC
   webhook, signed links, PII masking, portal isolation…) so nothing regressed.
5. **Proof** — `scripts/pen_test.py` drives the Django test client with
   `DEBUG=False` (production CSP/cookie paths) against the real settings
   module; `manage.py test` guards the behavioural suite.

## 2. Threat model

| Asset | Actor | Entry point | Primary risk |
|---|---|---|---|
| Citizen PII (name, CNIC, phone, address, chassis) | anonymous visitor | public search, `/challan/<id>/`, PDF links | PII harvesting, enumeration |
| Challan integrity / payment state | malicious payer, replaying gateway | `/api/v1/payment/webhook/`, demo checkout | free PAID status, double credit |
| Camera network & AI pipeline | anyone who can reach `/api/v1/*` | enroll / ingest / heartbeat | flooding, forged detections, enrollment-token brute force |
| Staff portals (DIG/SSP/SUPV/OFFICER/AUDIT/IT) | insider or hijacked session | `/portal/*`, uploads, backups | privilege abuse, data exfil, template injection |
| Session & credentials | remote attacker | auth portal, reset links | brute force, fixation, token reuse |
| Public homepage & branding | compromised DIG/IT account | banner editor | stored XSS on the public site |
| Static/media serving | any visitor | `/static/`, `/media/` | cache poisoning, executable uploads |

## 3. Findings

Severity: **C**ritical / **H**igh / **M**edium / **L**ow.
Status: **FIXED** (this pass, file+function named) / **SAFE** (verified, reason) /
**RESIDUAL** (documented, outside this pass's file ownership — see §7).

| # | Sev | Asset | Attack | Fix / verification | Status |
|---|---|---|---|---|---|
| F1 | H | Payment state | **Webhook double-credit TOCTOU.** `payment_webhook` read `payment_status`, then `mark_paid()` — two concurrent deliveries both settle: duplicate audit entries, `paid_at` overwritten, notifications double-consumed. | `payments/webhook.py::payment_webhook` — settlement now wrapped in `transaction.atomic()` + `select_for_update()` on the challan row; loser re-reads `PAID` inside the lock and returns `already_paid`. | FIXED |
| F2 | H | Payment state | **Demo-checkout double-submit.** Same check-then-act; visitor double-clicks "Confirm" or races the webhook. | `payments/views.py::demo_checkout` — challan row locked via `select_for_update`, transaction claimed with guarded `UPDATE … WHERE status='pending'`; only the first claimant settles. | FIXED |
| F3 | M | Credentials | **Reset-token single-use race.** `_get_valid_token` checked `used_at`, wrote it back after `set_password` — concurrent use of one reset link could both succeed. | `auth_portal/views.py::citizen_reset_confirm` — token claimed atomically (`UPDATE … WHERE used_at IS NULL`) *before* the password write; second claimant gets the invalid-token page. | FIXED |
| F4 | H | Public search | **XSS via reflected search fields** (`plate`, `q`, `cnic`). | SAFE + hardened: view-side normalisation (`challans/views.py::home`), template auto-escaping, `looks_malicious` query-string rejection in middleware; proven by pen-test T3 (script/img-onerror/javascript: payloads all neutralised). | SAFE |
| F5 | — | All search paths | **SQL injection.** | SAFE: 100% ORM (`Q` objects); zero `.raw()/.extra()` in views (only migrations/management commands touch cursors); proven by pen-test T3 SQLi payload. | SAFE |
| F6 | C | Challan PDF | **IDOR on `/challan/<id>/pdf/`.** | SAFE: anonymous requests require a `TimestampSigner` token bound to the challan id (30-day max age); ticket numbers and numeric ids rejected; staff roles or CNIC/phone ownership for citizens; proven by pen-test T1 (5 rejection cases + 1 valid token). Additionally new: **20/min per user-or-IP download limit** (`challans/views.py::_pdf_rate_limited`) because `?regen=1` re-renders the document (CPU DoS vector). | SAFE + FIXED (limit) |
| F7 | H | Challan detail | **IDOR on `/challan/<id>/`** for anonymous visitors. | SAFE **by design**: public verification portal — guests receive in-memory PII masking (`_mask_challan_pii`: name initials, CNIC/phone dotted, address truncated, chassis hidden); guest appeals demand the 13-digit CNIC linked to the challan. Covered by tests `PublicPiiMaskingTests`. | SAFE |
| F8 | M | Backups | **Path traversal in IT backup download.** | SAFE: `admin/dig_portal/views.py::backup_download` uses `Path(filename).name` (strips every directory component) + `.json` suffix check + `@it_required`; payloads with `/` never match the `<str:filename>` converter (404). Proven by pen-test T5 (5 payloads, no leak, legit file still downloads). | SAFE |
| F9 | M | Camera endpoints | **Abuse of unauthenticated API surface.** | FIXED: view-level limits in `cameras/views.py` — enroll 5/h, ingest 300/m, heartbeat 120/m per IP, checked *before* auth (flooders never reach the DB/AI pipeline); `@csrf_exempt` untouched (plain in-view checks, no decorator wrapping). Proven by pen-test T2. | FIXED |
| F10 | M | Payments API | **Webhook / demo-checkout flooding.** | FIXED: `payments/webhook.py` 60/m per IP pre-HMAC; `payments/views.py` POST 30/m per IP. 429 responses are JSON on `/api/*` with `Retry-After`. | FIXED |
| F11 | H | Guest appeals | **Arbitrary file upload** (`evidence_file` had no validation on the public `/challan/<id>/` POST). | FIXED: `challans/views.py::_validate_evidence_file` — extension whitelist (jpg/jpeg/png/webp/gif), 5 MB cap, PIL `verify()` content sniffing (rejects HTML/PHP/polyglots). Applied to guest *and* authenticated appeal paths. | FIXED |
| F12 | C | Browser clients | **Weak CSP** (`unsafe-eval` in script-src, dead `CSP_*` config drift, `code.jquery.com` leftover, no form-action/base-uri, framing only via `X-Frame-Options`). | FIXED: single-source CSP_* constants in `settings.py` consumed by `SecurityHeadersMiddleware`; `unsafe-eval` removed (no `eval`/`new Function` anywhere in assets — grep-verified); per-request **nonce** (`request.csp_nonce`) injected into script-src and adopted by the one owned inline script (tailwind.config, `templates/base.html`); `form-action 'self' https:` (JazzCash/EasyPaisa POST targets are https); `object-src 'none'`, `base-uri 'self'`; `frame-ancestors 'none'` with the `?embed=1` profile exception kept; `X-Frame-Options` now DENY (SAMEORIGIN on embeds). Full policy text in §5. | FIXED |
| F13 | — | Static serving | **WhiteNoise declared but never wired** (requirements.txt-only dependency); no immutable caching. | FIXED: wired `whitenoise.middleware.WhiteNoiseMiddleware` after `SecurityMiddleware`; `STORAGES['staticfiles']` = graceful compressed-manifest storage; fingerprinted assets get `Cache-Control: max-age=…, immutable` (verified: hashed URL → `max-age=315360000, public, immutable`, unhashed → 60 s). DEBUG keeps unhashed URLs + finder mode (dev unchanged). | FIXED |
| F14 | L | Signup | **Phone-only citizen signup 500s** (`IntegrityError`: `email` NOT NULL vs `email=None` from the form). | FIXED in `auth_portal/views.py::citizen_signup` (coerce `None → ''`); proven by pen-test T4. Root cause in `accounts/forms.py` (outside ownership) noted in §7. | FIXED |
| F15 | — | Signup | **Mass assignment** (`role`, `is_staff`, `is_superuser` via POST). | SAFE: `UserSignupForm` fields are whitelisted; view force-sets `role=USER` after `save(commit=False)`. Proven by pen-test T4 (injected `role=DIG is_staff=on is_superuser=on` → USER, staff False, super False). | SAFE |
| F16 | — | Auth | **Session fixation on login.** | SAFE: Django's `login()` rotates the session key (`cycle_key`/flush semantics) — a cookie fixed by the attacker pre-login is invalidated at login. | SAFE |
| F17 | — | Password reset | **Token entropy / expiry / single-use / enumeration.** | SAFE: `secrets.token_urlsafe(32)` (256-bit), 2 h TTL, single-use (now atomically — F3), citizen flow never renders the token (email-only delivery), uniform response whether the account exists; admin flow notifies DIG in-app (no self-service reset). | SAFE |
| F18 | — | Login | **Brute force / enumeration.** | SAFE: in-memory limiter 8/60s per IP on all four auth POSTs + `django_ratelimit` (admin 20/15m, citizen 30/15m) + account lockout 5 fails/15 min. Uniform "Invalid credentials."; lockout notice only after 5 failures (accepted standard trade-off). | SAFE |
| F19 | — | DB templates | **Template injection via `Template(row.html_content)`.** | SAFE: every writer is `@it_required` (`challan_templates_manage`, `challan_template_designer`, `audit_templates_manage`, `settings_edit`); DIG's `audit_templates_select` is select-only. | SAFE |
| F20 | — | SSRF | **User input → URL fetch.** | SAFE: `excise/nadra/webhook` URLs are admin-configured; the only fetch of admin data (`camera_snapshot`'s `http_snapshot_url`) is staff-configured and camera-scoped for officers. No user-controlled URL fetch exists. | SAFE |
| F21 | M | Static/media | **Executable content types from /media/.** | RESIDUAL (media): MEDIA is dev-served by `django.views.static.serve` (extension-based types); production recipe in §6. STATIC side now fixed via WhiteNoise (F13); guest-appeal uploads validated (F11). | PARTIAL |
| F22 | H | Officer portal | **`detection_detail` not camera-scoped** — any OFFICER can open any detection by id (list views *are* scoped via `scope_detections`). | RESIDUAL: `admin/officer_portal/views.py` outside this pass's ownership. Patch sketch in §7 (P3). | RESIDUAL |
| F23 | H | Public homepage | **Stored XSS by privileged staff**: `Banner.html_content` is written verbatim by DIG/IT and rendered `|safe` on the public homepage (`templates/challans/_public_ads.html`). | RESIDUAL: writer files outside ownership. §7 (P2). | RESIDUAL |
| F24 | M | Video upload | **No extension/MIME whitelist on `/video/upload/`** (200 MB, any content-type; `content_type` is client-supplied). | RESIDUAL: `video_processor/views.py` outside ownership. §7 (P4). | RESIDUAL |
| F25 | M | Citizen portal | **Evidence upload trusts client `content_type`** (no extension whitelist) — spoofable. | RESIDUAL: `citizen/citizen_portal/views.py` outside ownership; the equivalent guest path is fixed (F11). §7 (P4). | RESIDUAL |
| F26 | L | Challan issuance | **Double-submit race in `issue_challan`** (check-then-act; `Challan.detection` is not unique). Mitigated by the 24 h same-plate `chain_integrity` check. | RESIDUAL: `detections/pipeline.py` outside ownership. §7 (P5). | RESIDUAL |
| F27 | L | Banner images | **No validation on banner image upload** (`banner_add/banner_edit` accept any file into MEDIA). | RESIDUAL: writer outside ownership. §7 (P4). | RESIDUAL |
| F28 | — | Error pages | **Stack-trace leakage.** | SAFE: shared error handlers render generic pages (`wrongway_system/views.py`); 500 never echoes internals; DEBUG=False refuses the demo SECRET_KEY and `ALLOWED_HOSTS=*`. | SAFE |
| F29 | — | `/django-admin/` | **Django admin exposure.** | SAFE by design: portal isolation exempts it, but it sits behind Django admin auth (`is_staff` only — no account created by this app is staff), CSRF, lockout middleware and the same CSP headers. Documented decision; recommendation in §7 (P8). | SAFE |
| F30 | L | Rate limiter scope | **Single-process counters** (in-memory limiter + locmem cache). | RESIDUAL: fine for the single-worker uvicorn deployment (docs/REALTIME.md mandates 1 worker); multi-worker needs Redis. §7 (P7). | RESIDUAL |
| F31 | L | Proxy trust | `X-Forwarded-For` is trusted by the limiter/audit IP extraction. | RESIDUAL (documented pre-existing): must sit behind a trusted proxy that overwrites XFF, or switch to `REMOTE_ADDR`. §7 (P6). | RESIDUAL |

## 4. Rate-limit matrix (post-hardening)

| Endpoint | Method | Limit | Key | Layer | On breach |
|---|---|---|---|---|---|
| `/auth/admin/login/` | POST | 8/60s + 20/15m | IP | in-memory MW + django_ratelimit | 429 page / 403 ratelimited page |
| `/auth/citizen/login/` | POST | 8/60s + 30/15m | IP | in-memory MW + django_ratelimit | 429 page / 403 ratelimited page |
| `/auth/admin/forgot-password/` | POST | 8/60s | IP | in-memory MW | 429 page |
| `/auth/citizen/forgot-password/` | POST | 8/60s | IP | in-memory MW | 429 page |
| `/portal/**` (all portals) | POST | 120/60s | IP | in-memory MW | 429 page |
| `/api/v1/enroll/` | POST | **5/hour** | IP | view (`cameras/views.py`) | JSON 429 + `Retry-After` |
| `/api/v1/ingest/` | POST | **300/min** | IP | view (`cameras/views.py`) | JSON 429 |
| `/api/v1/heartbeat/` | POST | **120/min** | IP | view (`cameras/views.py`) | JSON 429 |
| `/api/v1/payment/webhook/` | POST | **60/min** | IP | view (`payments/webhook.py`) | JSON 429 |
| `/api/v1/payment/demo-checkout/` | POST | **30/min** | IP | view (`payments/views.py`) | JSON 429 |
| `/challan/<id>/pdf/` | GET | **20/min** | user-or-IP | view (`challans/views.py`) | HTML 429 error page |
| `/` public search | GET | 20/60s | IP (staff exempt) | view (pre-existing) | plain 429 |
| Citizen appeal submit | POST | 5/day | user | django_ratelimit | 403 ratelimited page |
| Any request | * | body ≤ 5 MB (50 MB on `/upload`, `/cameras/`, `/camera/`, `/video/`, `/media/`, `/api/v1/ingest`) | — | `RequestSizeLimitMiddleware` | 400 |
| Any request | * | malicious query-string patterns | — | `RateLimitMiddleware` | 400 |

Camera push cadence is every few seconds → 300/min leaves >2× headroom for a
single camera while capping floods (verified: normal heartbeat + ingest traffic
unaffected in pen-test T2).

## 5. Final CSP policy (composed by `SecurityHeadersMiddleware`)

Production (`DEBUG=False`), with `<nonce>` regenerated per request via
`secrets.token_urlsafe(16)` and exposed as `request.csp_nonce`:

```text
default-src 'self';
  script-src 'nonce-<per-request>' 'self' 'unsafe-inline'
    https://cdn.jsdelivr.net https://cdnjs.cloudflare.com
    https://unpkg.com https://cdn.tailwindcss.com
    https://fonts.googleapis.com;
  style-src 'self' 'unsafe-inline'
    https://fonts.googleapis.com https://cdnjs.cloudflare.com
    https://unpkg.com https://cdn.jsdelivr.net;
  font-src 'self' data: https://fonts.gstatic.com
    https://fonts.googleapis.com https://cdnjs.cloudflare.com;
  img-src 'self' data: blob: https:;
  connect-src 'self';
  frame-ancestors 'none';            /* 'self' on /…/profile/?embed=1 */
  object-src 'none';
  base-uri 'self';
  form-action 'self' https:
```

Other headers on every response: `X-Content-Type-Options: nosniff`,
`Referrer-Policy: same-origin`,
`Permissions-Policy: geolocation=(), microphone=(), camera=()`,
`X-Frame-Options: DENY` (SAMEORIGIN on embed fragments). In production also:
HSTS 1 y + preload, SSL redirect, secure cookies.

**Documented decisions**
- `'unsafe-eval'` removed — nothing in `static/` or templates uses `eval` /
  `new Function` (grep-verified).
- script-src `'unsafe-inline'` **retained** (residual, §7 P1): grep found
  inline event handlers in 16+ templates outside this pass's ownership, incl.
  public login eye-toggles (`onclick=…`), `onerror="this.remove()"` on chart.js
  tags (10 dashboards), DIG appeal-override action buttons, camera_add
  `onchange`, penalty_config `onchange="onToggle('{{ v.key }}', this)"`
  (dynamic — unhashable), banner delete `onsubmit="confirm('… {{ b.title }} …')"`.
  Removing it now would break public logins and staff workflows. The nonce
  infrastructure is live (base.html adopted it), so templates can migrate
  one file at a time and the flag can then be dropped.
- style-src `'unsafe-inline'` **accepted risk** — templates use extensive
  inline `style=` attributes and inline `<style>` blocks; CSP style noncing
  is a separate migration.
- `form-action 'self' https:` — the payment integrations POST to
  `sandbox|payments.jazzcash.com.pk` and `easypaystg|easypay.easypaisa.com.pk`
  (all https). http: form targets are blocked.
- `connect-src 'self'` — the Socket.IO client connects to
  `window.location.origin` + `/ws/socket.io`; same-origin `ws:`/`wss:` are
  matched by `'self'` under CSP origin equivalence.
- `img-src … data:` — data-URI images (charts, avatars); challan QR codes are
  inline SVG elements (DOM, not fetched resources).
- DEBUG variant (unchanged permissive): `*` hosts, `unsafe-eval` allowed,
  `form-action 'self' http: https:` — plus the same per-request nonce.

## 6. Static & media serving (F13/F21)

**Static.** WhiteNoise is now wired (`MIDDLEWARE`, directly after
`SecurityMiddleware`) with `STORAGES['staticfiles']` pointing at
`CompressedManifestStaticFilesStorage` subclassed with `manifest_strict=False`
(a stale/partial manifest falls back to an on-the-fly hashed URL instead of
raising). `collectstatic` produces 262 fingerprinted files (12-hex md5) plus
`.gz`/`.br` variants; `WHITENOISE_IMMUTABLE_FILE_TEST = r'\.[0-9a-f]{12}\.'`
matches them, so verified headers are:

- fingerprinted: `Cache-Control: max-age=315360000, public, immutable`
- everything else: `max-age=60` (0 in DEBUG)

DEBUG mode keeps unhashed `{% static %}` URLs (Django's `HashedFilesMixin`
DEBUG guard) and WhiteNoise's finder mode — dev servers behave exactly as
before. `launcher.py` already runs `collectstatic` before serving; a fresh
production checkout must run `python3 manage.py collectstatic` (documented in
settings.py). Add `staticfiles/` to `.gitignore` (it is a build artifact).

**Media (`/uploads`).** WhiteNoise intentionally does not serve MEDIA. In
DEBUG, `django.views.static.serve` handles it (extension-based types — dev
only). In production serve `/media/` from nginx with an explicit allow-list so
uploads are never executable:

```nginx
location /media/ {
    alias /home/z/my-project/safe-cities-project/uploads/;
    add_header X-Content-Type-Options nosniff;
    add_header Content-Disposition "attachment";
    types { }
    default_type application/octet-stream;   # nothing is ever text/html
}
```

Upload *writers* validated this pass: guest/authenticated appeal evidence
(whitelist + PIL sniff, F11). Remaining upload surfaces are §7 P4.

## 7. Residual risks & prioritised recommendations

- **P1 — retire script-src `'unsafe-inline'`** (F12 note). Move the 16+
  templates' inline handlers into `static/js/pages/*.js` (event delegation),
  adopt `nonce="{{ request.csp_nonce }}"` for any remaining inline script,
  then delete `'unsafe-inline'` from `CSP_SCRIPT_SRC` in `settings.py`.
  Browsers ignore the nonce while `'unsafe-inline'` is present, so the flag
  is the switch.
- **P2 — banner stored XSS (F23).** `admin/dig_portal/views.py::banner_add/
  banner_edit` store `html_content` verbatim; `templates/challans/
  _public_ads.html` renders it `|safe` on the **public** homepage. Sanitise on
  write (allow-list tags/attributes, e.g. bleach) or escape and drop `|safe`.
  Until then, a compromised DIG/IT account = persistent XSS against every
  visitor, including staff.
- **P3 — officer detection_detail scoping (F22).** `admin/officer_portal/
  views.py::detection_detail` does `get_object_or_404(Detection, pk=…)`.
  Wrap it with the existing `scope_detections()` helper (or 404 unless the
  officer has an active `CameraAssignment` for `detection.camera`), mirroring
  `camera_snapshot`'s officer check.
- **P4 — upload validation on remaining surfaces (F24/F25/F27).** Apply the
  F11 pattern (`_validate_evidence_file`) to `video_processor/views.py::
  upload_video` (video extension/MIME whitelist + capybara sniff via
  `cv2.VideoCapture`), `citizen/citizen_portal/views.py::submit_appeal`
  (extension whitelist; `content_type` alone is spoofable), and banner image
  uploads in `admin/dig_portal/views.py`.
- **P5 — challan duplicate issuance (F26).** Add `unique=True` to
  `Challan.detection` (FK) + `select_for_update` in `detections/pipeline.py::
  issue_challan` so concurrent finalisation cannot double-issue; keep the 24 h
  `chain_integrity` duplicate check as the semantic guard.
- **P6 — proxy trust (F31).** The limiter/audit IP extraction honours
  `X-Forwarded-For`. Deploy only behind a proxy that *overwrites* the header;
  otherwise strip it in `wrongway_system/security/rate_limit.py::_client_ip`.
- **P7 — multi-worker counters (F30).** In-memory windows + locmem cache are
  per-process (acceptable for the mandated single-worker uvicorn topology).
  For horizontal scaling switch both to Redis:
  `RATELIMIT_USE_CACHE='redis'` + a Redis-backed `is_rate_limited`.
- **P8 — `/django-admin/` (F29).** Auth is Django-admin-only (`is_staff`),
  which no account created by this app holds. Recommended: IP-restrict the
  mount at the proxy and set `ADMIN_URL` to an unguessable prefix.
- **P9 — CSRF cookie readability.** `CSRF_COOKIE_HTTPONLY=False` is required
  by the dashboard AJAX layer; risk is bounded by SameSite=Lax + Secure in
  production. Move AJAX CSRF transmission to the `X-CSRFToken` header +
  HttpOnly cookie when the JS layer is next touched.
- **P10 — `.gitignore`**: add `staticfiles/`; remove the vestigial
  `CAMERA_WORKER_INTERVAL` line from `launcher.py`'s generated `.env`
  (harmless — nothing reads it; the Django setting was removed this pass).
- **P11 — search limiter races.** `_check_rate_limit` uses non-atomic
  `cache.get/set` (minor undercount under bursts) and exempts all staff
  roles; tighten to `cache.incr` if abuse is observed.

## 8. Validation evidence (this pass)

| Command | Result |
|---|---|
| `python3 manage.py check` | `System check identified no issues (2 silenced)` |
| `python3 manage.py test challans accounts --keepdb -v 0` | `Ran 30 tests … OK (skipped=2)` |
| `python3 manage.py test challans accounts auth_portal --keepdb -v 0` | `Ran 37 tests … OK (skipped=2)` |
| `python3 manage.py collectstatic --noinput` | `262 static files copied, 1248 post-processed` (manifest + gzip/brotli) |
| `python3 scripts/pen_test.py` | **44/44 checks — ALL GREEN** (T1 PDF IDOR, T2 API 429s, T3 XSS, T4 mass-assignment, T5 traversal, T6 CSP/nonce, T7 429 rendering) |

## 9. Files changed in this pass

```
wrongway_system/settings.py            CSP_* single source (prod+debug), SECURE/X-Frame tighten,
                                       dead settings removed (AI_CONFIDENCE_THRESHOLD,
                                       CAMERA_WORKER_INTERVAL — grep-verified unused),
                                       WhiteNoise wiring (middleware + STORAGES + WHITENOISE_*)
wrongway_system/security/rate_limit.py request-aware 429 (JSON on /api/, error page elsewhere)
wrongway_system/security/middleware.py request plumbed into rate_limit_response; docs
admin/dig_portal/middleware.py         SecurityHeadersMiddleware: settings-driven CSP,
                                       per-request nonce, form-action, X-Frame DENY/SAMEORIGIN
templates/base.html                    tailwind.config script -> nonce="{{ request.csp_nonce }}"
cameras/views.py                        enroll 5/h, ingest 300/m, heartbeat 120/m (pre-auth checks)
payments/webhook.py                     60/m limit + atomic idempotent settlement (select_for_update)
payments/views.py                       demo-checkout 30/m + atomic guarded-claim settlement
challans/views.py                       PDF 20/m user-or-IP limit; appeal evidence whitelist+PIL sniff
auth_portal/views.py                    atomic reset-token claim; phone-only signup IntegrityError fix
requirements.txt                        whitenoise comment (now actually wired)
scripts/pen_test.py                     NEW — regression/pen-test harness (44 assertions)
docs/SECURITY_AUDIT.md                  NEW — this report
staticfiles/                            build artifact (collectstatic; gitignore recommended)
```

Pre-existing controls were re-verified and are unchanged: Argon2 hashing,
8 h HttpOnly SameSite=Lax sessions, custom CSRF token (HttpOnly=False by
design), 5/15 min lockout, HMAC-SHA256 webhook signatures, 30-day signed
links, guest PII masking, portal isolation, DEBUG=False guards, and the
django_ratelimit decorators on logins (20/15m, 30/15m) and citizen appeals
(5/day).
