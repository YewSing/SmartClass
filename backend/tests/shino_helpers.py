"""Test helpers for Shino's modules (M2, M5, M6, M7) — S03.

Fixtures (made available to every test through `tests/conftest.py`):

- `shino_class` — course SH101 with one teaching lecturer, four enrolled students, a student
  who is not enrolled, a second lecturer who teaches another course, and an *open*
  `AttendanceSession` started through M3's own service (`session_schedule.start_now`), never
  by raw SQL. Returns a `ShinoClass` with plain ids and `client(user_id, role)`.
- `fake_expo_push` — a respx fake of the Expo Push API (`EXPO_PUSH_URL`): records every
  message, answers `DeviceNotRegistered` for chosen tokens, can simulate a network failure.
  Any other outgoing HTTP call in the test fails (respx blocks unmatched requests).
- `fake_smtp` — replaces `smtplib.SMTP` / `smtplib.SMTP_SSL` with an in-memory sink that keeps
  each sent message; can fail the next N sends. Passwords are never kept.
- `shino_llm` — record/replay for Shino's LLM prompts in `tests/fixtures/llm/m6/<name>.json`.
  Normal tests replay the recording (no network). Live tests (`@pytest.mark.live`) call the real
  LLM; with `--record-llm` their responses are saved, but only when the test passed.
"""
from __future__ import annotations

import hashlib
import json
import smtplib
import uuid
import warnings
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path

import httpx
import pytest
import respx

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.user import Lecturer, Student, User
from app.services.kb import llm as kb_llm

M6_LLM_DIR = Path(__file__).resolve().parent / "fixtures" / "llm" / "m6"
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
SHINO_PASSWORD = "Shino@1234"


# ── a class with an open session ────────────────────────────────────────────────

@dataclass
class ShinoClass:
    course_id: int
    occurrence_id: int
    session_id: int                      # the open AttendanceSession
    lecturer_user_id: int
    lecturer_id: int
    student_user_ids: list[int]          # 4 enrolled students (users.id)
    student_ids: list[int]               # their students.id, same order
    outsider_user_id: int                # a student not enrolled in SH101
    outsider_student_id: int
    other_lecturer_user_id: int          # teaches SH202, not SH101
    other_lecturer_id: int
    other_occurrence_id: int

    @staticmethod
    def token(user_id: int, role: str) -> str:
        return create_access_token(user_id, role)

    @staticmethod
    def client(user_id: int | None = None, role: str | None = None) -> httpx.AsyncClient:
        """An in-process API client, signed in as (user_id, role) when given. Use `async with`."""
        headers = {"Authorization": f"Bearer {create_access_token(user_id, role)}"} if user_id else {}
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                 headers=headers)


async def build_shino_class(n_students: int = 4, open_session: bool = True) -> ShinoClass:
    """Create the SH101 class (see module docstring). Emails/codes don't clash with conftest's
    `users`/`classroom` fixtures, so a test may use both."""
    from app.services import session_schedule

    async with AsyncSessionLocal() as db:
        pw = hash_password(SHINO_PASSWORD)

        def user(email: str, role: str, name: str) -> User:
            return User(email=email, password_hash=pw, role=role, name=name, status="active")

        lec_u = user("shino.lecturer@um.edu.my", "lecturer", "Shino Lecturer")
        other_lec_u = user("shino.other@um.edu.my", "lecturer", "Other Shino Lecturer")
        stu_us = [user(f"shino.student{i}@siswa.um.edu.my", "student", f"Shino Student {i}")
                  for i in range(1, n_students + 1)]
        out_u = user("shino.outsider@siswa.um.edu.my", "student", "Outsider Student")
        db.add_all([lec_u, other_lec_u, *stu_us, out_u])
        await db.flush()

        lec = Lecturer(user_id=lec_u.id, staff_id="SH-STAFF-1", dept="Software Engineering")
        other_lec = Lecturer(user_id=other_lec_u.id, staff_id="SH-STAFF-2", dept="Computer Science")
        students = [Student(user_id=u.id, matric_no=f"SH{i:06d}", programme="Software Engineering")
                    for i, u in enumerate(stu_us, start=1)]
        outsider = Student(user_id=out_u.id, matric_no="SH999999", programme="Computer Science")
        db.add_all([lec, other_lec, *students, outsider])
        await db.flush()

        course = Course(code="SH101", name="Shino Test Course")
        other_course = Course(code="SH202", name="Shino Other Course")
        db.add_all([course, other_course])
        await db.flush()
        occ = ClassOccurrence(course_id=course.id, type="LECTURE", day_of_week="Mon",
                              start_time="08:00", end_time="10:00", room="SH-R1", lecturer_id=lec.id)
        other_occ = ClassOccurrence(course_id=other_course.id, type="LECTURE", day_of_week="Tue",
                                    start_time="10:00", end_time="12:00", room="SH-R2",
                                    lecturer_id=other_lec.id)
        db.add_all([occ, other_occ])
        await db.flush()
        db.add_all([Enrollment(student_id=s.id, occurrence_id=occ.id) for s in students])
        await db.flush()

        session_id = 0
        if open_session:
            # M3's own "Start now" (FR-316): the same row, status and audit a real class gets.
            session = await session_schedule.start_now(db, occ, lec, session_schedule.clock(),
                                                       duration_minutes=120)
            session_id = session.id
        await db.commit()

        return ShinoClass(
            course_id=course.id, occurrence_id=occ.id, session_id=session_id,
            lecturer_user_id=lec_u.id, lecturer_id=lec.id,
            student_user_ids=[u.id for u in stu_us], student_ids=[s.id for s in students],
            outsider_user_id=out_u.id, outsider_student_id=outsider.id,
            other_lecturer_user_id=other_lec_u.id, other_lecturer_id=other_lec.id,
            other_occurrence_id=other_occ.id,
        )


