# Performance & Load Testing

High-traffic load test suite for the Safe City e-Challan platform. The runner is
dependency-free (Python 3 standard library only) and drives real HTTP traffic
against a running server.

## Run

Start the production server first:

```bash
python launcher.py run          # gunicorn when DEBUG=False, else dev server
```

Then drive load:

```bash
python performance/loadtest.py --vus 30 --duration 60 --ramp 10

# include an authenticated portal scenario (login handled automatically):
python performance/loadtest.py --vus 30 --duration 60 \
  --email itsupport@safecity.fyp --password '<password>' \
  --portal-path /portal/it/
```

Options: `--base-url`, `--vus` (concurrent virtual users), `--duration` (s),
`--ramp` (s), `--think-time` (s between requests per VU).

Scenarios and weights: public home 35%, admin login page 20%, public challan
search 20%, static asset (WhiteNoise) 15%, authenticated portal dashboard 10%
(when credentials are supplied). Search uses the real GET form flow.

Reports (markdown + JSON) are written to `performance/reports/`.

## Results (reference hardware: 2 vCPU, gunicorn 4 x gthread, PostgreSQL local)

| profile | server | throughput | p50 | p95 | p99 | errors | verdict |
|---|---|---|---|---|---|---|---|
| 30 VUs / 45s | dev (runserver) | 212.6 req/s | 57 ms | 183 ms | 233 ms | 0 | PASS |
| 100 VUs / 40s | dev (runserver) | 237.6 req/s | 207 ms | 976 ms | 1274 ms | 1 | saturation |
| 100 VUs / 45s | gunicorn (production) | ~230 req/s | 246 ms | 498 ms | 2306 ms | 0 | PASS |
| 40 VUs / 40s + auth | gunicorn (production) | ~81 req/s | 255 ms | 646 ms | 879 ms | 0 | PASS |

- Zero application errors on the production server at every tested level; 429
  responses under aggressive same-IP search are the built-in rate limiter
  working as designed.
- The load generator shares CPUs with the server in this reference setup;
  dedicated load infrastructure will show lower server-side latency.
- The dev server (`runserver`) spawns one thread per request with no bound, so
  sustained 100+ concurrency can exhaust PostgreSQL `max_connections` (the one
  observed dev-server error was exactly that). Production gunicorn bounds
  concurrency to `workers x threads` (default 4 x 4 = 16 connections).
- Scaling out: gunicorn worker count is CPU-derived (`deploy/gunicorn.conf.py`);
  raise `GUNICORN_WORKERS`/`GUNICORN_THREADS` via `.env` on larger hosts, put
  PostgreSQL on dedicated hardware for production traffic, and keep
  `GUNICORN_WORKERS x GUNICORN_THREADS + headroom` below PostgreSQL
  `max_connections` (or front PostgreSQL with PgBouncer).
