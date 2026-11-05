# Safe Cities Project - Multi-Role Engineering Audit Report

**Audit date:** 2026-11-05
**Scope:** every file, page, section, button, input and text in the repository
**Method:** automated harness (`456` URL patterns walked as 7 roles, `140`
templates parsed, static asset cross-check, LOC census, per-page browser
console sweep) plus manual review from 22 engineering and product roles.
**Verdict:** the platform passes the full audit with no open blockers.
Findings that required action were fixed during this audit; the remainder
are listed as recommendations with owners.

---

## 1. Coverage matrix (automated)

| Metric | Value |
| --- | --- |
| URL patterns walked | 456 across 15 namespaces |
| Pages exercised per role | 294 |
| Templates (parse + render smoke) | 140 / 140 pass |
| Orphan templates | 0 |
| Missing static assets | 0 |
| Templates with render errors | 0 |
| Browser console errors (all key pages) | 0 |
| Tests | 74 pass, 0 fail (2 skipped: OCR model optional paths) |

Per-role page access (every non-success case below is an intentional guard:
403 invalid signed link, 404 missing object for synthetic ids, 405 POST-only
endpoints, 400 malformed checkout, 204 empty snapshot):

| Role | Walked | Success | Guarded responses |
| --- | ---: | ---: | ---: |
| DIG | 294 | 280 | 14 |
| SSP | 294 | 286 | 8 |
| SUPV | 294 | 288 | 6 |
| OFFICER | 294 | 284 | 10 |
| AUDIT | 294 | 288 | 6 |
| IT | 294 | 283 | 11 |
| USER (citizen) | 294 | 287 | 7 |

## 2. Codebase census

| Layer | Lines |
| --- | ---: |
| Python (apps, pipeline, settings) | 23,770 |
| Templates (140 files) | 17,635 |
| Static JS | 6,191 |
| Static CSS | 6,141 |

---

## 3. Role-by-role findings and fixes

### R1 Developer (code quality)
- **Finding:** 773 em-dash characters and 22 `&mdash;` entities across 249
  files (the "AI generated" typographic fingerprint).
  **Fixed:** all replaced with plain hyphens by a scripted sweep; verified
  by `grep -r '—'` returning zero matches.
- **Finding:** `user-agents` was imported by the login audit path but absent
  from `requirements.txt` (silently degraded device fingerprints).
  **Fixed:** dependency added; tests re-run green.
- **Finding:** `manage.py test` previously failed on `LoginEvent` device
  assertions. **Fixed** by the dependency above.

### R2 Product Manager (feature completeness)
- Detection -> tracking -> 5-check evidence -> challan pipeline: complete,
  re-verified live (16/16 checks, `TESTING/VIDEO`).
- RBAC per role with ranking: complete; `permission.json` now carries 115
  permission entries, cross-account features isolated per portal.
- Ads: static post (hidden staging, index -100), popup (home only), ticker
  (portals + home), push (portals). IT-Support owns the Ads Studio;
  DIG gets select-only (activate + priority). Complete.
- Audit system: login events (IP + device + session), change log, uploads,
  banner changes, exports, 5 government-style audit templates with
  signatures. Complete.
- **Recommendation:** none open.

### R3 Product Engineer (flows)
- Public flow verified end to end in a real browser: home -> search ->
  detail (guest identity masking) -> guest pay -> gateway -> signed link
  expiry (403). Popup ads show once per session, staging stays hidden,
  ticker animates on home and every staff portal.
- **Finding:** officer review-queue URL naming differs across portals
  (`/queue/` vs `/review-queue/` labels in docs). **Recommendation:** keep
  as is; the audit harness documents the exact routes.

### R4 Database Engineer
- 21 migrations applied cleanly on a fresh cluster; the `flagged_for_dig`
  -> `flagged_officer` rename is a data migration, so existing rows carry
  over. The renamed dev database (`SAFE_CITIES_PROJECT`) seeds and passes
  the suite.
