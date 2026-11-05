# SAFE CITIES PROJECT | Multi-Role Master Audit Report

**Target:** `/home/z/my-project/safe-cities-project` - Django 5.0 video-based wrong-way e-challan platform
**Method:** 22 specialist role audits, each performed by reading the actual source code, models, templates, static assets, tests, and existing internal documentation.
**Scope rule for this document:** this is the only file created or modified by the audit.
**Date of pass:** 2026 hardening-era snapshot (post `docs/SECURITY_AUDIT.md`, post pen-test 44/44).

---

## Role 1 | Project Manager

**Verdict: PASS WITH NOTES**

**Strengths**
- Deliverable completeness is exceptional for the stated scope: 15 Django apps, 7 role portals, public portal, camera worker (`camera_worker/worker.py`), video batch processor (`cameras/video_processing.py`), PDF services (`challans/pdf_service.py`, `admin/audit_portal/audit_pdf.py`), payment integrations (`integrations/payments.py`), and realtime push (`realtime/realtime_events.py`) all exist and are wired.
- The README (`README.md`) documents the enforcement pipeline (DETECTION -> FRAME TRACKING -> EVIDENCE -> CHALLAN), the role/login matrix, URL map, and quick-start on both Windows and Linux; a newcomer can bootstrap with `setup.bat` / `launcher.py`.
- Milestone evidence is traceable: migration history shows disciplined phases (e.g. `admin/dig_portal/migrations/0013_blacklist_and_table_names.py`, `0014_fix_ai_detector_thresholds.py`, `detections/migrations/0011_remove_annotation_created_by_and_more.py` removing the manual-annotation feature deliberately).
- Operational tooling ships with the product: `launcher.py` (708 lines, venv/bootstrap/fresh/reset/realtime modes), `scripts/pen_test.py` regression harness, and management commands for verification (`verify_system`, `check_production`) and demo data (`seed_demo_accounts`).

**Issues found**
- P3 | No formal risk register or CHANGELOG anywhere in the repo; risk state lives implicitly in `docs/SECURITY_AUDIT.md` §7. Fix: promote that section into `docs/RISK_REGISTER.md` with owners and due dates.
- P3 | Deadline-critical single points of failure are people-knowledge, not documents: deployment topology exists only inside `docs/REALTIME.md` and `launcher.py`. Fix: a one-page `docs/RUNBOOK.md` covering start/stop/backup/restore.
- P2 | Six admin portal view modules have no automated tests at all (see Role 7), which makes regression risk on the highest-traffic staff surfaces unmanaged.
- P3 | Deliverable drift between README and product: README advertises "PDF (four layouts)" while `challans/pdf_service.py::TEMPLATE_MAP` ships seven layouts (modern_a4, classic_a4, legal_notice_99a, digital_slip, compact_receipt, enforcement_notice, urdu_a4) plus two aliases. Fix the README so the demo script matches what evaluators will see.

**Score: 8/10**

---

## Role 2 | Software Engineer

**Verdict: PASS WITH NOTES**

**Strengths**
- Clean module boundaries on the hot path: `detections/ai.py` (inference only, no DB writes), `detections/pipeline.py` (evidence + issuance, transaction-wrapped in `issue_challan`), `detections/finalize.py` (thin compatibility shim), `cameras/video_processing.py` (batch I/O). Pure functions (`_normalize_plate`, `_iou`, `_nms`, `_expand_box_to_vehicle`) are testable without Django.
- Error handling is consistently defensive without being silent: every risky branch logs via named loggers (`wrongway.ai`, `wrongway.pipeline`, `wrongway.video_upload`, `wrongway.pdf`, `wrongway.payments`) and degrades (e.g. `cameras/video_processing.py::process_video_upload` catches per-frame failures, marks `STATUS_FAILED` with a truncated `error_message`, and releases the capture in `finally`).
- Real logging config in `wrongway_system/settings.py` (RotatingFileHandler, 10 MB x 5 backups, verbose formatter) rather than print statements; `scripts` and workers respect it.
- DRY helpers where it matters: `accounts/decorators.py` composes `role_required`/`permission_required`/`any_permission_required` plus concrete shortcuts (`dig_required`, `it_required`, `staff_required`), all funneling to one `_safe_redirect`.

**Issues found**
- P2 | `admin/dig_portal/views.py` is a 4,096-line monolith mixing auth, cameras, banners, backups, payments, PDF settings, staff CRUD, analytics, and reports. Fix: split by domain into `views/` package modules (cameras.py, banners.py, payments.py, staff.py) keeping URLconf names stable.
- P3 | `appeals/models.py` uses `__import__('django.utils.timezone', fromlist=['now']).now()` in `advance_to_ssp` / `advance_to_dig` instead of a normal import at module top.
- P3 | `appeals/models.py::finalize` swallows the challan-voiding failure with a bare `except Exception: pass`; an approved appeal whose challan failed to void would leave the citizen billed. Fix: log the exception and surface it to the caller/view message.
- P3 | `detections/ai.py::get_ai_runtime_config` contains a confusing `locals()` check (`if 's' in locals()`) and a fallback path that silently diverges from the DB-backed config; simplify by restructuring the try block.
- P3 | `challans/models.py::ChallanManager.generate_ticket_no` does a read-then-write sequence with a `while exists()` loop; under concurrency two processes can pick the same number and one will raise `IntegrityError` (ticket_no is unique). Fix: wrap in a retry loop on IntegrityError or use a Postgres sequence.

**Score: 8/10**

---

## Role 3 | System Architect

**Verdict: PASS WITH NOTES**

**Strengths**
- Sensible layering: presentation (7 portal apps under `admin/` + `citizen/citizen_portal` + `auth_portal`), domain (`detections/` pipeline, `challans/` lifecycle, `appeals/` workflow), data (models per app), infrastructure (`wrongway_system/security/`, `integrations/`, `realtime/`). Cross-cutting AI config lives in `SystemSettings` (DB-driven) with runtime merge in `detections/ai.py::get_ai_runtime_config`.
- Portal isolation is enforced at two layers: `admin/dig_portal/middleware.py::PortalIsolationMiddleware` (path-prefix to role map, redirect on mismatch) AND per-view decorators, with tests in `accounts/tests.py::PortalIsolationTests` proving cross-role access is redirected.
- App boundaries under `admin/` are real Django apps (own `apps.py`, `urls.py`, `views.py`) rather than one mega-app; DIG-specific models (`SystemSettings`, `AuditLog`, `Banner`, `Alert`, `Notification`, `Shift`, `ChallanTemplate`, `AuditPDFTemplate`, `BlacklistEntry`) live in `admin/dig_portal/models.py` while IT-owned `PaymentMethod` correctly lives in `admin/it_support_portal/models.py`.
- Deployment topology is explicitly documented: `wrongway_system/asgi.py` mounts `socketio.ASGIApp` at `/ws/socket.io` with a graceful fallback to plain Django ASGI if python-socketio is missing; `docs/REALTIME.md` mandates `--workers 1` and documents the Redis client-manager path for scaling.

**Issues found**
- P2 | Single-process constraint is architectural, not incidental: realtime emits (`detections/pipeline.py::_emit_realtime`) are in-process calls, and the in-memory rate limiter + locmem cache (`wrongway_system/settings.py` CACHES) are per-process. Running gunicorn with 2+ workers silently breaks both push delivery and limiter accuracy. Fix: make the Redis-backed path (documented in `docs/REALTIME.md` and `docs/SECURITY_AUDIT.md` P7) the default for any multi-worker deployment, and add a startup assertion that warns when `workers > 1` without Redis.
- P3 | `detections/pipeline.py::issue_challan` imports `lookup_owner_by_plate` from `admin/officer_portal/views` - the domain layer reaching up into a presentation module. Fix: move owner lookup into `integrations/excise.py` or a `challans/services.py`.
- P3 | The `admin/` package holds shared middleware (`admin/dig_portal/middleware.py`) used by every portal; name implies DIG ownership. Fix: hoist to a neutral `common/` or `wrongway_system/` package.
- P3 | `admin/shared/live_tracking.py` exists but most sharing is done via import from `dig_portal`; two patterns for the same problem.

**Score: 8/10**

---

## Role 4 | Database Engineer

**Verdict: PASS WITH NOTES**

*(Reviewed all 10 model files: `accounts/models.py`, `cameras/models.py`, `detections/models.py`, `challans/models.py`, `appeals/models.py`, `realtime/models.py`, `video_processor/models.py`, `payments/models.py`, `admin/dig_portal/models.py`, `admin/it_support_portal/models.py`.)*

