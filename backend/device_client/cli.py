"""`python -m device_client`: parse config, then run until Ctrl-C. Never prints the key."""
import signal
import sys

from device_client.api import AuthError, DeviceApi
from device_client.config import parse_args
from device_client.detector import HaarDetector
from device_client.runner import CameraError, DeviceRunner


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    if not config.key:
        print(
            "DEVICE_KEY is not set. An admin registers the device (or regenerates its key); "
            "for the seeded camera: python scripts/device_key.py CAM-TEST",
            file=sys.stderr,
        )
        return 2

    import cv2

    detector = HaarDetector(config.min_face)
    api = DeviceApi(config.api_url, config.key)
    runner = DeviceRunner(api, lambda: cv2.VideoCapture(config.camera), detector, config)
    signal.signal(signal.SIGINT, lambda *_: runner.stop())
    try:
        runner.run()
    except AuthError as exc:
        print(f"[device] the server refused this device key ({exc}). Ask an admin for a new key.",
              file=sys.stderr)
        return 1
    except CameraError as exc:
        print(f"[device] {exc}", file=sys.stderr)
        return 1
    finally:
        api.close()
    print("[device] stopped")
    return 0
