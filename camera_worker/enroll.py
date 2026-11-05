import argparse
import sys
import requests


def main():
    parser = argparse.ArgumentParser(description='Safe City Camera Enrollment')
    parser.add_argument('--server', default='http://127.0.0.1:8000', help='Django server URL')
    parser.add_argument('--token', required=True, help='Enrollment token (UUID)')
    parser.add_argument('--rtsp-url', default=None, help='RTSP URL to register with this camera')
    parser.add_argument('--http-url', default=None, help='HTTP snapshot URL alternative')
    args = parser.parse_args()

    data = {'enrollment_token': args.token}
    if args.rtsp_url:
        data['rtsp_url'] = args.rtsp_url
    if args.http_url:
        data['http_snapshot_url'] = args.http_url

    print(f"Enrolling camera with token {args.token}...")
    try:
        resp = requests.post(f"{args.server.rstrip('/')}/api/v1/enroll/", data=data, timeout=15)
    except Exception as e:
        print(f"ERROR: Could not reach server: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code == 200:
        j = resp.json()
        print("\n✓ Enrollment successful!")
        print(f"  Camera ID: {j['camera_id']}")
        print(f"  API Key:   {j['api_key']}")
        print("\nSave this API key. The camera_worker.py will use it automatically")
        print("once it picks up this camera from the database (which now has the RTSP URL).")
        print("\nNext step: run the camera worker:")
        print(f"  python camera_worker/worker.py --server {args.server}")
    elif resp.status_code == 403:
        print("ERROR: Invalid or already-used enrollment token.", file=sys.stderr)
        sys.exit(1)
    elif resp.status_code == 400:
        print(f"ERROR: Bad request - {resp.text}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"ERROR: Server returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