@pytest.fixture
async def shino_class() -> ShinoClass:
    return await build_shino_class()


# ── fake Expo Push API ──────────────────────────────────────────────────────────

@dataclass
class FakeExpoPush:
    """Speaks the Expo push protocol: POST a message object or a list of them; the reply holds one
    ticket per message (`{"status":"ok","id":...}` or an error ticket with `details.error`)."""
    messages: list[dict] = field(default_factory=list)       # every message received, flattened
    batches: list[list[dict]] = field(default_factory=list)  # one entry per HTTP request
    requests: list[httpx.Request] = field(default_factory=list)  # the raw requests (headers)
    unregistered: set[str] = field(default_factory=set)      # tokens answered DeviceNotRegistered
    fail_network: bool = False                               # raise httpx.ConnectError instead
    status_code: int = 200                                   # e.g. 500 to simulate a server error

    @property
    def tokens(self) -> list[str]:
        return [m.get("to") for m in self.messages]

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_network:
            raise httpx.ConnectError("fake Expo push: network down", request=request)
        body = json.loads(request.content or b"null")
        batch = body if isinstance(body, list) else [body]
        self.batches.append(batch)
        self.messages.extend(batch)
        if self.status_code != 200:
            return httpx.Response(self.status_code, json={"errors": [{"code": "INTERNAL_SERVER_ERROR"}]})
        tickets = []
        for msg in batch:
            if msg.get("to") in self.unregistered:
                tickets.append({"status": "error",
                                "message": f"\"{msg.get('to')}\" is not a registered push notification recipient",
                                "details": {"error": "DeviceNotRegistered"}})
            else:
                tickets.append({"status": "ok", "id": str(uuid.uuid4())})
        return httpx.Response(200, json={"data": tickets})


@pytest.fixture(autouse=True)
async def _drain_push(_db_isolation):
    """Let background Expo pushes (S13) and emails (S14) finish before `_db_isolation` truncates
    the tables."""
    yield
    from app.services.notifications import announcements, mailer, push

    await announcements.drain()   # S17 Moodle posts (they may notify nothing, but touch the DB)
    await push.drain()
    await mailer.drain()


@pytest.fixture
def fake_expo_push():
    fake = FakeExpoPush()
    with respx.mock(assert_all_called=False) as router:
        router.post(EXPO_PUSH_URL).mock(side_effect=fake.handle)
        yield fake


# ── fake SMTP sink ──────────────────────────────────────────────────────────────

@dataclass
class SentMail:
    host: str
    port: int
    sender: str
    recipients: list[str]
    message: EmailMessage | None
    raw: str
    used_tls: bool
    username: str | None

    @property
    def subject(self) -> str | None:
        return self.message["Subject"] if self.message is not None else None


@dataclass
class FakeSMTPSink:
    sent: list[SentMail] = field(default_factory=list)
    fail_next: int = 0               # the next N sends raise SMTPServerDisconnected
    attempts: int = 0                # every send attempt, failed or not

    def _maybe_fail(self) -> None:
        self.attempts += 1
        if self.fail_next > 0:
            self.fail_next -= 1
            raise smtplib.SMTPServerDisconnected("fake SMTP: connection lost")


def _fake_smtp_class(sink: FakeSMTPSink, ssl: bool):
    class FakeSMTP:
        def __init__(self, host: str = "", port: int = 0, *args, **kwargs):
            self.host, self.port = host, port
            self.tls = ssl
            self.username: str | None = None

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.quit()
            return False

        def connect(self, host: str = "", port: int = 0, *args, **kwargs):
            self.host, self.port = host or self.host, port or self.port
            return (220, b"fake")

        def ehlo(self, *args, **kwargs):
            return (250, b"fake")

        helo = ehlo

        def starttls(self, *args, **kwargs):
            self.tls = True
            return (220, b"fake")

        def login(self, user: str, password: str, *args, **kwargs):
            self.username = user          # the password is deliberately not kept
            return (235, b"fake")

        def send_message(self, msg, from_addr=None, to_addrs=None, *args, **kwargs):
            sink._maybe_fail()
            sender = from_addr or msg["From"]
            rcpts = to_addrs or [a.strip() for h in ("To", "Cc", "Bcc") if msg[h]
                                 for a in str(msg[h]).split(",")]
            if isinstance(rcpts, str):
                rcpts = [rcpts]
            sink.sent.append(SentMail(self.host, self.port, sender, list(rcpts), msg, msg.as_string(),
                                      self.tls, self.username))
            return {}

        def sendmail(self, from_addr, to_addrs, msg, *args, **kwargs):
            sink._maybe_fail()
            if isinstance(to_addrs, str):
                to_addrs = [to_addrs]
            raw = msg.decode() if isinstance(msg, bytes) else msg
            from email import message_from_string, policy
            parsed = message_from_string(raw, policy=policy.default)
            sink.sent.append(SentMail(self.host, self.port, from_addr, list(to_addrs), parsed, raw,
                                      self.tls, self.username))
            return {}

        def quit(self):
            return (221, b"bye")

        close = quit

    return FakeSMTP