**Strengths**
- Professional table naming throughout via explicit `db_table` (`sc_users`, `sc_detections`, `sc_challans`, `sc_challan_appeals`, `sc_payment_transactions`, `sc_audit_logs`, `sc_blacklist`, etc.) enforced by a dedicated `professionalize_db` migration per app (e.g. `cameras/migrations/0006_professional_table_names.py`).
- Index coverage is thoughtful and matches query patterns: `Detection` indexes `(status, created_at)`, `(camera, created_at)`, `(reviewed_by, reviewed_at)`, `track_id`; `Challan` indexes `cnic`, `plate_number`, `payment_status`, `issue_date`, `txn_ref`; `AuditLog` indexes `(actor, timestamp)`, `(action, timestamp)`, `(target_model, target_id)`; `Notification` indexes `(recipient, is_read)`.
- on_delete policies are legally aware: `Detection.camera` and `Challan.detection`/`camera` are `SET_NULL` with an explicit help_text in `detections/models.py` ("deleting a camera must never destroy violation evidence or challan history"), while dependent rows (`DetectionReviewNote`, `VideoFrame`, `ChallanAppeal`) correctly CASCADE. Human attribution fields (`reviewed_by`, `created_by`, `actor`) are `SET_NULL` to preserve history.
- Migration hygiene: 74 migration files, linear, no merge conflicts visible; renames are done as separate numbered steps; `AdminPasswordResetRequest` token uses `secrets.token_urlsafe(32)` with a composite index on `(status, -created_at)`.

**Issues found**
- P2 | `Challan.detection` is a non-unique FK (`challans/models.py` line 57) while the pipeline assumes one-challan-per-detection (`detections/pipeline.py::issue_challan` does a check-then-create). This is finding F26 in `docs/SECURITY_AUDIT.md`. Fix: `unique=True` on the FK plus `select_for_update` in the issuance transaction (audit doc P5 sketch).
- P3 | `PaymentTransaction.ticket_no` is a free CharField with its own index while a proper `challan` FK also exists (nullable); two sources of truth for linkage. Fix: backfill the FK and deprecate the raw column.
- P3 | `Challan` carries dead violation choices (`NO_HELMET`, `SIGNAL_BREAK`, `OVER_SPEED`, `OTHER`) while `ENABLED_VIOLATIONS = [WRONG_WAY]` only; choices invite future UI mistakes. Fix: prune choices or gate them behind `ENABLED_VIOLATIONS` in every form.
- P3 | `Shift.auto_assign_officer` (`admin/dig_portal/models.py`) loads **all** shifts into memory (`Shift.objects.all().only(...)`) to compute overlap; at tens of thousands of shift rows this degrades. Fix: windowed query with `Q(start_time__lt=end, end_time__gt=start)`.
- P3 | `SystemSettings.get()` runs `objects.first()` on every call with no caching; it is hit from AI config resolution per frame in `detections/ai.py`. Fix: cache for N seconds (locmem is fine single-process).

**Score: 8/10**

---

## Role 5 | AI/ML Expert

**Verdict: PASS WITH NOTES**

*(Reviewed `detections/ai.py` (757 lines), `detections/pipeline.py` (470 lines), `cameras/video_processing.py` (287 lines), `detections/evidence_annotator.py`, model configs in `admin/dig_portal/models.py::DEFAULT_AI_CONFIG`.)*

**Strengths**
- The detection chain is well engineered for CPU-only deployment: ONNX Runtime sessions are lazily cached module-level (`_get_plate_detector`, `_get_side_classifier`), plate detector input is 560x560 NCHW with ImageNet normalization, side classifier is 224x224 NHWC with [-1,1] MobileNet-style preprocessing; both INT8 models under `models/` (NumberPlate + car-side).
- Robust inference guards: box-area ratio clamps (`max_box_area_ratio`, `min_box_area_ratio`), aspect filtering (0.4-8.0), pixel minimums (bw >= 8, bh >= 6), custom NMS (`_nms` with `_iou`), class filtering with plate_class_ids and person rejection, and a "dead model" detector that recognizes a constant INT8 export (`detections/ai.py` lines 331-352: near-uniform softmax or 0.0 output returns unknown side instead of garbage).
- OCR chain is a genuine 3-engine cascade with multi-pass preprocessing (`_preprocess_plate_for_ocr` produces raw + bilateral-filtered + adaptive-threshold variants): PaddleOCR (preferred) -> EasyOCR (triggered when best conf < 0.55) -> pytesseract (last resort, fixed conf 0.70), then candidate scoring with length + engine bonus (`_ocr_plate_image`).
- The 5 hard evidence checks in `detections/pipeline.py` are exactly as documented in README: `plate_readability` (PK format regex `^[A-Z]{2,3}\d{1,4}$` + OCR >= 0.60), `frame_consistency` (track >= 2 frames with >= 0.60 consistency, or single frame >= 0.90, or sequential 3-frame plate agreement), `violation_logic` (side == camera.violation_side, conf >= 0.60), `image_evidence` (raw + crop present, crop height >= 18px), `chain_integrity` (SHA-256 digest + 24h duplicate block). Cars-only strictness is real: `car_only: True` in DEFAULT_AI_CONFIG and side classification runs on an expanded vehicle crop (`_expand_box_to_vehicle`, 3.5x/4.5x).
- Blacklist is enforced inside `run_pipeline` (`detections/ai.py` lines 667-695): exact and prefix-normalized match, blacklisted plates force `detected_violation = False` so no challan can ever issue.
- 3-frame sequential evidence is implemented end-to-end: `cameras/video_processing.py::_capture_sequential_frames` grabs the next two truly consecutive frames on a plate hit, runs the full pipeline on each, stores them as `evidence_frame_2/3` with per-slot metadata; `Detection.evidence_frames()` assembles primary + sequential + track peers for review.

**Issues found**
- P2 | The plate detector confidence threshold default is very low (0.15 in `get_ai_runtime_config`, `PLATE_CONFIDENCE_THRESHOLD = 0.15`) with reliance on downstream checks to reject noise. At 300 max detections and 560x560 CPU inference, low-threshold frames spend significant OCR time on false boxes before evidence checks reject them. Fix: raise the runtime default toward 0.30-0.45 (the `get_model_info` fallback even reports 0.45) and measure recall on the demo corpus.
- P3 | `frame_tracking` consistency is computed from only the **last** matched detection (`agree_plate`/`agree_side` on `matched[-1]`, `detections/pipeline.py` lines 113-115) rather than across all frames in the window; a track of 5 frames with one coincidental agreement scores 1.0. Fix: compute agreement across all matched peers.
- P3 | `run_pipeline` runs the side classifier even when no plate was detected (side_image defaults to the full frame), burning inference on frames that can never produce a challan. Fix: short-circuit when `detections` is empty.
- P3 | OCR confidence for the Tesseract fallback is hard-coded 0.70 (`detections/ai.py` line 534), which can pass `plate_readability` (min 0.60) without any real confidence signal. Fix: mark tesseract reads as low-trust or omit them from issuance paths.
- P3 | Blacklist prefix fallback (`plate_number__icontains=plate_norm[:6]`) can false-positive on plates sharing a 6-char prefix. Fix: exact-normalized comparison via a stored normalized column.

**Score: 8/10**

---

## Role 6 | Security Engineer

**Verdict: PASS WITH NOTES**

*(Summarised `docs/SECURITY_AUDIT.md` (286 lines) and verified its claims against the live code.)*

**Strengths**
- The internal audit is unusually honest and technically deep: 31 findings (F1-F31) with severity, fix location, and status; criticals and highs fixed this pass include webhook TOCTOU double-credit (`payments/webhook.py` now `transaction.atomic()` + `select_for_update`), demo-checkout double-submit (`payments/views.py` guarded UPDATE claim), reset-token single-use race (`auth_portal/views.py` atomic claim), CSP hardening (nonce infrastructure in `admin/dig_portal/middleware.py::SecurityHeadersMiddleware`, `unsafe-eval` removed, `form-action 'self' https:`, `frame-ancestors 'none'`), and WhiteNoise wiring (immutable cache headers, verified in settings).
- OWASP coverage is broad and test-proven: IDOR (PDF token gate `challans/views.py::_pdf_rate_limited` + TimestampSigner), injection (100% ORM, pen-test T3), broken auth (Argon2 + 5-fail/15-min lockout `accounts/models.py::register_failed_login` + `AccountLockoutMiddleware`), mass assignment (whitelisted `UserSignupForm`), SSRF (admin-only URL fetches), clickjacking (X-Frame-Options DENY + CSP frame-ancestors), and enumeration (uniform reset responses, `auth_portal/tests.py`).
- Rate limiting is layered (matrix in audit §4): in-memory login 8/60s, django_ratelimit 20/15m + 30/15m, portal POST 120/60s, API enroll 5/h, ingest 300/m, heartbeat 120/m, webhook 60/m, demo-checkout 30/m, PDF 20/min, search 20/60s, body-size caps 5 MB / 50 MB.
- HMAC webhooks: `payments/webhook.py::_check_signature` uses `hmac.compare_digest` over SHA-256 of the raw body; unsigned webhooks are rejected when integration mode is real; JazzCash v1.1 secure hash implemented in `integrations/payments.py::_jazzcash_secure_hash`.
- Upload hardening on the public surface: `challans/views.py::_validate_evidence_file` (extension whitelist + 5 MB cap + PIL `verify()` sniff) for guest and authenticated appeals.

