# Safe Cities Project - Load Test Report

**Date:** 2026-11-06 (fresh pass; supersedes the 2026-11-05 run)
**Target:** full public portal + staff portal stack
**Purpose:** validate that the platform carries Pakistan-wide e-challan
traffic and to size a production deployment.

---

## 1. Test environment

| Component | Value |
| --- | --- |
| Host | sandbox, 2 vCPU Intel Xeon, 4 GB RAM |
| App server | gunicorn 26.2, 4 sync workers |
| Mode | `DEBUG=False`, WhiteNoise static serving, plain-HTTP profile (TLS flags off, see §4) |
| Database | PostgreSQL 17 (same host, dedicated data volume) |
| Tool | Locust 2.47, headless, 200 simulated users, ramp 20/s, 120 s per run |
| Profiles | `PublicVisitor` (weight 3) + `StaffUser` (weight 1) = the documented 75/25 mix |

Searches hit the real database (6 challans, 7 banners, 2 ticker ads, 2 push
ads seeded). Every response is fully rendered HTML through the template
engine, context processors and the ads delivery channel.

**Corrections vs the 2026-11-05 pass (harness fixes, app unchanged):**
- The staff profile now logs in with a real account
  (`officer@safecity.fyp`, env-overridable). The previous revision posted
  credentials for `officer@safecities.project` - an account that does not
  exist in this database - so its "staff" traffic silently exercised the
  login page only.
- The previous revision had no `weight` attributes, so the mix was 50/50,
  not the documented 75/25.
- Login success detection now follows the redirect chain (requests follows
  redirects; a rejected login re-renders the password form).

## 2. Results

### 2.1 Protection profile (production defaults)

Default per-IP guards active: 20 public searches / minute / IP and the
login limiter. Single-IP harness: all traffic originates from 127.0.0.1.

| Endpoint | Requests | Blocked (429) | Served | Median | p99 |
| --- | ---: | ---: | ---: | ---: | ---: |
| GET / (home) | 4085 | 0 | 4085 | 9 ms | 670 ms |
| GET /?plate&cnic (search) | 2045 | 1965 | 80 | 2 ms | 710 ms |
| GET /portal/officer/ (auth) | 757 | 0 | 757 | 35 ms | 790 ms |
| GET /auth/notifications/feed/ (auth) | 198 | 0 | 198 | 8 ms | 810 ms |
| GET /static (css + js) | 1452 | 0 | 1452 | 2 ms | 750 ms |
| POST /auth/admin/login/ | 50 | 1 | 49 | 1400 ms | 2100 ms |

Aggregate: 8637 requests, 72.5 req/s, overall median 8 ms. No 5xx in any
run. The 429 column is the abuse protection doing its job: a single source
IP flooding the public search is capped while every other endpoint -
including fully authenticated staff pages - stays unaffected.

### 2.2 Capacity profile (search guard effectively removed)

`SEARCH_RATE_LIMIT=100000`. Note: the previously documented 600/min
relaxation still sheds load in this harness - the offered single-IP search
rate is ~1030/min - so the raw-capacity number requires the guard removed.

| Endpoint | Requests | Failures | Median | p90 | p99 | Throughput |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GET / (home) | 4057 | 0 | 10 ms | 26 ms | 1.4 s | 34.0 req/s |
| GET /?plate&cnic (search) | 2018 | 0 | 12 ms | 29 ms | 1.5 s | 16.9 req/s |
| GET /portal/officer/ (auth) | 743 | 0 | 46 ms | 100 ms | 1.4 s | 6.2 req/s |
| GET /auth/notifications/feed/ (auth) | 177 | 0 | 8 ms | 20 ms | 1.1 s | 1.5 req/s |
| GET /static css + js | 1310 | 0 | 2 ms | 14 ms | 1.5 s | 11.0 req/s |
| POST /auth/admin/login/ | 50 | 0 | 3.8 s* | 4.3 s | 4.6 s | 0.4 req/s |

Aggregate: 8405 requests, **70.5 req/s sustained, 0 failures**, median
11 ms.

\* The login-POST latency is an on_start burst artifact: 50 simulated
staff authenticate within seconds of the ramp while all 200 users are
spinning up on 2 vCPU. A single login measured in isolation (curl with
CSRF token, argon2 verification included) completes in **239 ms**.

