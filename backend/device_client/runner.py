"""The device loop: heartbeat always, open the camera only while a session is open (FR-401).

The camera is opened when `GET /device/session` reports an open session for this device's room and
released as soon as that session closes (or the server answers 404 for it), then the client goes
back to polling. A 401/403 stops everything: a revoked key will never start working.
"""
import time
from typing import Any, Callable

from device_client.api import ApiError, ApiUnreachable, AuthError
from device_client.config import Config
from device_client.crops import crop_faces


class CameraError(Exception):
    """The camera cannot be opened, or stopped giving frames."""


# Clocks are floats: a frame that is due exactly one period later must not be dropped because
# the measured gap came out a few ULPs short (0.9999999999999999 vs 1.0).
_PACING_EPSILON = 1e-6


class DeviceRunner:
    def __init__(self, api: Any, open_camera: Callable[[], Any], detector: Any, config: Config,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 log: Callable[[str], None] = print) -> None:
        self.api = api
        self._open_camera = open_camera
        self._detector = detector
        self.config = config
        self._clock = clock
        self._sleep = sleep
        self._log = log
        self.running = True
        self._last_heartbeat: float | None = None

    def stop(self) -> None:
        self.running = False

    def tick_heartbeat(self) -> None:
        """Send a heartbeat when one is due. `_last_heartbeat` is set first, so a down server
        is not hammered on every loop iteration."""
        now = self._clock()
        if self._last_heartbeat is not None and now - self._last_heartbeat < self.config.heartbeat_seconds:
            return
        self._last_heartbeat = now
        try:
            self.api.heartbeat()
        except AuthError:
            raise
        except ApiError as exc:
            self._log(f"[device] heartbeat failed: {exc}")

    def wait_for_session(self) -> int | None:
        """Poll until a session is open; None when the runner was stopped."""
        self._log("[device] waiting for an open session...")
        while self.running:
            self.tick_heartbeat()
            sid = None
            try:
                sid = self.api.current_session()
            except ApiUnreachable as exc:
                self._log(f"[device] server unreachable: {exc}")
            except AuthError:
                raise
            except ApiError as exc:
                self._log(f"[device] cannot check the session: {exc}")
            if sid is not None:
                self._log(f"[device] session {sid} is open")
                return sid
            self._sleep(self.config.poll_seconds)
        return None

    def process_frame(self, frame: Any) -> str:
        """Detect, crop and send one frame. Returns "no_face", "sent" or "session_closed"."""
        boxes = self._detector.detect(frame)
        if not boxes:
            return "no_face"
        crops = crop_faces(frame, boxes, self.config.margin, self.config.max_crops, self.config.max_side)
        if not crops:
            return "no_face"
        result = self.api.send_faces(crops)
        if result is None:
            return "session_closed"
        for r in result.get("results", []):
            self._log(
                f"[device] face {r['index']}: {r['outcome']} student={r.get('student_id')} "
                f"similarity={r.get('similarity')} votes={r.get('votes')}"
            )
        return "sent"

    def capture(self, session_id: int) -> None:
        """Stream frames of one session until it closes; the camera is off before and after."""
        camera = self._open_camera()
        if not camera.isOpened():
            camera.release()
            raise CameraError(f"Cannot open camera {self.config.camera}")
        last_check = self._clock()
        last_frame: float | None = None
        failures = 0
        try:
            while self.running:
                self.tick_heartbeat()
                now = self._clock()
                if now - last_check >= self.config.poll_seconds:
                    last_check = now
                    try:
                        sid = self.api.current_session()
                    except ApiUnreachable:
                        sid = session_id   # unreachable is not a closed session: keep going
                    if sid != session_id:
                        self._log(f"[device] session {session_id} closed")
                        break
                ok, frame = camera.read()
                if not ok:
                    failures += 1
                    if failures >= 50:
                        raise CameraError("Camera stopped giving frames")
                    self._sleep(0.1)
                    continue
                failures = 0
                if last_frame is not None and now - last_frame < 1 / self.config.fps - _PACING_EPSILON:
                    continue   # read but skip analysing, so the camera buffer stays fresh
                last_frame = now
                try:
                    outcome = self.process_frame(frame)
                except AuthError:
                    raise
                except ApiUnreachable as exc:
                    self._log(f"[device] server unreachable: {exc}")
                    self._sleep(1.0)
                    continue
                except ApiError as exc:
                    self._log(f"[device] frame not sent: {exc}")
                    continue
                if outcome == "session_closed":
                    self._log(f"[device] session {session_id} closed")
                    break
        finally:
            camera.release()

    def run(self, max_sessions: int | None = None) -> None:
        """Wait for a session, capture it, and repeat until stopped (`max_sessions` is for tests)."""
        count = 0
        while self.running:
            sid = self.wait_for_session()
            if sid is None:
                break
            self.capture(sid)
            count += 1
            if max_sessions is not None and count >= max_sessions:
                break