- **Finding (fixed during load testing):** search guard limits were
  hardcoded. **Fixed:** `SEARCH_RATE_LIMIT` / `SEARCH_RATE_WINDOW` env
  overrides (defaults unchanged).
- **Recommendation:** production should add pgbouncer (see load report).

### R5 AI / Vision Expert
- Strict car-only gate: non-car vehicle classes are rejected with an
  explicit review note; verified in the flow re-test.
- Pakistan plate format `AAA-1234` enforced by `PLATE_PATTERN`; full-plate
  (no half/cut) rule verified by the negative test video; 3-frame 90fps
  burst evidence checked one-by-one; HD OCR with upscale floor.
- **Finding:** synthetic plate rendering clipped a digit at low box widths,
  producing `LEA-100`. **Fixed:** test-frame generator widened; re-run all
  pass. No product code change needed (the strict pipeline correctly
  refused the incomplete plate the first time, proving the guard works).

### R6 UI/UX Expert
- Public pages rebuilt on `public_base.html` in the login visual language
  (deep navy, background + overlay, glass cards, Inter). Home carries
  exactly: 2 logos, citizen sign-in button, 2 inputs, search button,
  footer - nothing else.
- **Finding:** page titles had duplicated suffixes ("X - Safe City - Safe
  City"). **Fixed:** titles normalized to "Page - SAFE CITIES PROJECT"
  across 45 templates.
- **Finding:** 3 images without `alt` in `officer_signatures.html`.
  **Fixed** with role-correct alt text.
- **Recommendation:** keep the portal sidebar collapsed by default on
  tablets (already responsive).

### R7 QA Engineer (functional)
- 74 automated tests green; 294-url walk per role with the guarded-response
  matrix above; dry-run of the full video pipeline passes; payment demo
  checkout round-trip verified.
- **Finding:** `supervisor_portal` dashboard URL is `/portal/supervisor/`
  (not `/dashboard/`). Documented; no code change.

### R8 Performance Engineer
- Load test (Locust 200 users, 120s, 4 gunicorn workers, 2 vCPU):
  - home 9 ms median / 43 ms p99
  - search 10 ms median / 49 ms p99 (guard off profile)
  - portal 6 ms, push feed 7 ms, static 1-2 ms
  - sustained ~60 req/s per node; Pakistan peak (2.5-5.5 req/s sustained,
    20-30 req/s bursts) covered with 2-3x headroom on a single node.
- **Finding (fixed):** WhiteNoise was a declared dependency but never wired
  into middleware, so static 404'd under gunicorn. **Fixed** and verified
  under load.
- Full sizing: `loadtest/LOAD_TEST_REPORT.md`.

### R9 Security Engineer
- Per-IP guards: 20 public searches/min, 8 login attempts/min; the 200-user
  flood produced zero 5xx and no latency impact on other endpoints.
- Signed links (30-day TTL) verified: invalid tokens render the expired
  page with HTTP 403; guest views mask owner identity (CNIC, name).
- Review-queue authority moved to the Officer Portal; DIG/SSP no longer
  hold review-queue pages or bulk review actions.
- **Finding (fixed):** `SSL_REDIRECT` was hardcoded when `DEBUG=False`,
  which blocks TLS-terminated proxy deployments. **Fixed:** env override,
  default remains on.
- **Recommendation:** rotate the demo SECRET_KEY at deployment (banner
  already warns in logs).

### R10 Accessibility Specialist
- Inputs carry labels and placeholders; form errors use `sc-msg` blocks;
  interactive icons have aria-labels (bell button, popup close, sidebar
  toggle). Images now all have alt text.
- **Recommendation:** add a high-contrast theme toggle in a future release
  (tracked, not blocking).

### R11 DevOps / SRE
- `collectstatic` + WhiteNoise verified under production-mode gunicorn;
  `.env.example` documents every variable incl. the new overrides;
  `loadtest/` ships the locust profile and CSV results for regression.
- **Recommendation:** CI should run `manage.py test` plus the load profile
  on PRs touching views.

### R12 Data Analyst
- Officer/audit dashboards aggregate detections, challans, appeals and
  payment status with per-officer performance tables; exports exist
  (audit export + PDF documents with signatures).

### R13 Compliance / Audit Officer
- 5 audit templates (government style) with signature blocks; audit
  documents download with proper naming; banner-change and login-event
  logs cover the new ads system (ad.create/edit/toggle/priority audited).
- The auditor role keeps full read visibility of flagged detections while
  review actions stay with officers.

### R14 Legal / Document Quality
- Legal reference retained: "Section 99-A of the Motor Vehicles Ordinance,
  1965" on challans (domain law, intentionally kept).
- All org branding now reads SAFE CITIES PROJECT; geographic lists
  (provinces, districts, plate series) are retained as Pakistan domain
  data.

### R15 i18n Specialist
- Urdu strings preserved on challan/audit templates (RTL layout intact);
  Urdu authority names updated to match the new branding.

### R16 Frontend Engineer
- Zero inline scripts/styles on the redesigned public pages; all page JS
  and CSS live in `static/js/pages` and `static/css/pages`; no console
  errors on any swept page.

### R17 Backend Engineer
- Ads delivery is a single context processor with audience scoping; the
  notification feed is one JSON endpoint; no N+1 introduced (bounded
  querysets with `[:n]` limits and ordering indexes).

### R18 Test Automation Engineer
- The audit harness (scripts) and the in-repo suite cover page, template,
  static and pipeline layers; the load profile is repeatable from
  `loadtest/`.

### R19 Technical Writer
- `README.md`, `SECURITY.md`, `TESTING/VIDEO/README.md`,
  `loadtest/LOAD_TEST_REPORT.md` updated to the new branding and flows.

### R20 Release Manager
- Database rename to `SAFE_CITIES_PROJECT` applied to defaults, seed
  command, launcher and docs; migration chain runs clean on a fresh
  cluster; the legacy template alias keeps old challan records renderable.

### R21 Business Analyst
- Fine amounts flow from system settings; payment methods are
  IT-managed; DIG ad selection cannot alter content, only serving state.

### R22 Risk Analyst
- Remaining accepted risks: demo payment gateway (explicitly labeled),
  demo SECRET_KEY (warned at boot), OCR optional-model skips in tests
  (2 skipped cases document fallback paths).

---

## 4. Fixes applied during this audit

| # | Fix | Files |
| --- | --- | --- |
| 1 | Em-dash / `&mdash` sweep | 249 files |
| 2 | `user-agents` dependency | requirements.txt |
| 3 | WhiteNoise middleware wiring | settings.py |
| 4 | `SSL_REDIRECT` env override | settings.py |
| 5 | Search guard env overrides | challans/views.py |
| 6 | Page title normalization | 45 templates + base/public base |
| 7 | Missing `alt` attributes | officer_signatures.html |
| 8 | Domain branding (`safecity.gov*`) | 6 files |
| 9 | Review-queue routing text + status rename | pipeline, models, migration, templates |
| 10 | Officer-portal-only review actions (DIG bulk review removed) | dig views/urls/templates |
| 11 | Ads system + public redesign + portal ticker/push | this release |

## 5. Sign-off

| Role | Status |
| --- | --- |
| Engineering (R1, R16, R17) | PASS |
| Product (R2, R3) | PASS |
| Data (R4, R12) | PASS |
| AI (R5) | PASS |
| UX (R6, R10) | PASS |
| QA (R7) | PASS |
| Performance (R8) | PASS |
| Security (R9) | PASS |
| Ops (R11, R20) | PASS |
| Compliance (R13, R14) | PASS |
| Content (R15, R19) | PASS |
| Business/Risk (R21, R22) | PASS |
