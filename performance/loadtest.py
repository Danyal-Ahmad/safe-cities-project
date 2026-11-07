from __future__ import annotations

import argparse
import http.client
import json
import random
import re
import statistics
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = Path(__file__).resolve().parent / 'reports'

CSRF_INPUT_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.latencies = defaultdict(list)
        self.counts = defaultdict(int)
        self.errors = defaultdict(int)
        self.throttled = defaultdict(int)
        self.statuses = defaultdict(lambda: defaultdict(int))
        self.total = 0
        self.stop_at = time.time()

    def record(self, scenario, status, elapsed_ms, is_error, is_throttled=False):
        with self.lock:
            self.total += 1
            self.counts[scenario] += 1
            self.statuses[scenario][status] += 1
            if is_throttled:
                self.throttled[scenario] += 1
                self.latencies[scenario].append(elapsed_ms)
            elif is_error:
                self.errors[scenario] += 1
            else:
                self.latencies[scenario].append(elapsed_ms)


class Session:
    def __init__(self, base_url):
        self.host = base_url.split('://', 1)[-1].split('/', 1)[0]
        self.conn = http.client.HTTPConnection(self.host, timeout=30)
        self.cookies = {}

    def request(self, method, path, body=None, headers=None, retry=True):
        hdrs = dict(headers or {})
        if self.cookies:
            hdrs['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())
        payload = None
        if body is not None:
            payload = body if isinstance(body, bytes) else body.encode()
            hdrs.setdefault('Content-Type', 'application/x-www-form-urlencoded')
        started = time.perf_counter()
        try:
            self.conn.request(method, path, body=payload, headers=hdrs)
            resp = self.conn.getresponse()
            data = resp.read()
            elapsed = (time.perf_counter() - started) * 1000
            for value in resp.getheaders():
                if value[0].lower() == 'set-cookie':
                    pair = value[1].split(';', 1)[0]
                    if '=' in pair:
                        k, _, v = pair.partition('=')
                        self.cookies[k.strip()] = v.strip()
            return resp.status, elapsed, data
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError):
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = http.client.HTTPConnection(self.host, timeout=30)
            if retry:
                return self.request(method, path, body, headers, retry=False)
            raise
        except Exception:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = http.client.HTTPConnection(self.host, timeout=30)
            raise

    def csrf_post(self, path, form_body):
        status, _, body = self.request('GET', path)
        if status != 200:
            return status, 0.0
        match = CSRF_INPUT_RE.search(body.decode('utf-8', 'ignore'))
        if not match:
            return status, 0.0
        token = match.group(1)
        sep = '&' if form_body else ''
        payload = f'{form_body}{sep}csrfmiddlewaretoken={token}'
        return self.request(
            'POST', path, payload,
            headers={'Referer': path},
        )

    def login(self, login_path, username, password):
        status, _, body = self.request('GET', login_path)
        if status != 200:
            return False
        match = CSRF_INPUT_RE.search(body.decode('utf-8', 'ignore'))
        if not match:
            return False
        form = f'username={username}&password={password}&csrfmiddlewaretoken={match.group(1)}'
        status, _, _ = self.request(
            'POST', login_path, form,
            headers={'Referer': login_path},
        )
        return status in (200, 302)


def build_scenarios(args):
    scenarios = [
        ('home', 35, 'GET', '/', None),
        ('login_page', 20, 'GET', '/auth/admin/login/', None),
        ('static_css', 15, 'GET', '/static/css/safe-city.css', None),
        ('search_form', 20, 'GET', '/?plate=LEA-1100&cnic=35202-1234567-1', None),
    ]
    if args.portal_path and args.email and args.password:
        scenarios.append(('portal_dash', 10, 'GET', args.portal_path, 'AUTH'))
    return scenarios


def worker(vu_id, args, scenarios, stats, ready_barrier):
    session = Session(args.base_url)
    authenticated = False
    if args.email and args.password:
        try:
            authenticated = session.login('/auth/admin/login/', args.email, args.password)
        except Exception:
            authenticated = False
    ready_barrier.wait()
    weights = [s[1] for s in scenarios]
    while time.time() < stats.stop_at:
        scenario = random.choices(scenarios, weights=weights, k=1)[0]
        name, _weight, method, path, body = scenario
        if body == 'AUTH' and not authenticated:
            name, method, path, body = 'home', 'GET', '/', None
        try:
            status, elapsed, _ = session.request(method, path, body)
            is_throttled = status == 429
            is_error = status >= 400 and not is_throttled
            stats.record(name, status, elapsed, is_error, is_throttled)
        except Exception as exc:
            stats.record(name, f'conn_err:{type(exc).__name__}', 0.0, True)
        time.sleep(args.think_time)