**Single-node capacity: ~70 req/s on 2 vCPU / 4 workers.** Latency
percentiles swing between runs (p99 670 ms - 1.5 s) on this shared
sandbox; medians are stable (home 9-10 ms, search 12 ms, static 2 ms).

## 3. Pakistan-scale sizing

Working figures (public census / PTA / excise registry magnitudes):

| Metric | Value used |
| --- | --- |
| Population | ~240 M |
| Registered vehicles | ~6.5 M |
| Active internet users | ~87 M |
| Unique portal visitors on a deadline day (SMS campaign, due-date reminders) | 300k-500k |
| Peak hour share | 15% of daily traffic |
| Peak-hour visits | 45k-75k |
| Average session | 4-6 requests (home, search, detail, PDF, static) |
| Pages per second at peak | 50k-75k requests / 3600 s / 4-6 per session = **2.5-5.5 req/s sustained, 20-30 req/s minute-bursts** |

A single 2-vCPU node already delivers 70 req/s, which covers the national
peak with 2-3x headroom. Recommended production topology:

1. **2 app nodes** (4 vCPU, 8 workers each) behind a TLS-terminating load
   balancer with a shared PostgreSQL primary + hot standby.
2. Postgres connection pooling (pgbouncer, 20-30 connections per app node;
   `CONN_MAX_AGE=60` is already set).
3. Object storage / CDN for challan PDFs and ad images; WhiteNoise already
   serves fingerprints from the app tier during rollout.
4. Keep the per-IP guards (20 searches/min) - they absorbed a 200-user
   flood with zero 5xx and no latency impact on other endpoints.
5. Autoscale trigger: sustained 70% worker CPU for 5 minutes or p95 > 250 ms
   on `GET /` for 2 minutes.

## 4. Bottlenecks observed and actions taken

| Finding | Action |
| --- | --- |
| Secure cookie flags (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) are forced on when `DEBUG=False`, so no cookie ever travels back over the plain-HTTP load profile - every login POST failed with "CSRF cookie not set" (403) | Env overrides added (default unchanged, on in production) - same pattern as the existing `SSL_REDIRECT` override |
| The locustfile pointed at a non-existent staff account and had no class weights; its "staff" traffic exercised the login page only | Credentials now env-overridable with real defaults; weight 3:1 added; success detection follows redirects and rejects the re-rendered form |
| Login limiter counters are per-worker (locmem) under the 4-worker profile, so single-IP bursts only partially trip them (this pass: 1 of 50 logins 429'd; an earlier identical run shed 41) | Known limitation (documented in `docs/SECURITY_AUDIT.md` P7); switch to Redis before scaling beyond one worker per node |
| Static files returned 404 under gunicorn (whitenoise was a dependency but never wired) | `whitenoise.middleware.WhiteNoiseMiddleware` added; `collectstatic` verified (2026 pass) |
| HTTPS redirect is hardcoded when `DEBUG=False`, blocking plain-HTTP load profiles behind a TLS proxy | `SSL_REDIRECT` env override added (default stays on) |
| Search guard constants were hardcoded | `SEARCH_RATE_LIMIT` / `SEARCH_RATE_WINDOW` env overrides added (defaults unchanged) |
| Aggregate p99 spikes coincide with locust ramp bursts on 2 vCPU | Acceptable at this scale; production runs on 4 vCPU nodes per the sizing above |

## 5. Reproducing

```bash
# production-style server (plain-HTTP load profile)
DEBUG=false ALLOWED_HOSTS=localhost,127.0.0.1 SSL_REDIRECT=off \
SESSION_COOKIE_SECURE=off CSRF_COOKIE_SECURE=off \
SECRET_KEY=<key> PG_PASSWORD=<password> \
gunicorn -w 4 -b 127.0.0.1:8010 wrongway_system.wsgi:application

# protection profile (defaults)
locust -f loadtest/locustfile.py --headless -u 200 -r 20 -t 120s \
    --host http://127.0.0.1:8010 --csv loadtest/results/run

# capacity profile (search guard effectively removed)
SEARCH_RATE_LIMIT=100000 gunicorn ...   # then rerun locust --csv loadtest/results/cap

# staff account override
LOADTEST_STAFF_USERNAME=... LOADTEST_STAFF_PASSWORD=... locust ...
```

Raw data: `loadtest/results/run_stats.csv` and `loadtest/results/cap_stats.csv`.
