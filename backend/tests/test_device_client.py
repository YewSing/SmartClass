"""T42: the camera device client (FR-401, FR-402, FR-409).

No network and no face images: camera frames are numpy noise, the detector and the API are fakes,
and the HTTP client uses `httpx.MockTransport`. Crops are never written anywhere (NFR-01).
"""
import httpx
import numpy as np
import pytest

from device_client.api import ApiError, ApiUnreachable, AuthError, DeviceApi
from device_client.cli import main
from device_client.config import Config, parse_args
from device_client.crops import crop_faces, expand_box
from device_client.detector import HaarDetector
from device_client.runner import CameraError, DeviceRunner


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


class FakeCamera:
    def __init__(self, frames, clock=None, frame_dt=0.1, opened=True):
        self.frames = list(frames)
        self.clock = clock
        self.frame_dt = frame_dt
        self.opened = opened
        self.reads = 0
        self.released = False

    def isOpened(self):
        return self.opened

    def read(self):
        self.reads += 1
        if self.clock is not None:
            self.clock.t += self.frame_dt
        if self.frames:
            return True, self.frames.pop(0)
        return False, None

    def release(self):
        self.released = True


class FakeDetector:
    def __init__(self, boxes):
        self.boxes = list(boxes)
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        return list(self.boxes)


class FakeApi:
    def __init__(self, sessions=None, faces_replies=None):
        self.sessions = list(sessions or [])
        self.faces_replies = list(faces_replies or [])
        self.heartbeats = 0
        self.sent = []
        self.events = []
        self.send_calls = 0
        self._session_calls = 0

    def heartbeat(self):
        self.heartbeats += 1
        self.events.append("heartbeat")

    def current_session(self):
        self.events.append("session")
        if self.sessions:
            value = self.sessions[min(self._session_calls, len(self.sessions) - 1)]
            self._session_calls += 1
        else:
            value = None
        if isinstance(value, Exception):
            raise value
        return value

    def send_faces(self, crops):
        self.events.append("faces")
        self.sent.append(list(crops))
        self.send_calls += 1
        if self.faces_replies:
            value = self.faces_replies.pop(0)
        else:
            value = {"session_id": 7, "results": []}
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        pass


def frame():
    return np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8)


def cfg(**kw):
    return Config(key="scd_test", **kw)


def api_with(handler) -> DeviceApi:
    return DeviceApi("http://test", "scd_test",
                     client=httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)))


# ── Crops ───────────────────────────────────────────────────────────────────

def test_expand_box_adds_margin_and_stays_inside_the_frame():
    assert expand_box((100, 100, 100, 100), 640, 480) == (70, 70, 160, 160)
    assert expand_box((0, 0, 50, 50), 640, 480) == (0, 0, 65, 65)
    assert expand_box((600, 440, 40, 40), 640, 480) == (588, 428, 52, 52)


def test_crop_faces_sends_jpegs_largest_face_first_and_caps_the_count():
    crops = crop_faces(frame(), [(10, 10, 40, 40), (200, 100, 100, 100)], max_crops=1)
    assert len(crops) == 1
    assert crops[0].startswith(b"\xff\xd8")
    decoded = cv2_imdecode(crops[0])
    assert decoded.shape == (160, 160, 3)


def test_crop_faces_shrinks_big_crops_to_max_side():
    crops = crop_faces(frame(), [(100, 50, 300, 300)])
    assert len(crops) == 1
    decoded = cv2_imdecode(crops[0])
    assert max(decoded.shape[:2]) == 320


def test_crop_faces_skips_empty_boxes():
    assert crop_faces(frame(), [(10, 10, 0, 40)]) == []


def cv2_imdecode(data: bytes):
    import cv2

    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


# ── HTTP client ─────────────────────────────────────────────────────────────

def test_api_current_session_reads_id_and_404_is_none():
    seen = []

    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(200, json={"session_id": 7, "occurrence_id": 3, "room": "DK1"})
        return httpx.Response(404, json={"detail": "No open session for this device's room"})

    api = api_with(handler)
    try:
        assert api.current_session() == 7
        assert seen[0].url.path == "/device/session"
        assert seen[0].headers["X-Device-Key"] == "scd_test"
        assert api.current_session() is None
    finally:
        api.close()