def run(args):
    scenarios = build_scenarios(args)
    duration = args.duration
    ramp = max(0.0, args.ramp)
    stats = Stats()
    print(f'target    : {args.base_url}')
    print(f'vus       : {args.vus} (ramp {ramp:.1f}s)')
    print(f'duration  : {duration}s')
    print(f'scenarios : ' + ', '.join(f'{s[0]}({s[1]}%)' for s in scenarios))
    print()

    threads = []
    barrier_count = 1 if ramp > 0 else args.vus
    barrier = threading.Barrier(barrier_count)
    stats.stop_at = time.time() + duration

    started = time.perf_counter()
    if ramp > 0:
        for i in range(args.vus):
            t = threading.Thread(target=worker, args=(i, args, scenarios, stats, barrier), daemon=True)
            t.start()
            threads.append(t)
            time.sleep(ramp / args.vus)
            if time.time() >= stats.stop_at:
                break
    else:
        for i in range(args.vus):
            t = threading.Thread(target=worker, args=(i, args, scenarios, stats, barrier), daemon=True)
            t.start()
            threads.append(t)

    while time.perf_counter() - started < duration:
        time.sleep(5)
        elapsed = time.perf_counter() - started
        print(f'  [{elapsed:6.1f}s] requests={stats.total} errors={sum(stats.errors.values())}')

    for t in threads:
        t.join(timeout=15)

    wall = time.perf_counter() - started
    return stats, wall


def report(args, stats, wall):
    lines = []
    lines.append('# Load Test Report')
    lines.append('')
    lines.append(f'- generated: {datetime.now(timezone.utc).isoformat()}')
    lines.append(f'- target: {args.base_url}')
    lines.append('- note: load generator and server share the same host CPUs; dedicated load infrastructure will show lower server latencies')
    lines.append(f'- virtual users: {args.vus}, duration: {args.duration}s, ramp: {args.ramp}s, think time: {args.think_time}s')
    lines.append(f'- total requests: {stats.total}, wall time: {wall:.1f}s')
    lines.append(f'- aggregate throughput: {stats.total / wall:.1f} req/s')
    total_errors = sum(stats.errors.values())
    total_throttled = sum(stats.throttled.values())
    lines.append(f'- errors: {total_errors} ({(total_errors / max(1, stats.total)) * 100:.2f}%), throttled (429): {total_throttled}')
    lines.append('')
    lines.append('| scenario | requests | rps | p50 ms | p95 ms | p99 ms | max ms | errors | status distribution |')
    lines.append('|---|---|---|---|---|---|---|---|---|')
    all_latencies = []
    for name in stats.counts:
        lat = stats.latencies.get(name, [])
        all_latencies.extend(lat)
        statuses = ', '.join(f'{k}:{v}' for k, v in sorted(stats.statuses[name].items(), key=lambda kv: -kv[1]))
        lines.append(
            f'| {name} | {stats.counts[name]} | {stats.counts[name] / wall:.1f} '
            f'| {percentile(lat, 50):.0f} | {percentile(lat, 95):.0f} | {percentile(lat, 99):.0f} '
            f'| {max(lat) if lat else 0:.0f} | {stats.errors[name]} | {statuses} |'
        )
    lines.append('')
    lines.append(
        f'**Aggregate latency:** p50 {percentile(all_latencies, 50):.0f} ms, '
        f'p95 {percentile(all_latencies, 95):.0f} ms, p99 {percentile(all_latencies, 99):.0f} ms'
    )
    verdict = 'PASS' if total_errors == 0 and percentile(all_latencies, 95) < 1000 else 'REVIEW'
    lines.append('')
    lines.append(f'**Verdict: {verdict}** (PASS requires 0 errors and p95 < 1000ms; 429 throttling is the rate limiter working as designed)')
    text = '\n'.join(lines)
    print()
    print(text)
    return text


def main():
    parser = argparse.ArgumentParser(description='Safe City high-traffic load test')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--vus', type=int, default=50)
    parser.add_argument('--duration', type=int, default=60)
    parser.add_argument('--ramp', type=float, default=10.0)
    parser.add_argument('--think-time', type=float, default=0.05)
    parser.add_argument('--email', default='')
    parser.add_argument('--password', default='')
    parser.add_argument('--portal-path', default='')
    parser.add_argument('--save', action='store_true', default=True)
    args = parser.parse_args()

    stats, wall = run(args)
    text = report(args, stats, wall)

    if args.save:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        (REPORT_DIR / f'loadtest_{stamp}.md').write_text(text + '\n', encoding='utf-8')
        payload = {
            'generated': datetime.now(timezone.utc).isoformat(),
            'base_url': args.base_url,
            'vus': args.vus,
            'duration': args.duration,
            'total': stats.total,
            'errors': sum(stats.errors.values()),
            'rps': round(stats.total / wall, 2),
            'latency_ms': {
                name: {
                    'count': stats.counts[name],
                    'p50': round(percentile(stats.latencies.get(name, []), 50), 1),
                    'p95': round(percentile(stats.latencies.get(name, []), 95), 1),
                    'p99': round(percentile(stats.latencies.get(name, []), 99), 1),
                    'errors': stats.errors[name],
                }
                for name in stats.counts
            },
        }
        (REPORT_DIR / f'loadtest_{stamp}.json').write_text(
            json.dumps(payload, indent=2), encoding='utf-8')
        print(f'\nreport saved to performance/reports/loadtest_{stamp}.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
