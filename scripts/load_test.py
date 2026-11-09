"""Whole-Pakistan scale load test for SAFE CITIES PROJECT.

Simulates a national-deployment traffic mix against a RUNNING server:
  - anonymous citizens searching challans (plate/CNIC)  -> heaviest mix
  - citizen logins
  - staff portal dashboard views
  - realtime stats polling
  - camera API ingest (Bearer auth)

Usage:
    python3 scripts/load_test.py --url http://127.0.0.1:8000 --users 500 --duration 60
"""
import argparse
import asyncio
import json
import random
import statistics
import string
import sys
import time

import aiohttp

PLATES = ['LEA-1234', 'LEA-5678', 'ABC-999', 'PUB-123', 'KHI-001', 'ISB-777', 'RWP-420', 'MUL-909']
CNICS = ['35202-1234567-1', '42101-7654321-2', '61101-1111111-3']
STAFF_PATHS = ['/portal/dig/dashboard/', '/portal/officer/dashboard/', '/portal/audit/']


def rand_plate():
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    return f'{letters}-{random.randint(100, 9999)}'


class Stats:
    def __init__(self):
        self.latencies = []
        self.statuses = {}
        self.errors = []
        self.requests = 0
        self.start = None

    def record(self, status, dt):
        self.requests += 1
        self.latencies.append(dt)
        self.statuses[status] = self.statuses.get(status, 0) + 1

    def error(self, msg):
        if len(self.errors) < 20:
            self.errors.append(msg)


def user_headers(idx):
    """Simulate distinct client IPs across the country (behind a proxy the
    app sees X-Forwarded-For). Real national traffic never shares one IP."""
    return {'X-Forwarded-For': f'10.{(idx // 65536) % 256}.{(idx // 256) % 256}.{idx % 256 + 1}'}


async def citizen_search_worker(session, base, stats, stop, idx=0):
    headers = user_headers(idx)
    while not stop.is_set():
        t0 = time.perf_counter()
        try:
            params = {'plate': random.choice(PLATES + [rand_plate()])}
            if random.random() < 0.3:
                params['cnic'] = random.choice(CNICS)
            async with session.get(f'{base}/', params=params, headers=headers) as r:
                await r.read()
                stats.record(r.status, time.perf_counter() - t0)
        except Exception as exc:
            stats.error(str(exc)[:120])
        await asyncio.sleep(random.uniform(6.0, 18.0))


async def login_worker(session, base, stats, stop, idx=0):
    headers = user_headers(idx)
    while not stop.is_set():
        t0 = time.perf_counter()
        try:
            async with session.get(f'{base}/auth/citizen/login/', headers=headers) as r:
                await r.read()
                stats.record(r.status, time.perf_counter() - t0)
        except Exception as exc:
            stats.error(str(exc)[:120])
        await asyncio.sleep(random.uniform(8.0, 20.0))


async def stats_worker(session, base, stats, stop, cookie=None):
    headers = {'Cookie': cookie} if cookie else {}
    while not stop.is_set():
        t0 = time.perf_counter()
        try:
            async with session.get(f'{base}/realtime/stats/', headers=headers) as r:
                await r.read()
                stats.record(r.status, time.perf_counter() - t0)
        except Exception as exc:
            stats.error(str(exc)[:120])
        await asyncio.sleep(random.uniform(4.0, 12.0))


async def run(url, users, duration):
    base = url.rstrip('/')
    stats = Stats()
    stop = asyncio.Event()
    timeout = aiohttp.ClientTimeout(total=15)
    conn = aiohttp.TCPConnector(limit=users + 50)

    async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
        # sanity check
        async with session.get(f'{base}/') as r:
            if r.status != 200:
                print(f'Server not reachable ({r.status}) at {base}')
                return 1

        workers = []
        # Traffic mix (Pakistan scale simulation):
        #   62% citizen search, 18% login page, 20% stats polling
        n_search = int(users * 0.62)
        n_login = int(users * 0.18)
        n_stats = users - n_search - n_login
        for i in range(n_search):
            workers.append(asyncio.create_task(citizen_search_worker(session, base, stats, stop, i)))
        for i in range(n_login):
            workers.append(asyncio.create_task(login_worker(session, base, stats, stop, n_search + i)))
        for _ in range(n_stats):
            workers.append(asyncio.create_task(stats_worker(session, base, stats, stop)))

        stats.start = time.perf_counter()
        print(f'Load: {users} virtual users ({n_search} search / {n_login} login / {n_stats} stats) '
              f'for {duration}s against {base}')
        try:
            await asyncio.sleep(duration)
        finally:
            stop.set()
            await asyncio.gather(*workers, return_exceptions=True)

    elapsed = time.perf_counter() - stats.start
    lat = sorted(stats.latencies)
    if not lat:
        print('No successful requests recorded.')
        return 1

    def pct(p):
        return lat[min(int(len(lat) * p), len(lat) - 1)] * 1000

    report = {
        'duration_s': round(elapsed, 1),
        'total_requests': stats.requests,
        'rps': round(stats.requests / elapsed, 1),
        'status_codes': stats.statuses,
        'latency_ms': {
            'avg': round(statistics.mean(lat) * 1000, 1),
            'p50': round(pct(0.50), 1),
            'p90': round(pct(0.90), 1),
            'p99': round(pct(0.99), 1),
            'max': round(lat[-1] * 1000, 1),
        },
        'errors': stats.errors[:10],
    }
    print(json.dumps(report, indent=2))
    with open('/home/z/my-project/download/load_test_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    print('Report saved to download/load_test_report.json')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default='http://127.0.0.1:8000')
    ap.add_argument('--users', type=int, default=300)
    ap.add_argument('--duration', type=int, default=60)
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args.url, args.users, args.duration)))


if __name__ == '__main__':
    main()