def test_api_send_faces_posts_each_crop_as_multipart():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["key"] = request.headers.get("X-Device-Key")
        seen["body"] = request.content
        return httpx.Response(200, json={"session_id": 7, "results": []})

    api = api_with(handler)
    crops = [b"\xff\xd8first", b"\xff\xd8second"]
    try:
        assert api.send_faces(crops) == {"session_id": 7, "results": []}
    finally:
        api.close()
    assert seen["path"] == "/device/faces"
    assert seen["method"] == "POST"
    assert seen["key"] == "scd_test"
    assert seen["body"].count(b'name="crops"') == 2
    assert crops[0] in seen["body"]
    assert crops[1] in seen["body"]


def test_api_send_faces_404_means_session_closed():
    api = api_with(lambda request: httpx.Response(404, json={"detail": "no session"}))
    try:
        assert api.send_faces([b"\xff\xd8x"]) is None
    finally:
        api.close()


def test_api_bad_key_raises_auth_error():
    for status_code in (401, 403):
        api = api_with(lambda request, code=status_code: httpx.Response(code, json={"detail": "Invalid device key"}))
        try:
            with pytest.raises(AuthError):
                api.current_session()
        finally:
            api.close()


def test_api_other_errors_and_unreachable():
    api = api_with(lambda request: httpx.Response(503, json={"detail": "model not loaded"}))
    try:
        with pytest.raises(ApiError) as caught:
            api.send_faces([b"\xff\xd8x"])
        assert not isinstance(caught.value, AuthError)
    finally:
        api.close()

    def down(request):
        raise httpx.ConnectError("down")

    api = api_with(down)
    try:
        with pytest.raises(ApiUnreachable):
            api.heartbeat()
    finally:
        api.close()


# ── One frame ───────────────────────────────────────────────────────────────

def test_process_frame_without_faces_sends_nothing():
    api = FakeApi()
    runner = DeviceRunner(api, lambda: FakeCamera([]), FakeDetector([]), cfg())
    assert runner.process_frame(frame()) == "no_face"
    assert api.sent == []


def test_process_frame_sends_one_crop_per_face():
    api = FakeApi()
    detector = FakeDetector([(10, 10, 60, 60), (200, 100, 80, 80)])
    runner = DeviceRunner(api, lambda: FakeCamera([]), detector, cfg())
    assert runner.process_frame(frame()) == "sent"
    assert len(api.sent[0]) == 2


# ── The loop ────────────────────────────────────────────────────────────────

def test_camera_opens_only_while_a_session_is_open():
    clock = FakeClock()
    reply = {"session_id": 7, "results": [
        {"index": 0, "outcome": "voting", "student_id": 1, "similarity": 0.8, "votes": 1}]}
    api = FakeApi(sessions=[None, None, 7], faces_replies=[reply, reply, None])
    logs = []
    cameras = []

    def open_camera():
        api.events.append("camera")
        camera = FakeCamera([frame()] * 5, clock, frame_dt=0.3)
        cameras.append(camera)
        return camera

    runner = DeviceRunner(api, open_camera, FakeDetector([(100, 100, 100, 100)]), cfg(fps=4.0, poll_seconds=5.0),
                          clock=clock, sleep=clock.sleep, log=logs.append)
    runner.run(max_sessions=1)

    assert api.events.count("session") >= 3
    third_session = [i for i, event in enumerate(api.events) if event == "session"][2]
    assert api.events.index("camera") > third_session
    assert len(api.sent) == 3
    assert all(len(crops) == 1 and crops[0].startswith(b"\xff\xd8") for crops in api.sent)
    assert cameras[0].released
    assert api.heartbeats >= 1
    assert api.events.index("heartbeat") < api.events.index("camera")
    assert not any("scd_test" in line for line in logs)


