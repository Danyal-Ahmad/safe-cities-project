import argparse
import logging
import os
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wrongway_system.settings')

try:
    import django
    django.setup()
    from cameras.models import Camera
except Exception as e:
    print(f"ERROR: Could not initialize Django: {e}", file=sys.stderr)
    sys.exit(1)

try:
    import cv2
    import requests
except ImportError:
    print("ERROR: Install required packages: pip install opencv-python-headless requests", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s [%(threadName)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('wrongway.camera_worker')


class CameraStreamWorker:

    def __init__(self, camera, server_url):
        self.camera = camera
        self.server_url = server_url.rstrip('/')
        self.ingest_url = f"{self.server_url}/api/v1/ingest/"
        self.heartbeat_url = f"{self.server_url}/api/v1/heartbeat/"
        self.api_key = str(camera.api_key)
        self.interval = max(2, camera.capture_interval)
        self.running = False
        self._cap = None
        self._last_heartbeat = 0

    def _open_stream(self):
        if self.camera.rtsp_url:
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
            cap = cv2.VideoCapture(self.camera.rtsp_url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                log.error("[%s] Could not open RTSP stream: %s", self.camera.camera_id, self.camera.rtsp_url)
                return None
            return cap
        return None

    def _capture_frame_rtsp(self):
        if self._cap is None:
            self._cap = self._open_stream()
            if self._cap is None:
                return None
        for _ in range(3):
            self._cap.grab()
        ret, frame = self._cap.read()
        if not ret or frame is None:
            log.warning("[%s] Frame grab failed - reopening stream", self.camera.camera_id)
            try:
                if self._cap: self._cap.release()
            except Exception: pass
            self._cap = None
            return None
        return frame

    def _capture_frame_http(self):
        if not self.camera.http_snapshot_url:
            return None
        try:
            resp = requests.get(self.camera.http_snapshot_url, timeout=10, auth=None)
            if resp.status_code != 200:
                return None
            import numpy as np
            arr = np.frombuffer(resp.content, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            log.warning("[%s] HTTP snapshot failed: %s", self.camera.camera_id, e)
            return None

    def _capture_frame(self):
        if self.camera.rtsp_url:
            frame = self._capture_frame_rtsp()
            if frame is not None:
                return frame
        if self.camera.http_snapshot_url:
            return self._capture_frame_http()
        return None

    def _post_frame(self, frame):
        success, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not success:
            return False
        files = {'image': (f'{self.camera.camera_id}.jpg', buf.tobytes(), 'image/jpeg')}
        data = {'moving_direction': self.camera.legal_direction}
        headers = {'Authorization': f'Bearer {self.api_key}'}
        try:
            resp = requests.post(self.ingest_url, files=files, data=data, headers=headers, timeout=20)
            if resp.status_code == 201:
                try:
                    j = resp.json()
                    log.info("[%s] Frame posted - detection #%s (side=%s, conf=%.3f, violation=%s)",
                             self.camera.camera_id, j.get('detection_id'),
                             j.get('side'), j.get('confidence') or 0, j.get('detected_violation'))
                except Exception:
                    log.info("[%s] Frame posted (201)", self.camera.camera_id)
                return True
            else:
                log.warning("[%s] Ingest failed: HTTP %s - %s",
                            self.camera.camera_id, resp.status_code, resp.text[:200])
                return False
        except Exception as e:
            log.warning("[%s] Ingest request failed: %s", self.camera.camera_id, e)
            return False

    def _send_heartbeat(self):
        headers = {'Authorization': f'Bearer {self.api_key}'}
        try:
            resp = requests.post(self.heartbeat_url, headers=headers, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            log.warning("[%s] Heartbeat failed: %s", self.camera.camera_id, e)
            return False

    def run_once(self):
        frame = self._capture_frame()
        if frame is None:
            log.warning("[%s] No frame captured", self.camera.camera_id)
            return False
        return self._post_frame(frame)

    def run_forever(self):
        self.running = True
        log.info("[%s] Worker started - interval=%ds", self.camera.camera_id, self.interval)
        while self.running:
            try:
                self.run_once()
            except Exception as e:
                log.exception("[%s] Worker iteration failed: %s", self.camera.camera_id, e)
            now = time.time()
            if now - self._last_heartbeat >= 60:
                self._send_heartbeat()
                self._last_heartbeat = now
            time.sleep(self.interval)

    def stop(self):
        self.running = False
        if self._cap:
            try: self._cap.release()
            except Exception: pass


def main():
    parser = argparse.ArgumentParser(description='Safe City Camera Worker - real RTSP/HTTP camera integration')
    parser.add_argument('--server', default='http://127.0.0.1:8000',
                        help='Django server URL (default: http://127.0.0.1:8000)')
    parser.add_argument('--once', action='store_true',
                        help='Capture a single frame per camera and exit (no looping)')
    parser.add_argument('--camera-id', default=None,
                        help='Process only this camera_id (default: all active+streaming cameras)')
    args = parser.parse_args()

    qs = Camera.objects.filter(is_active=True, is_streaming=True, is_enrolled=True)
    if args.camera_id:
        qs = qs.filter(camera_id=args.camera_id)

    if not qs.exists():
        log.error("No active+streaming+enrolled cameras found. Register cameras at /dig/cameras/add/ first.")
        sys.exit(1)

    log.info("Found %d camera(s) to process:", qs.count())
    for c in qs:
        rtsp = c.rtsp_url or '(no RTSP)'
        log.info("  - %s at %s (interval=%ds, source=%s)", c.camera_id, c.location, c.capture_interval, rtsp)

    if args.once:
        log.info("Single-capture mode")
        for c in qs:
            worker = CameraStreamWorker(c, args.server)
            worker.run_once()
        return

    threads = []
    workers = []
    for c in qs:
        worker = CameraStreamWorker(c, args.server)
        workers.append(worker)
        t = threading.Thread(target=worker.run_forever, name=f'cam-{c.camera_id}', daemon=True)
        t.start()
        threads.append(t)

    log.info("All %d camera worker(s) started. Press Ctrl+C to stop.", len(threads))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping workers...")
        for w in workers: w.stop()
        for t in threads: t.join(timeout=5)
        log.info("All workers stopped.")


if __name__ == '__main__':
    main()

