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

| profile | throughput | p50 | p95 | p99 | errors | verdict |
|---|---|---|---|---|---|---|
| 30 VUs / 60s | 96.3 req/s | 187 ms | 510 ms | 715 ms | 0 | PASS |
| 100 VUs / 45s | ~75 req/s | 849 ms | 1853 ms | 3894 ms | 0 | saturation |

- Zero application errors at every tested level; 429 responses under aggressive
  same-IP search are the built-in rate limiter working as designed.
- The load generator shares CPUs with the server in this reference setup;
  dedicated load infrastructure will show lower server-side latency.
- Scaling out: gunicorn worker count is CPU-derived (`deploy/gunicorn.conf.py`);
  raise `GUNICORN_WORKERS`/`GUNICORN_THREADS` via `.env` on larger hosts and put
  PostgreSQL on dedicated hardware for production traffic.