def test_frames_are_paced_to_the_fps():
    clock = FakeClock()
    camera = FakeCamera([frame()] * 20, clock, frame_dt=0.1)
    reply = {"session_id": 7, "results": []}
    api = FakeApi(sessions=[7], faces_replies=[reply, reply, None])
    detector = FakeDetector([(100, 100, 100, 100)])
    runner = DeviceRunner(api, lambda: camera, detector, cfg(fps=2.0, poll_seconds=100),
                          clock=clock, sleep=clock.sleep, log=lambda line: None)
    runner.capture(7)

    assert detector.calls == 3
    assert len(api.sent) == 3
    assert camera.reads == 11


def test_capture_ends_when_the_session_closes_without_faces():
    clock = FakeClock()
    camera = FakeCamera([frame()] * 50, clock, frame_dt=0.3)
    api = FakeApi(sessions=[7, None])
    runner = DeviceRunner(api, lambda: camera, FakeDetector([]), cfg(poll_seconds=1.0),
                          clock=clock, sleep=clock.sleep, log=lambda line: None)
    runner.capture(7)

    assert camera.released
    assert api.sent == []


def test_unreachable_server_while_sending_is_logged_and_retried():
    clock = FakeClock()
    camera = FakeCamera([frame()] * 5, clock, frame_dt=0.3)
    api = FakeApi(sessions=[7], faces_replies=[ApiUnreachable("down"), None])
    logs = []
    runner = DeviceRunner(api, lambda: camera, FakeDetector([(100, 100, 100, 100)]), cfg(),
                          clock=clock, sleep=clock.sleep, log=logs.append)
    runner.capture(7)

    assert api.send_calls == 2
    assert 1.0 in clock.sleeps
    assert any("unreachable" in line for line in logs)


def test_bad_key_stops_the_runner():
    api = FakeApi(sessions=[AuthError("401")])
    runner = DeviceRunner(api, lambda: FakeCamera([]), FakeDetector([]), cfg(),
                          clock=FakeClock(), sleep=lambda seconds: None, log=lambda line: None)
    with pytest.raises(AuthError):
        runner.run()


def test_camera_that_will_not_open_raises():
    cameras = []

    def open_camera():
        camera = FakeCamera([], opened=False)
        cameras.append(camera)
        return camera

    api = FakeApi(sessions=[7])
    runner = DeviceRunner(api, open_camera, FakeDetector([]), cfg(),
                          clock=FakeClock(), sleep=lambda seconds: None, log=lambda line: None)
    with pytest.raises(CameraError):
        runner.capture(7)
    assert cameras[0].released


def test_heartbeat_every_interval():
    clock = FakeClock()
    api = FakeApi()
    logs = []
    runner = DeviceRunner(api, lambda: FakeCamera([]), FakeDetector([]), cfg(heartbeat_seconds=20),
                          clock=clock, sleep=clock.sleep, log=logs.append)
    for t in (0, 5, 20, 39, 41):
        clock.t = t
        runner.tick_heartbeat()
    assert api.heartbeats == 3

    def down():
        raise ApiUnreachable("down")

    api.heartbeat = down
    clock.t = 61
    runner.tick_heartbeat()   # logged, not raised
    assert any("heartbeat failed" in line for line in logs)


# ── Config and entry point ──────────────────────────────────────────────────

def test_parse_args_reads_env_and_flags_override():
    config = parse_args(["--camera", "1"], env={
        "DEVICE_KEY": "scd_x", "SMARTCLASS_API_URL": "http://pi:8000/", "CAMERA_INDEX": "3"})
    assert config.key == "scd_x"
    assert config.api_url == "http://pi:8000"
    assert config.camera == 1

    config = parse_args([], env={"API_BASE_URL": "http://a:1"})
    assert config.api_url == "http://a:1"
    assert config.camera == 0
    assert config.key == ""


def test_cli_without_key_exits_2(monkeypatch, capsys):
    monkeypatch.delenv("DEVICE_KEY", raising=False)
    assert main([]) == 2
    assert "DEVICE_KEY" in capsys.readouterr().err


def test_haar_detector_loads_and_finds_nothing_in_noise():
    assert HaarDetector().detect(np.zeros((480, 640, 3), np.uint8)) == []
