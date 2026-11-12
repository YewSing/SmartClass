"""Configuration from argparse flags and environment variables (FR-409).

Flags override the environment. No `.env` file is read: the key comes from `DEVICE_KEY` or `--key`.
"""
import argparse
import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Config:
    api_url: str = "http://localhost:8000"
    key: str = ""
    camera: int = 0
    fps: float = 4.0                  # frames analysed per second
    poll_seconds: float = 5.0         # how often to look for / re-check the open session
    heartbeat_seconds: float = 20.0   # server counts a device online for 60 s
    margin: float = 0.3               # added on each side of a face box, as a fraction of its size
    max_crops: int = 10               # = server DEVICE_MAX_CROPS
    max_side: int = 320               # crops are shrunk so the longer side is at most this
    min_face: int = 60                # smallest face (px) the detector reports


def parse_args(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> Config:
    """Build a Config from CLI flags, falling back to env vars, then the defaults."""
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(
        prog="device_client",
        description="SmartClass camera device client: detect faces, send crops while a session is open.",
    )
    parser.add_argument("--api", default=(env.get("SMARTCLASS_API_URL") or env.get("API_BASE_URL")
                                          or "http://localhost:8000"),
                        help="server base URL (env SMARTCLASS_API_URL, then API_BASE_URL)")
    parser.add_argument("--key", default=env.get("DEVICE_KEY", ""),
                        help="this device's key (env DEVICE_KEY); never printed")
    parser.add_argument("--camera", type=int, default=int(env.get("CAMERA_INDEX") or "0"),
                        help="cv2.VideoCapture index; 0 is the laptop webcam (env CAMERA_INDEX)")
    parser.add_argument("--fps", type=float, default=Config.fps, help="frames analysed per second")
    parser.add_argument("--poll-seconds", type=float, default=Config.poll_seconds,
                        help="seconds between checks for the open session")
    parser.add_argument("--heartbeat-seconds", type=float, default=Config.heartbeat_seconds,
                        help="seconds between heartbeats")
    parser.add_argument("--min-face", type=int, default=Config.min_face,
                        help="smallest face (pixels) the detector reports")
    args = parser.parse_args(argv)
    return Config(
        api_url=args.api.rstrip("/"),
        key=args.key,
        camera=args.camera,
        fps=args.fps,
        poll_seconds=args.poll_seconds,
        heartbeat_seconds=args.heartbeat_seconds,
        min_face=args.min_face,
    )