@pytest.fixture(autouse=True)
def _no_real_smtp(monkeypatch):
    """Email (S14) stays off in tests even if a dev `.env` sets SMTP_HOST; tests that need it turn
    it on themselves together with `fake_smtp`."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "SMTP_HOST", "")


@pytest.fixture
def fake_smtp(monkeypatch):
    sink = FakeSMTPSink()
    monkeypatch.setattr(smtplib, "SMTP", _fake_smtp_class(sink, ssl=False))
    monkeypatch.setattr(smtplib, "SMTP_SSL", _fake_smtp_class(sink, ssl=True))
    return sink


# ── LLM record / replay for Shino's prompts ─────────────────────────────────────

def prompt_sha(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class LLMReplay:
    """Swap `app.services.kb.llm.chat` (which `chat_json` also goes through) for a recording.

    Modes: `replay` — answers come from `<directory>/<name>.json` in call order (missing file or
    too many calls fails the test); `live` — the real LLM is called; `record` — live, and the
    answers are written to `<name>.json` by `finish(passed=True)`.
    """

    def __init__(self, monkeypatch, mode: str = "replay", directory: Path = M6_LLM_DIR):
        assert mode in ("replay", "live", "record"), mode
        self.monkeypatch, self.mode, self.directory = monkeypatch, mode, Path(directory)
        self.calls: list[list[dict]] = []          # messages of every call, for assertions
        self._name: str | None = None
        self._recorded: list[dict] = []

    def path(self, name: str) -> Path:
        return self.directory / f"{name}.json"

    def use(self, name: str) -> LLMReplay:
        """Route this test's LLM calls through the recording `name` (one per test)."""
        if self._name is not None:
            raise RuntimeError(f"shino_llm already uses {self._name!r}; one recording per test")
        self._name = name
        real_chat = kb_llm.chat

        if self.mode == "replay":
            path = self.path(name)
            if not path.exists():
                pytest.fail(f"No recorded LLM fixture {path.name} in {self.directory}. Record it with "
                            "`pytest -m live --record-llm` (needs LLM_API_KEY).", pytrace=False)
            recorded = json.loads(path.read_text(encoding="utf-8"))["calls"]
            queue = list(recorded)

            async def replay_chat(messages, max_tokens=None, temperature=0.2):
                self.calls.append(messages)
                if not queue:
                    raise AssertionError(f"LLM called {len(self.calls)} times but {name}.json recorded "
                                         f"only {len(recorded)} calls; re-record it")
                entry = queue.pop(0)
                if entry.get("prompt_sha256") and entry["prompt_sha256"] != prompt_sha(messages):
                    warnings.warn(f"{name}.json call {len(self.calls)}: the prompt changed since it was "
                                  "recorded; re-record with `pytest -m live --record-llm`", stacklevel=2)
                return entry["raw"]

            self.monkeypatch.setattr(kb_llm, "chat", replay_chat)
        else:
            async def live_chat(messages, max_tokens=None, temperature=0.2):
                self.calls.append(messages)
                raw = await real_chat(messages, max_tokens=max_tokens, temperature=temperature)
                self._recorded.append({"prompt_sha256": prompt_sha(messages), "raw": raw})
                return raw

            self.monkeypatch.setattr(kb_llm, "chat", live_chat)
        return self

    def finish(self, passed: bool) -> Path | None:
        """In record mode, save the answers of a passed test. Returns the written path."""
        if self.mode != "record" or not passed or self._name is None or not self._recorded:
            return None
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(self._name)
        path.write_text(json.dumps({"name": self._name, "calls": self._recorded}, indent=2,
                                   ensure_ascii=False) + "\n", encoding="utf-8")
        return path


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Remember whether the test body passed, so `shino_llm` records only passing live tests."""
    outcome = yield
    if call.when == "call":
        item._shino_call_passed = outcome.get_result().outcome == "passed"


@pytest.fixture
def shino_llm(request, monkeypatch):
    if request.node.get_closest_marker("live") is None:
        mode = "replay"
    else:
        mode = "record" if request.config.getoption("--record-llm") else "live"
    replay = LLMReplay(monkeypatch, mode)
    yield replay
    replay.finish(passed=getattr(request.node, "_shino_call_passed", False))