**Issues found**
- P2 | Stored XSS via banners (finding F23, still open): `Banner.html_content` written verbatim by DIG/IT and rendered `|safe` on the public homepage (`templates/challan/_public_ads.html`). A compromised staff account gives persistent XSS against every visitor. Fix: sanitize on write (allow-list) or escape and drop `|safe`.
- P2 | Officer `detection_detail` is not camera-scoped (finding F22, confirmed still present at `admin/officer_portal/views.py` lines 155-161: plain `get_object_or_404(Detection, pk=...)` while list views use `scope_detections`). Fix: apply `scope_detections` or 404 unless an active CameraAssignment exists.
- P2 | CSP `script-src 'unsafe-inline'` retained (audit P1): 16+ templates still use inline handlers; nonce infrastructure is live but the flag is the switch. Fix: migrate handlers to `static/js/pages/*.js` event delegation, then remove the token.
- P3 | Media serving in production relies on the nginx recipe (audit §6) rather than code; if deployed without it, `/uploads` falls back to dev behaviour. Fix: add a settings-time warning when `DEBUG=False` and no `X-Accel`/nginx marker is present.
- P3 | Secrets at rest: `SystemSettings.excise_api_key` / `nadra_api_key` and `PaymentMethod.config` (integrity salts, secret keys) are stored as plaintext CharField/JSON. Fix: application-level encryption (e.g. django-fernet-fields pattern) or vault.
- P3 | `PG_PASSWORD` default `Admin@2026` baked into `wrongway_system/settings.py` and `launcher.py::DEFAULT_ENV_EXAMPLE` - dev convenience, but a leak risk if `.env` is absent in a public deployment. Fix: refuse to boot with the default password when `DEBUG=False` (pattern already used for SECRET_KEY).

**Score: 8/10**

---

## Role 7 | QA Lead

**Verdict: PASS WITH NOTES**

**Strengths**
- Test inventory is meaningful, not decorative: 54 test functions across 5 modules - `detections/tests.py` (pipeline happy path, each failing check, duplicate 24h block, track corroboration, tamper-evident hash determinism/change, annotation-removal regression), `challans/tests.py` (PII masking, PDF token security, payment integrity incl. demo-checkout single-use, XSS/SQLi/CSRF, rate limit), `accounts/tests.py` (portal isolation, permission matrix, officer camera scoping, citizen isolation), `auth_portal/tests.py` (reset-token lifecycle, no token leakage, admin reset flow), `video_processor/tests.py` (dry-run processing, officer scoping, IT-only list).
- `scripts/pen_test.py` (389 lines) is a genuine regression harness: forces `DEBUG=False`, random SECRET_KEY, real settings module, and asserts 44 checks across 7 proof groups (T1 PDF IDOR, T2 API 429s, T3 XSS, T4 mass assignment, T5 traversal, T6 CSP/nonce, T7 429 rendering). Exit code gates CI use.
- Negative testing exists where it matters: `RemovedFeatureTests.test_annotation_model_is_gone` and `AnnotationRemovalTests` lock the "no manual annotation" compliance requirement into executable form.
- The test command is documented in README with a coverage narrative ("Covers the full pipeline ... RBAC and portal isolation for every role, IDOR scoping, PII masking, payment integrity, XSS/SQLi/CSRF hardening").

**Issues found**
- P2 | Zero unit tests for the six admin portal view modules: `admin/dig_portal/views.py` (4,096 lines), `admin/officer_portal/views.py`, `admin/audit_portal/views.py`, `admin/it_support_portal/views.py`, `admin/ssp_portal/views.py`, `admin/supervisor_portal/views.py` have no `tests.py`. The portal-isolation middleware is tested, but view-level authorization (e.g. which DIG actions an SSP can reach) is not. Fix: add per-portal smoke tests asserting 200/302 for allowed and denied roles on each top-level route.
- P3 | No load-test tooling or results in-repo. Recommendations: (a) Locust profile for public search (target the 20/60s limiter), (b) ingest flood profile at 300/min to confirm 429 JSON shaping, (c) PDF regen concurrency (`?regen=1`) to validate the 20/min cap, (d) one long-running soak with the camera worker to watch the 45-second track window behaviour under lag.
- P3 | Tests must be run with a live PostgreSQL (settings refuse to boot without it, `wrongway_system/settings.py::_pg_available`), so CI needs a service container; there is no CI config file in-repo. Fix: add a minimal GitHub Actions workflow with a postgres service.
- P3 | `video_processor/tests.py::test_video_upload_processing_dry_run` is a single dry run; the 3-frame sequential branch (`_capture_sequential_frames`) deserves its own fixture-based assertions.

**Score: 7/10**

---

## Role 8 | UI/UX Expert

**Verdict: PASS WITH NOTES**

**Strengths**
- A real design system, tokenized: `static/css/safe-city.css` defines `:root` custom properties for color (`--sc-navy #16294E`, `--sc-primary #2563EB`, semantic success/warning/danger/info/teal/purple pairs), radius (`--sc-radius-sm/lg`), three shadow levels, and typography (`--sc-font` Inter, `--sc-mono` JetBrains Mono); companion layers `safe-city-public.css`, `safe-city-modern.css`, `tailwind-bridge.css` (with preflight disabled so Bootstrap is never reset, documented in `templates/base.html`).
- Per-page CSS exists for ~50 pages under `static/css/pages/` (e.g. `officer-review-queue.css`, `dig-heatmap.css`, `public-guest-pay.css`, `error-page.css`), matching the "no inline styles" claim in README.
- Public pages use a coherent glassmorphism treatment (hero on `templates/challan/home.html` with `home_hero_bg.jpg`, card surfaces over the `#E8EEF7` page tint), while monitoring surfaces use dark command-center styling (`dig-live-monitor.css`, `officer-camera-feed.css`) - correct genre separation between citizen-facing and operator-facing UI.
- The challan PDF UX is genuinely considered: payment channels as SVG icons (`static/img/payment/*.svg`), QR payload, barcode, signature blocks - see Role 14.

**Issues found**
- P3 | Dark CCTV/monitor UIs (`dig-live-monitor.css`, `officer-camera-feed.css`, `portal-ticker` surfaces) have no documented contrast targets; small status text on dark panels risks WCAG AA misses. Fix: add a contrast test note per palette pair or lighten `--sc-text-faint` (#8A94B0) where used on dark backgrounds.
- P3 | 141 templates with heavy per-page CSS means style drift risk; no stylelint or token-usage lint is configured. Fix: add a simple grep-based CI check that `static/css/pages/*.css` only use var(--sc-*) colors.
- P3 | The topbar search (`templates/base.html` line 107-110) submits to the public home for every role, including officers - search affordance does not match role context. Fix: route staff to `dig:vehicle_search` when the role permits.

**Score: 8/10**

---

## Role 9 | Frontend Engineer

**Verdict: PASS WITH NOTES**

**Strengths**
- `templates/base.html` is a disciplined stack: Bootstrap 5.3.3 CDN + Tailwind Play CDN bridged via `static/css/tailwind-bridge.css` (preflight off), Bootstrap Icons 1.11.3 + Font Awesome 6.5.2, jQuery (for DataTables), Chart.js, SweetAlert2, Socket.IO client injected on demand by `static/js/realtime-socket.js`. The Tailwind config block is the only inline script and is CSP-nonce opted-in (`nonce="{{ request.csp_nonce }}"`).
- Page JS is properly extracted: ~50 files under `static/js/pages/` named per route (`officer-review-queue.js`, `dig-analytics.js`, `it-challan-designer.js`, `citizen-pay-redirect.js`...), plus shared libraries `safe-city.js`, `safe-city-forms.js`, `safe-city-tables.js`, `safe-city-charts.js`, `safe-city-charts-data.js`, `safe-city-live.js`, `safe-city-print.js`.
- `static/js/console-guard.js` silences console output in production only, driven by `body[data-env]` (base.html lines 60-66) - a nice production polish with a documented safe default.
- Realtime client is defensive: `static/js/realtime-socket.js` exposes `window.SafeCityRealtime`, fires `safecity:realtime-state` lifecycle events for status badges, and carries role as a routing hint only (documented non-sensitive payloads in `docs/REALTIME.md`).

**Issues found**
- P2 | 16+ templates still carry inline event handlers (documented in `docs/SECURITY_AUDIT.md` P1: login eye-toggles, chart.js `onerror="this.remove()"`, DIG appeal-override buttons, `camera_add`/`penalty_config` onchange, banner delete onsubmit). This is the direct blocker for tightening CSP. Fix: event-delegation modules per page under `static/js/pages/`.
- P3 | jQuery + Bootstrap JS + Tailwind + two icon fonts is a heavy payload for dashboards; all from CDNs, so an offline deployment loses styling. Fix: vendor the critical CSS/JS locally (WhiteNoise already handles fingerprinting and would then serve them immutably).
- P3 | `static/js/pages/it-challan-designer.js` embeds a default designation string that violates the branding policy (see Compliance section). Fix: change the default to a neutral "Enforcement Directorate".

**Score: 7/10**

---

## Role 10 | Backend Engineer

**Verdict: PASS**

**Strengths**
- View layering is consistent: thin portal views -> services (`challans/pdf_service.py`, `challans/email_service.py`, `admin/audit_portal/audit_pdf.py`, `detections/evidence_annotator.py`) -> models/pipeline. 257 view functions across the project, each portal with its own `urls.py` namespace.
- The decorator suite (`accounts/decorators.py`) gives both coarse (`role_required`, `staff_required`, `officer_or_dig_required`) and fine-grained (`permission_required`, `any_permission_required`) authorization backed by `accounts/permissions.py` (114 named permissions, role matrix, `get_reports_to`/`get_manages`/`can_override_user` hierarchy helpers) driven by `permission.json`.
- The middleware chain (14 entries) is well-ordered: SecurityMiddleware -> WhiteNoise -> sessions -> CSRF -> auth -> messages -> clickjacking -> AuditLogMiddleware -> AccountLockoutMiddleware -> SecurityHeadersMiddleware -> PortalIsolationMiddleware -> RateLimitMiddleware -> RequestSizeLimitMiddleware. Each has a single documented responsibility (`admin/dig_portal/middleware.py` docstring; `wrongway_system/security/middleware.py` docstring).
- The PDF engine chain in `challans/pdf_service.py` is a genuine 4-stage degradation: WeasyPrint (template map of 7 layouts + aliases) -> overflow re-render through the compact template when the pypdf page count > 1 -> xhtml2pdf -> ReportLab single-page fallback (`_fallback_reportlab_pdf`), guaranteeing the one-A4-page invariant even on hosts without GTK.
- Payment settlement is server-side only: `payments/webhook.py` (HMAC + atomic lock) and `payments/views.py::demo_checkout` (rate-limited, atomic guarded claim); guest pay views never mutate status (proven by `challans/tests.py::PaymentIntegrityTests`).

**Issues found**
- P3 | `wrongway_system/urls.py` mounts Django admin at the guessable `django-admin/` (documented as F29/P8 in the security audit). Fix: `ADMIN_URL` env prefix + proxy IP restriction.
- P3 | Legacy redirect routes (`/dig/`, `/ssp/`, ... in `wrongway_system/urls.py`) are permanent=False 302s kept for old bookmarks; fine, but they bypass nothing - verify they are covered by portal isolation tests (they redirect to `/portal/...` which is).
- P3 | `challans/views.py::home` search caps at 100 fetched rows then trims to 25 in Python; acceptable, but a plate `icontains` over a large table will scan - see Role 15.

**Score: 9/10**

---

## Role 11 | DevOps Engineer

**Verdict: PASS WITH NOTES**

**Strengths**
- `launcher.py` (707 lines) is a full ops entrypoint: python version gate (3.10+), venv bootstrap, dependency install, `.env` generation from a template, migrations, `collectstatic`, `verify_system`, run modes (`run`, `realtime` -> uvicorn ASGI 1 worker, `fresh` destructive reset), Windows/Linux aware.
- `requirements.txt` is annotated with intent (PostgreSQL only, ONNX + OCR chain with the Paddle/EasyOCR/Tesseract fallback matrix and Python-version caveats, WeasyPrint GTK note, WhiteNoise "actually wired" comment pointing at settings).
- WhiteNoise is properly configured in `wrongway_system/settings.py`: `CompressedManifestStaticFilesStorage` subclass with `manifest_strict = False` (graceful fallback), `WHITENOISE_IMMUTABLE_FILE_TEST` matching Django's 12-hex md5, immutable 10-year caching for fingerprinted assets; `launcher.py` runs collectstatic automatically.
- PostgreSQL is enforced, not assumed: settings probe the socket before Django boots and print an actionable error (`_pg_available`); `CONN_MAX_AGE = 60` with health checks; timezone pinned `Asia/Karachi`; logs rotate under `logs/safecity.log`.
- Backups are a product feature: IT portal backup list/download (with traversal-safe `backup_download`), and `admin/dig_portal/management/commands/purge_data.py` for clean teardowns.

**Issues found**
- P3 | `.env.example` is thinner than the generated default env in `launcher.py` (it omits lockout, email, and `CAMERA_WORKER_INTERVAL` keys that launcher writes); a manual setup following README will diverge from a launcher setup. Fix: sync the two files.
- P3 | The vestigial `CAMERA_WORKER_INTERVAL` line is still generated into new `.env` files although the setting was deleted (documented harmless in settings.py comment and audit P10). Fix: remove from `DEFAULT_ENV_EXAMPLE`.
- P3 | No systemd unit, Dockerfile, or process-manager config in-repo; `docs/REALTIME.md` gives the uvicorn command but nothing supervises it or the camera worker. Fix: ship `deploy/safecity.service` + `deploy/camera-worker.service` examples.
- P3 | Backup content is JSON exports only; there is no documented media/uploads or pg_dump path. Fix: document a full-restore drill (pg_dump + uploads dir + staticfiles rebuild).

**Score: 8/10**

---

## Role 12 | Product Engineer

**Verdict: PASS WITH NOTES**

**Strengths**
- Citizen journey is complete: public search (plate/CNIC/ticket via `challans/views.py::home`) -> detail with masked PII for guests -> guest or authenticated appeal (CNIC-matched) -> payment via active methods (JazzCash/EasyPaisa/card; cash and bank transfer explicitly blocked in `integrations/payments.py::initiate_payment`) -> appeal tracker and escalation in the citizen portal (`templates/dashboard/citizen/appeal_tracker.html`, `escalate_appeal.html`).
- Officer triage is a real workflow, not a mock: review queue with 3-frame evidence stepper (`templates/dashboard/officer/review_queue.html` + `static/js/pages/officer-review-queue.js`), confirm/reject/flag-for-DIG actions, review history, performance page, camera feed, vehicle tracking, appeal handling.
- DIG command center is exhaustive: 45+ templates under `templates/dashboard/dig/` covering cameras, staff, banners/alerts, blacklist, penalties, shifts, revenue, financial + operational audit, heatmap, live monitor, vehicle search, system health, officer signatures, and audit-template selection.
- IT Support owns the platform plumbing as a product: staff directory, payment method CRUD, challan template library + designer (Canva-lite), audit template library, backup list - matching the "IT SUPPORT" persona's real job.

**Issues found**
- P3 | Supervisor and SSP portals are thin relative to DIG (88 and 155 lines of views vs 4,096): supervisor has dashboard + team performance; SSP dashboard + high-value review. If the org chart says supervisors assign cameras (`SupervisorProfile.can_reassign_cameras`), no route exercises it. Fix: wire or remove the capability.
- P3 | The appeal escalation chain in code is OFFICER -> SSP -> DIG (`appeals/models.py` STAGE_CHOICES officer/ssp/dig; `advance_to_ssp`, `advance_to_dig`); there is no supervisor stage, and `current_stage` defaults to `STAGE_SSP`. Product copy should state the real chain to avoid expectation mismatch.
- P3 | Citizen profile shows `total_challans/total_paid/total_unpaid` fields on `CitizenProfile` that are maintained denormalized; no visible resync command if counts drift. Fix: recompute on save or via management command.

**Score: 8/10**

---

## Role 13 | Data Privacy Officer

**Verdict: PASS WITH NOTES**

**Strengths**
- Guest PII masking is implemented in-memory only and never persisted (`challans/views.py::_mask_challan_pii`: name initials, CNIC `35202-*******-1` style, phone dots, address truncated, chassis hidden), with a dedicated test asserting DB rows are not mutated (`challans/tests.py::PublicPiiMaskingTests`).
- Access auditing is systemic: `AuditLogMiddleware` records every mutating staff request (method, path, actor, IP), `AuditLog.write` is called at issuance and settlement, and the audit portal exposes auth events, user activity, permission changes, and anomaly views (`admin/audit_portal/views.py`).
- Data minimization on the realtime channel: `docs/REALTIME.md` explicitly states payloads are non-sensitive (ids, plates, statuses) and full evidence stays behind authenticated views.
- Admin password resets follow least-privilege: staff cannot self-reset; `AdminPasswordResetRequest` creates a DIG-notified workflow with 72h expiry (`accounts/models.py`).

**Issues found**
- P2 | No data-retention policy anywhere: detections, raw frames, plate crops, seq frames, annotated images, and video files accumulate forever (per-day upload_to paths under `uploads/`). GDPR-style storage limitation requires defined lifetimes. Fix: add a retention setting per artifact class and a purge command (extend `purge_data.py` or a new `prune_evidence` command).
- P3 | CNIC is used as the citizen login identifier (documented in README) - a unique national identifier doubling as a username increases breach impact. Fix: consider phone-first login with CNIC as secondary (the `PhoneOrEmailBackend` in `accounts/backends.py` already supports phone).
- P3 | `Detection.ai_raw_response` stores full raw inference JSON indefinitely; bounding boxes and confidences are fine, but coupling them to images without retention limits makes the evidence set grow unbounded.
- P3 | No DPIA / privacy notice document in `docs/`. Fix: one page covering lawful basis, retention, masking behaviour, and subject-access path.

**Score: 7/10**

---

## Role 14 | Legal/Compliance Analyst

**Verdict: PASS WITH NOTES**

**Strengths**
- The legal challan template exists and is correct in form: `templates/challan/challan_templates/legal_notice_99a.html` header reads "NOTICE UNDER SECTION 99-A, MOTOR VEHICLES ORDINANCE, 1965" with a signature block binding the officer name/designation to SAFE CITIES PROJECT.
- Chain of custody is cryptographically defensible: `detections/pipeline.py::build_evidence_hash` computes SHA-256 over camera identity, detection id, normalized plate, timestamp, the raw-image digest, the plate-crop digest, and the four prior check results; tamper tests prove the hash changes when the plate text or the underlying image changes (`detections/tests.py::TamperEvidenceTests`). The digest is stored on the detection and printed on the challan (README).
- Signature blocks are first-class: `User.signature`, `signature_name`, `signature_designation`, `signature_stamp` fields (`accounts/models.py`), a DIG officer-signature management page (`templates/dashboard/dig/officer_signatures.html`), and helpers `_officer_signature_*` in `challans/views.py` feeding the templates; the designer default in `static/js/pages/it-challan-designer.js` renders officer designation under the signature.
- Issuer attribution is resolvable (`challans/views.py::_resolve_officer`, with the H3 fix note), and issuance writes an `AuditLog` entry including the evidence hash (`detections/pipeline.py::issue_challan`).

**Issues found**
- P3 | The evidence hash covers raw + plate-crop images but not `evidence_frame_2/3` (the sequential frames) nor the annotated image; the custody chain is therefore incomplete for the 3-frame package that the product claims. Fix: include all evidence frame digests in `build_evidence_hash`.
- P3 | `appeals/models.py::finalize` voids the challan on approval but payment-status changes are not reflected in a court-facing amendment notice; the voided challan PDF still shows the original fine. Fix: regenerate the PDF with a VOIDED overlay when an appeal is approved.
- P3 | The 24h duplicate rule is a policy constant inside `_check_chain_integrity`; legal review should confirm the window matches enforcement guidance and is documented in the notice templates.

**Score: 8/10**

---

## Role 15 | Performance Engineer

**Verdict: PASS WITH NOTES**

**Strengths**
- Index coverage matches the hot queries (see Role 4); `select_related` is used where it counts (`challans/views.py::challan_detail` on camera+detection; `admin/audit_portal/views.py::operational_audit` on actor; `cameras/video_processing.py` on upload.camera).
- Expensive surfaces are explicitly capped: PDF generation 20/min per user-or-IP with the counter keyed AFTER auth so probes cost nothing (`challans/views.py::_pdf_rate_limited`), search 20/60s, `MAX_FRAMES_PER_UPLOAD = 500` in the video processor, ONNX sessions cached module-level.
- WhiteNoise immutable caching eliminates repeat static cost; `STATICFILES` post-processing produced 262 fingerprinted files with gzip/brotli variants (audit §6).
- The realtime path avoids polling entirely (Socket.IO push), and emits are best-effort non-blocking (`detections/pipeline.py::_emit_realtime` swallows transport errors by design).

**Issues found**
- P2 | N+1 and full-scan patterns in the pipeline hot path: `detections/pipeline.py::frame_tracking` loads all prior detections in a 45s window for the camera and normalizes plates in Python; `_check_chain_integrity` pulls every challan plate for the camera in 24h into memory and normalizes one-by-one. At city scale these are per-frame O(n) scans. Fix: store a normalized plate column with an index and use `__in` filters.
- P3 | `SystemSettings.get()` is called per frame (AI config) and per template render (context processors `admin/dig_portal/context_processors.py`); each call is a DB query plus dict merges. Fix: short-TTL cache.
- P3 | Rate limiter counters live in locmem (`CACHES` default) - accurate only in the mandated single-worker topology; the audit (F30/P7) documents the Redis migration.
- P3 | Video processing runs the full AI pipeline on every sampled frame AND twice more for sequential evidence on plate hits (3x inference per hit) inside a daemon thread (`start_processing_async`); a 500-frame upload on CPU is minutes of blocking work with no worker queue. Fix: move to a real task queue (or document the single-upload-at-a-time expectation) and add a progress heartbeat.
- P3 | `Shift.auto_assign_officer` full-table scan (see Role 4).
- P3 | Non-atomic cache read-modify-write in the two sliding-window counters (`challans/views.py::_pdf_rate_limited` and `_check_rate_limit` both do `cache.get` then `cache.set`): bursts can undercount (audit P11). Fix: `cache.incr` with add-fallback.
- P3 | PDF regeneration (`?regen=1`) re-runs WeasyPrint (HTML -> CSS -> PDF) synchronously in the request; even with the 20/min cap, ten concurrent regens on one worker stall the portal. Fix: pre-generate at issuance (already done in `save_challan_pdf`) and make regen an IT-only action.

**Score: 7/10**

---

## Role 16 | Accessibility Specialist

**Verdict: NEEDS ATTENTION**

**Strengths**
- Keyboard support in the flagship operator flow is real: `static/js/pages/officer-review-queue.js` implements single-key hotkeys (C/R/F/A) and ArrowUp/ArrowDown navigation, and correctly suppresses hotkeys while focus is in an input/textarea (lines 10-20).
- Semantic landmarks exist in base.html: `<nav class="sc-nav">`, breadcrumb nav with `aria-label="breadcrumb"`, sidebar toggle with `aria-label`, user menu button with `aria-haspopup`/`aria-expanded`.
- Focus-visible styling and reduced-motion handling are present in the design system CSS (`static/css/safe-city.css` includes `:focus-visible` and `prefers-reduced-motion` rules).

**Issues found**
- P2 | ARIA coverage is sparse across 141 templates: icon-only buttons (e.g. table row actions, chart cards, live-monitor tiles) frequently lack `aria-label`; status is conveyed by color chips without `role="status"`. Fix: sweep icon-only controls for labels; add text alternatives on the CCTV wall tiles (camera id + health state as text, not just color).
- P3 | The single-key hotkeys have no visible legend/affordance documented in the queue template for non-keyboard-first users, and no `aria-keyshortcuts` attributes. Fix: add a help popover listing C/R/F/A and arrows.
- P3 | Contrast on dark monitor UIs (`--sc-text-faint` #8A94B0 on navy) is likely below 4.5:1 for small text; no automated contrast test exists. Fix: run a palette audit and adjust faint tokens on dark surfaces.
- P3 | Charts (Chart.js) have no described-by text alternatives for screen readers on any dashboard checked.

**Score: 6/10**

---

## Role 17 | Documentation Specialist

**Verdict: PASS WITH NOTES**

**Strengths**
- `README.md` is honest and precise: the 5-check evidence table, the "no manual annotation anywhere" statement, role/login matrix, URL map, test narrative, sandbox-by-default integrations, and the "no view can mark a challan PAID on its own" guarantee are all verifiable against code.
- `docs/SECURITY_AUDIT.md` is the strongest document in the repo: methodology, threat model table, 31 findings with status, rate-limit matrix, final CSP text with rationale, static/media serving recipes, prioritized residual-risk list P1-P11, validation evidence table, and a files-changed manifest.
- `docs/REALTIME.md` covers architecture diagram, enablement commands, the single-worker requirement, server-side emit API, client DOM events, and the documented-not-implemented multi-worker Redis path.
- `SECURITY.md` (104 lines) summarizes the control set for auditors; `.env.example` and inline settings comments (CSP rationale block in `wrongway_system/settings.py` lines 292-322) are unusually good in-code documentation.

**Issues found**
- P2 | No runbook: nothing covers restore-from-backup, camera-worker restart, secret rotation, or "AI engine down" first response. The knowledge exists but is scattered. Fix: `docs/RUNBOOK.md` with 5-10 incident recipes.
- P3 | README says "PDF (four layouts)" while `challans/pdf_service.py` TEMPLATE_MAP ships 7 layouts plus aliases - the doc lags the product.
- P3 | No docs for the audit PDF templates (8 templates under `templates/audit_templates/`) or the ads/banner system beyond the security audit's XSS note.
- P3 | `wrongway_system/test_settings.py` exists but is not referenced by any documentation; its purpose should be stated in the testing section.

**Score: 8/10**

---

## Role 18 | Business Analyst

**Verdict: PASS WITH NOTES**

**Strengths**
- Fine collection flow is closed-loop: fine defaults configurable per violation in `SystemSettings.default_fines` (`get_fine`), PSID generated with a Luhn-style check digit per challan (`Challan.psid`), QR payload for mobile banking, payment methods governed by `PaymentMethod` status/type with cash and bank transfer excluded from online settlement, and settlement only via signed webhook or rate-limited demo checkout.
- Revenue reporting is real: `templates/dashboard/dig/revenue_dashboard.html`, `financial_reports.html`, `financial_audit.html` (total collected aggregation in `admin/audit_portal/views.py::financial_audit`), payment lists and manual record-payment with permission gating.
- Appeal escalation is structured with stage-appropriate fields (officer/ssp/dig comment + reviewer + timestamp each), `advance_to_ssp`, `advance_to_dig`, `finalize` writing to the correct stage columns (H5 fix note in code), appeal-approved auto-void of unpaid challans (H1 fix note), and `has_active_appeal` preventing duplicate parallel appeals.
- Blacklist policy is enforced at the AI layer (blacklisted plates can never produce a violation flag, `detections/ai.py`), managed by DIG (`templates/dashboard/dig/blacklist_list.html` / `blacklist_add.html`), with reason and audit attribution (`BlacklistEntry.created_by`).

**Issues found**
- P3 | Escalation chain in code is OFFICER -> SSP -> DIG; the supervisor role has no appeal stage even though `SupervisorProfile` exists (see Role 12). Confirm intended org process and align docs.
- P3 | `SspProfile.high_value_threshold` (default PKR 5000) is defined but no automation routes high-value challans to SSP review; `approve_high_value_challan` permission exists in `accounts/permissions.py` but the threshold trigger is manual.
- P3 | No refund path in the business flow: `PaymentTransaction.STATUS_REFUNDED` exists but no view or command issues refunds (appeal approval only voids unpaid challans). A paid-then-approved appeal has no remedy. Fix: define the refund SOP and either implement or explicitly mark out-of-scope.

**Score: 8/10**

---

## Role 19 | SRE/Reliability

**Verdict: PASS WITH NOTES**

**Strengths**
- Health-check tooling is layered: `admin/dig_portal/management/commands/verify_system.py` (14 named route reversals + demo-data/role presence), `check_production.py`, and `cameras/management/commands/check_camera_heartbeats.py` for camera liveness; `psutil` in requirements backs the DIG system-health dashboard.
- Failure modes degrade rather than crash: AI engine down -> `_get_plate_detector`/`_get_side_classifier` return None, `_detect_plates` returns empty, detections are rejected/queued, the site stays up; PostgreSQL down -> settings refuse boot with an actionable message; realtime layer unavailable -> `wrongway_system/asgi.py` falls back to plain Django ASGI; emit failures never raise (`_emit_realtime`); PDF chain degrades to ReportLab; email failures log and continue (`detections/pipeline.py::issue_challan` wraps notify in try/except).
- Camera health is modeled (`health_status` online/offline/degraded/unknown, `last_frame_at`, `mark_online`/`mark_offline` helpers) with heartbeat ingestion at `/api/v1/heartbeat/` and cleanup command `cameras/management/commands/cleanup_cameras.py`.
- Logging is production-shaped (rotating files, per-subsystem loggers) and errors are centralized through custom handlers (HANDLER400-503 in settings).

**Issues found**
- P2 | The backup path has no restore drill documented and no scheduled backup job: backups are JSON files downloadable from the IT portal; nothing verifies restorability. Fix: a `restore_backup` dry-run command + documented drill cadence.
- P3 | No process supervision or health-probe HTTP endpoint (`/healthz`) for a load balancer; the only liveness signal is the app responding at all. Fix: add a cheap `/healthz/` view checking DB + static manifest + model files.
- P3 | Video processing daemon threads die with the web process and have no retry/queue semantics; a crash mid-upload leaves status=processing forever. Fix: a sweeper command that marks stale processing uploads as failed after N hours.
- P3 | Single-worker uvicorn means every AI frame, PDF render, and request shares one process; a heavy upload slows the whole portal. Fix: queue video work to a separate process (even a cron-invoked command) and keep the web worker light.

**Score: 7/10**

---

## Role 20 | Integration Engineer

**Verdict: PASS WITH NOTES**

**Strengths**
- Sandbox/real modes are first-class: `integrations/mode.py` gates every external call; `SystemSettings.integration_mode` (demo/real) with per-service URL/key fields; NADRA demo mode returns fixture CNICs (`integrations/nadra.py::_SANDBOX_CNICS`) and format-only validation otherwise; Excise follows the same pattern (`integrations/excise.py`).
- Payment HMAC flows are implementable today: JazzCash v1.1 secure hash (sorted keys, salt-prefixed HMAC-SHA256, uppercase) in `integrations/payments.py::_jazzcash_secure_hash`; sandbox vs live endpoints switch on configured keys; missing keys degrade to `mode='demo'` local checkout so the UI flow is always completable; EasyPaisa and card/stripe paths structured similarly.
- Camera worker protocol is complete and authenticated: enrollment via one-time token (`camera_worker/enroll.py`), per-camera UUID API key used as Bearer on `/api/v1/ingest/` and `/api/v1/heartbeat/` (`cameras/views.py`), RTSP with TCP transport + HTTP snapshot fallback, per-camera threads with graceful stop, 60s heartbeat cadence, and ingest rate limiting (300/min) that the worker respects by design (interval >= 2s).
- Webhook contract is defensive: multi-provider field aliases (`pp_BillReference`, `orderId`, `basket_id`...), non-success statuses acknowledged but ignored, challan resolution by ticket, txn_ref, transaction row, or audit-log fallback (`payments/webhook.py::_resolve_challan`).

**Issues found**
- P3 | No retry/backoff or circuit breaker on outbound NADRA/Excise calls (`integrations/nadra.py` uses a bare `requests.get` with 8s timeout; failures just log). Fix: small retry helper with jittered backoff and a failure counter surfaced in system health.
- P3 | Webhook success-detection is an allow-list of strings (`_is_success`); a provider returning "121" (JazzCash code for approved) would be missed. Fix: map provider-specific response codes explicitly per integration.
- P3 | No contract tests or recorded fixtures for the external APIs; sandbox NADRA only covers three CNICs. Fix: add a testskeleton with mocked responses asserting field mapping.

**Score: 8/10**

---

## Role 21 | Fraud Analyst

**Verdict: PASS WITH NOTES**

**Strengths**
- Duplicate-challan suppression is a hard evidence check: `_check_chain_integrity` blocks any new challan for the same normalized plate on the same camera within 24h (`detections/pipeline.py` lines 222-243), with a dedicated test (`test_duplicate_plate_within_24h_is_blocked`).
- Payment verification paths are hardened against double-credit: webhook settlement under `select_for_update` (F1 fix), demo checkout atomic guarded claim (F2 fix), single-use transaction references (`test_demo_checkout_reference_is_single_use`), guest pay views proven to never mutate status, and `txn_ref` uniqueness enforced at the DB (`PaymentTransaction.txn_ref unique=True`).
- Anomaly detection exists in the audit portal (`admin/audit_portal/views.py::_detect_anomalies`): `HIGH_DISMISSAL_RATE` (officers rejecting >= 5 appeals), `ORPHAN_PAYMENT` (PAID without paid_at - HIGH severity), `ZERO_AMOUNT_CHALLAN` - surfaced on both dashboard and a dedicated anomaly-alerts page.
- Every staff mutation is audit-logged with actor + IP (middleware), and ticket numbers are sequential numeric with a `while exists()` guard, making gaps obvious to review.

**Issues found**
- P2 | The audit-log fallback in `_resolve_challan` scans the last 50 `challan.payment_submitted` entries when ticket/txn lookup fails - an attacker who can post webhooks with valid HMAC cannot exploit it, but a misrouted or forged-internal reference could settle the wrong challan in edge cases. Fix: resolve strictly by DB references; keep the log scan behind an explicit admin action.
- P3 | Ticket numbers are sequential and guessable; combined with the public PDF token gate this is fine, but ticket-based social engineering ("pay this ticket") benefits from a checksum. Fix: print the PSID check digit on notices (already generated) and verify it at payment initiation.
- P3 | No velocity rule for appeals beyond `django_ratelimit` 5/day per user; a guest with many valid CNICs could mass-file. Fix: per-IP cap on guest appeal POSTs (the F11 validator handles file content, not volume).

**Score: 8/10**

---

## Role 22 | Training/Adoption Specialist

**Verdict: PASS WITH NOTES**

**Strengths**
- Demo accounts are one command away: `admin/dig_portal/management/commands/seed_demo_accounts.py` creates SSP, SUPV, OFFICER, AUDIT, IT, and citizen accounts with role-tagged emails (`officer@safecity.fyp` etc.), refuses to run without `--yes`, prints credentials once, and warns they are dev-only; the first DIG comes from `create_dig_admin`.
- `verify_system.py` doubles as a training sanity script: it confirms all 14 core routes resolve and each role has at least one account before a demo session.
- The role-based sidebar system (`templates/_sidebar/_*.html` per role, selected by `base.html` on `user.role`) gives each persona a stable, scoped navigation - a new officer sees exactly the review queue, flagged list, appeals, camera feed, performance, and profile; nothing else.
- Learning curve is reduced by consistent interaction patterns: same card/table/chart components (DataTables + Chart.js), same SweetAlert confirmations, same keyboard model in the review queue.

**Issues found**
- P3 | No in-product guided tour or contextual help; the 5-check evidence terminology (`plate_readability`...`chain_integrity`) appears in review notes without a legend. Fix: a collapsible "what do these checks mean" panel on the review-queue template.
- P3 | Suggested screen-recording scripts (for the FYP/demo package): (1) public search -> masked detail -> guest appeal with CNIC; (2) officer queue hotkeys C/R/F/A across a 3-frame evidence stepper; (3) video upload -> live progress -> auto-challan with 5/5 checks and PDF; (4) DIG revenue + heatmap + audit-template export; (5) IT payment-method config -> JazzCash sandbox checkout -> webhook settles -> citizen sees PAID; (6) banner + alert publishing to demonstrate the notification/ads system. None of these scripts exist in docs.
- P3 | Demo passwords are fixed strings; if a demo instance is ever exposed, every role is one known password away. Fix: generate random passwords at seed time and print them once.

**Score: 8/10**

---

# EXECUTIVE SUMMARY

## Role score card

| # | Role | Verdict | Score |
|---|------|---------|-------|
| 1 | Project Manager | PASS WITH NOTES | 8/10 |
| 2 | Software Engineer | PASS WITH NOTES | 8/10 |
| 3 | System Architect | PASS WITH NOTES | 8/10 |
| 4 | Database Engineer | PASS WITH NOTES | 8/10 |
| 5 | AI/ML Expert | PASS WITH NOTES | 8/10 |
| 6 | Security Engineer | PASS WITH NOTES | 8/10 |
| 7 | QA Lead | PASS WITH NOTES | 7/10 |
| 8 | UI/UX Expert | PASS WITH NOTES | 8/10 |
| 9 | Frontend Engineer | PASS WITH NOTES | 7/10 |
| 10 | Backend Engineer | PASS | 9/10 |
| 11 | DevOps Engineer | PASS WITH NOTES | 8/10 |
| 12 | Product Engineer | PASS WITH NOTES | 8/10 |
| 13 | Data Privacy Officer | PASS WITH NOTES | 7/10 |
| 14 | Legal/Compliance Analyst | PASS WITH NOTES | 8/10 |
| 15 | Performance Engineer | PASS WITH NOTES | 7/10 |
| 16 | Accessibility Specialist | NEEDS ATTENTION | 6/10 |
| 17 | Documentation Specialist | PASS WITH NOTES | 8/10 |
| 18 | Business Analyst | PASS WITH NOTES | 8/10 |
| 19 | SRE/Reliability | PASS WITH NOTES | 7/10 |
| 20 | Integration Engineer | PASS WITH NOTES | 8/10 |
| 21 | Fraud Analyst | PASS WITH NOTES | 8/10 |
| 22 | Training/Adoption Specialist | PASS WITH NOTES | 8/10 |

Average score: **7.8/10**. One PASS (Backend), twenty PASS WITH NOTES, one NEEDS ATTENTION (Accessibility).

## Overall project grade

**A- (8.2/10) | Production-ready for a controlled pilot, with a short P2 punch-list**

The SAFE CITIES PROJECT delivers an unusually complete, internally consistent enforcement platform: a fully automated wrong-way-only pipeline with five hard evidence gates, tamper-evident SHA-256 custody, 3-frame sequential evidence, cars-only classification, a blacklist enforced inside the AI layer, server-side-only payment settlement with atomic idempotency, layered rate limiting, a real CSP with nonce infrastructure, per-role portal isolation with tests, a 7-template challan PDF system with a verified one-A4-page guarantee, an 8-template audit PDF export system, and a documented single-process realtime layer. The engineering honesty is notable: `docs/SECURITY_AUDIT.md` and in-code fix notes (H1/H3/H5, F1/F2) show defects were found, fixed, and locked with tests.

The grade is held below A by: five residual security items the project's own audit already flagged (banner XSS, officer detail scoping, duplicate-issuance race, upload whitelist gaps, `unsafe-inline`), the absence of any tests for the six admin portal view modules, unbounded evidence retention, and the single-process coupling of realtime + rate limiting.

## Top 10 priority actions

| # | Priority | Action | Files | Why |
|---|----------|--------|-------|-----|
| 1 | P2 | Sanitize or escape `Banner.html_content`; drop `\|safe` in the public ads partial | `admin/dig_portal/views.py` (banner_add/edit), `templates/challan/_public_ads.html` | Stored XSS on the public homepage from any compromised DIG/IT account (audit F23) |
| 2 | P2 | Camera-scope `detection_detail` with `scope_detections` / CameraAssignment check | `admin/officer_portal/views.py:155` | IDOR: any OFFICER can open any detection by id (audit F22) |
| 3 | P2 | `unique=True` on `Challan.detection` + `select_for_update` in `issue_challan` | `challans/models.py`, `detections/pipeline.py` | Concurrent finalisation can double-issue (audit F26) |
| 4 | P2 | Apply the `_validate_evidence_file` pattern to video upload, citizen appeal evidence, banner images | `video_processor/views.py`, `citizen/citizen_portal/views.py`, `admin/dig_portal/views.py` | Upload whitelist gaps F24/F25/F27 |
| 5 | P2 | Migrate 16+ templates off inline handlers; then remove CSP `script-src 'unsafe-inline'` | `templates/**`, `wrongway_system/settings.py` CSP_SCRIPT_SRC | Closes the largest remaining CSP hole (audit P1); nonce infra already live |
| 6 | P2 | Add per-portal authorization smoke tests for all six admin portal view modules | new `admin/*/tests.py` | 4,096-line DIG module and siblings currently have zero unit tests |
| 7 | P3 | Define retention + purge for detections/evidence/videos; document a DPIA | `detections/models.py`, new management command, `docs/` | Unbounded PII/evidence growth; privacy compliance |
| 8 | P3 | Cache `SystemSettings.get()`; add normalized+indexed plate column for track/duplicate queries | `admin/dig_portal/models.py`, `detections/pipeline.py` | Per-frame DB hits and O(n) Python scans on the hot path |
| 9 | P3 | Purge legacy enforcement-agency branding placeholder strings (department defaults and region/city choice labels) from defaults/templates | `admin/dig_portal/admin_profiles.py`, 4 templates, `static/js/pages/it-challan-designer.js` | Branding policy: SAFE CITIES PROJECT only |
| 10 | P3 | Encrypt `PaymentMethod.config` and NADRA/Excise API keys at rest; remove default PG password for DEBUG=False | `admin/it_support_portal/models.py`, `admin/dig_portal/models.py`, `wrongway_system/settings.py` | Secrets currently plaintext in DB/env defaults |

## Compliance checklist

| Requirement | Status | Evidence |
|---|---|---|
| Branding: SAFE CITIES PROJECT only (no legacy agency names) | PARTIAL | Titles/headers correct everywhere (`templates/base.html` line 8, `legal_notice_99a.html`); but placeholder/default strings found in `admin/dig_portal/admin_profiles.py` (department default, region list entries), `templates/dashboard/dig/admin_add.html:56`, `officer/profile.html:87-88`, `dig/self_profile.html:68`, `it_support/staff_list.html:62`, and `static/js/pages/it-challan-designer.js:157` |
| No manual annotation anywhere | PASS | `Annotation` model deleted (`detections/migrations/0011`), removal locked by `detections/tests.py::RemovedFeatureTests` and `accounts/tests.py::AnnotationRemovalTests`; pipeline docstring states exclusive issuance |
| Wrong-way violations only | PASS | `Challan.ENABLED_VIOLATIONS = [WRONG_WAY]`; `issue_challan` hardcodes `violation_type=Challan.WRONG_WAY`; `effective_violation_type` maps only wrong_way |
| 3-frame sequential evidence | PASS | `Detection.evidence_frame_2/3` + `evidence_frames_meta`; `cameras/video_processing.py::_capture_sequential_frames`; `SEQUENTIAL_EVIDENCE_MIN_FRAMES = 3` in `detections/pipeline.py`; `evidence_frames()` assembler |
| One-A4-page challans | PASS | `challans/pdf_service.py` pypdf page-count verification with compact re-render and ReportLab single-page fallback; audit doc records the guarantee |
| One evidence image on the PDF | PASS | `_evidence_image()` returns exactly one image: annotated frame first, raw frame fallback; module docstring guarantees "Exactly ONE large evidence image" |
| English-or-Urdu policy | PASS | `CitizenProfile.preferred_language` choices en/ur; `templates/challan/challan_templates/urdu_a4.html` with Noto Nastaliq Urdu loaded in base.html |
| RBAC hierarchy | PASS | `accounts/permissions.py` (114 permissions, role levels, reports_to/manages/can_override) + `permission.json` + decorator suite; tested by `PermissionMatrixTests` |
| Portal isolation | PASS | `PortalIsolationMiddleware` path-to-role map + per-view decorators + `PortalIsolationTests` cross-role redirect proof |

## Project statistics (measured, excluding `staticfiles/` build artifacts and venv)

| Metric | Count |
|---|---|
| Python files (total) | 230 |
| Python files (excluding migrations) | 146 |
| Migration files | 74 |
| Model classes (10 model modules) | 30 |
| View functions | 257 |
| URL route patterns (14 urls.py modules) | 346 |
| HTML templates | 141 |
| Static assets under `static/` | 109 (47 CSS, 50 JS, 12 images) |
| Lines of Python (excl. migrations) | ~21,666 |
| Lines of Python (incl. migrations) | ~35,000+ |
| Lines of template HTML | ~18,323 |
| Lines of CSS | ~8,125 |
| Lines of JS | ~5,977 |
| Total source lines (py+html+css+js, excl. migrations) | ~54,000 |
| Unit test functions (5 test modules) | 54 |
| Pen-test assertions (`scripts/pen_test.py`) | 44 (all green per audit §8) |
| Middleware entries | 14 (7 Django + WhiteNoise + 6 custom) |
| Django apps | 15 (incl. `integrations`) |
| Challan PDF templates | 7 (+2 aliases in TEMPLATE_MAP) |
| Audit PDF templates | 8 |
| Role portals | 7 (DIG, SSP, SUPERVISOR, OFFICER, AUDIT, IT SUPPORT, CITIZEN) |

## Closing note

The project's strongest asset is that its guarantees are executable: every compliance claim in the README (5 checks, no manual annotation, wrong-way only, single-page PDF, one evidence image, server-side settlement) maps to code and, in most cases, to a test that fails if the guarantee breaks. The fastest path to an A is to finish the project's own residual list (items 1-5 above are all pre-sketched in `docs/SECURITY_AUDIT.md` §7), close the portal-test gap, and put a boundary on data retention.

---

# APPENDIX A | Route inventory (14 URL modules, 346 patterns)

| URL module | Mount point | Purpose |
|---|---|---|
| `wrongway_system/urls.py` | `/` | Root: mounts everything, error handlers, legacy redirects, django-admin |
| `challans/urls.py` | `/` | Public search, challan detail, guest pay, PDF, signed links |
| `auth_portal/urls.py` | `/auth/` | Admin + citizen login/signup/forgot/reset, role redirect |
| `admin/dig_portal/urls.py` | `/portal/dig/` | DIG command center (largest route set: cameras, staff, banners, blacklist, reports, settings, backups, payments) |
| `admin/ssp_portal/urls.py` | `/portal/ssp/` | SSP dashboard, high-value review |
| `admin/supervisor_portal/urls.py` | `/portal/supervisor/` | Supervisor dashboard, team performance |
| `admin/officer_portal/urls.py` | `/portal/officer/` | Review queue, detection detail, flagged list, appeals, camera feed, tracking, performance |
| `admin/audit_portal/urls.py` | `/portal/audit/` | Dashboard, anomalies, compliance, financial/operational audit, exports |
| `admin/it_support_portal/urls.py` | `/portal/it/` | Staff, payment methods, challan + audit templates, backups, designer |
| `citizen/citizen_portal/urls.py` | `/portal/citizen/` | Citizen home, pay, appeals, tracker, profile, password |
| `cameras/urls.py` | `/api/` | v1 enroll / ingest / heartbeat (Bearer-auth camera API) |
| `payments/urls.py` | `/api/v1/payment/` | HMAC webhook, demo checkout |
| `realtime/urls.py` | `/realtime/` | JSON APIs + shared chart endpoints |
| `video_processor/urls.py` | `/video/` | Batch video upload + processing status |

# APPENDIX B | Middleware inventory (14 entries, in order)

| # | Middleware | Source | Responsibility |
|---|---|---|---|
| 1 | SecurityMiddleware | Django | SSL redirect, HSTS (production) |
| 2 | WhiteNoiseMiddleware | whitenoise 6.x | Compressed static serving, immutable cache headers |
| 3 | SessionMiddleware | Django | Sessions (8h, HttpOnly, SameSite=Lax, safecity_sessionid) |
| 4 | CommonMiddleware | Django | APPEND_SLASH etc. |
| 5 | CsrfViewMiddleware | Django | CSRF (safecity_csrftoken, custom failure view) |
| 6 | AuthenticationMiddleware | Django | Auth (PhoneOrEmailBackend + ModelBackend) |
| 7 | MessageMiddleware | Django | Flash messages |
| 8 | XFrameOptionsMiddleware | Django | Clickjacking baseline (DENY) |
| 9 | AuditLogMiddleware | admin/dig_portal/middleware.py | Audit every staff mutating request (actor, path, IP) |
| 10 | AccountLockoutMiddleware | admin/dig_portal/middleware.py | Force-logout locked accounts mid-session |
| 11 | SecurityHeadersMiddleware | admin/dig_portal/middleware.py | CSP composition + per-request nonce + frame-ancestors embed exception |
| 12 | PortalIsolationMiddleware | admin/dig_portal/middleware.py | /portal/<role>/ prefix to role enforcement |
| 13 | RateLimitMiddleware | wrongway_system/security/middleware.py | Login 8/60s, portal POST 120/60s, malicious query-string rejection |
| 14 | RequestSizeLimitMiddleware | wrongway_system/security/middleware.py | Body caps 5 MB default / 50 MB upload paths |

# APPENDIX C | Evidence-check reference (detections/pipeline.py)

| Check | Constant | Threshold | Failure effect |
|---|---|---|---|
| plate_readability | `OCR_MIN_CONFIDENCE = 0.60`, `PLATE_PATTERN = ^[A-Z]{2,3}\d{1,4}$` | OCR conf >= 0.60 + valid PK format | Queued for officer review |
| frame_consistency | `TRACK_MIN_FRAMES = 2`, `TRACK_MIN_CONSISTENCY = 0.60`, `SINGLE_FRAME_HIGH_CONF = 0.90`, `TRACK_WINDOW_SECONDS = 45` | Corroborated track (>= 2 frames, >= 0.60 agreement) or single frame >= 0.90 or 3-frame sequential agreement | Queued for officer review |
| violation_logic | side conf >= 0.60 | Classified side == camera.violation_side AND violation flag | Queued for officer review |
| image_evidence | `PLATE_CROP_MIN_HEIGHT = 18` | Raw frame + plate crop present, crop height >= 18 px | Queued for officer review |
| chain_integrity | 24h duplicate window | SHA-256 digest computed AND no same-plate challan on same camera within 24 h | Queued for officer review (duplicate detail recorded) |

Auto-ignore path (before checks): no usable plate box, or no violation and confidence below `_doubt_floor(auto_thr)` = `max(0.35, auto_thr - 0.25)` -> status REJECTED, no evidence stored.

# APPENDIX D | Challan + audit PDF template inventory

Challan templates (`templates/challan/challan_templates/`, mapped in `challans/pdf_service.py::TEMPLATE_MAP`):
1. `modern_a4.html` (also aliased as `safecityfyp_classic` - the SystemSettings default)
2. `classic_a4.html`
3. `legal_notice_99a.html` (Section 99-A Motor Vehicles Ordinance 1965 notice)
4. `digital_slip.html`
5. `compact_receipt.html` (also the overflow re-render guard as `compact_a4`)
6. `enforcement_notice.html`
7. `urdu_a4.html` (Nastaliq Urdu layout for the English-or-Urdu policy)

Audit templates (`templates/audit_templates/`, exported via `admin/audit_portal/audit_pdf.py`, selectable in DIG via `audit_templates_select.html`):
1. `executive_summary.html` 2. `financial_ledger.html` 3. `compliance_matrix.html` 4. `statistical_digest.html` 5. `incident_report.html` 6. `field_inspection.html` 7. `legal_affidavit.html` 8. `government_classic.html` (SystemSettings default `audit_pdf_template`)

Both systems also accept DB-stored custom templates (`ChallanTemplate`, `AuditPDFTemplate` models with `db:<id>` keys) authored in the IT designer, with writers restricted to `@it_required`.
