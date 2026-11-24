"""S35: live interaction updates over `WS /interaction/{attendance_session_id}/ws` (FR-516).

The websocket is driven in-process through a small ASGI client (as in test_notifications_live),
so it runs on the test's own event loop next to asyncpg. The class is started and ended through
M3's own services (shino_helpers / session_service), never by M5.
"""
import asyncio
import json
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from jose import jwt
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal, discard_after_commit, run_after_commit
from app.core.security import ALGORITHM, create_access_token, create_refresh_token
from app.core.timezone import now_myt
from app.main import app
from app.models.class_ import ClassOccurrence
from app.models.interaction import Question
from app.models.user import Lecturer, User
from app.services import session_service
from app.services.interaction import live, sessions

pytestmark = pytest.mark.db

QUIET = 0.3     # how long "nothing (more) arrives" is waited for


class Closed(Exception):
    def __init__(self, code: int):
        super().__init__(code)
        self.code = code


class WSClient:
    """A minimal ASGI websocket client for one connection to the app."""

    def __init__(self, attendance_session_id: int, token: str | None):
        self.path = f"/interaction/{attendance_session_id}/ws"
        self.query = urlencode({"token": token}) if token is not None else ""
        self._in: asyncio.Queue = asyncio.Queue()
        self._out: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> "WSClient":
        scope = {
            "type": "websocket", "asgi": {"version": "3.0"}, "scheme": "ws", "http_version": "1.1",
            "path": self.path, "raw_path": self.path.encode(), "root_path": "",
            "query_string": self.query.encode(), "headers": [(b"host", b"test")],
            "client": ("127.0.0.1", 50000), "server": ("test", 80), "subprotocols": [],
        }
        self._task = asyncio.create_task(app(scope, self._in.get, self._out.put))
        await self._in.put({"type": "websocket.connect"})
        first = await asyncio.wait_for(self._out.get(), 5)
        assert first["type"] == "websocket.accept", first
        return self

    async def recv(self, timeout: float = 5) -> dict:
        msg = await asyncio.wait_for(self._out.get(), timeout)
        if msg["type"] == "websocket.close":
            raise Closed(msg.get("code", 1000))
        assert msg["type"] == "websocket.send", msg
        return json.loads(msg["text"])

    async def drain(self) -> list[dict]:
        """Every message that arrives until nothing more comes for QUIET seconds."""
        out = []
        while True:
            try:
                msg = await asyncio.wait_for(self._out.get(), QUIET)
            except asyncio.TimeoutError:
                return out
            if msg["type"] == "websocket.close":
                out.append({"__closed__": msg.get("code", 1000)})
            else:
                out.append(json.loads(msg["text"]))

    async def __aexit__(self, *exc) -> None:
        await self._in.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(self._task, 5)


def ws(c, user_id: int, role: str, session_id: int | None = None) -> WSClient:
    return WSClient(session_id or c.session_id, create_access_token(user_id, role))


async def hello(client: WSClient) -> dict:
    msg = await client.recv()
    assert msg["type"] == "connected", msg
    return msg


async def call(c, uid, role, method, path, body=None, expect=None):
    async with c.client(uid, role) as api:
        r = await api.request(method, path, json=body)
    if expect is not None:
        assert r.status_code == expect, r.text
    return r


def changed(topic: str) -> dict:
    return {"type": "changed", "topic": topic}


async def end_class(session_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await session_service.close_session(session_id, db)
        await db.commit()


async def wait_until(cond, timeout: float = 5) -> None:
    for _ in range(int(timeout / 0.02)):
        if cond():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met")


def _token(payload: dict, minutes: int = 15) -> str:
    return jwt.encode({**payload, "exp": now_myt() + timedelta(minutes=minutes)},
                      settings.SECRET_KEY, algorithm=ALGORITHM)


async def rejected(session_id: int, token: str | None) -> int:
    async with WSClient(session_id, token) as client:
        with pytest.raises(Closed) as exc:
            await client.recv()
    return exc.value.code


# ── access ────────────────────────────────────────────────────────────────────────

async def test_only_the_teaching_lecturer_and_enrolled_students_connect(shino_class):
    c = shino_class
    me = c.student_user_ids[0]
    expired = jwt.encode({"sub": str(me), "role": "student", "type": "access", "exp": 1},
                         settings.SECRET_KEY, algorithm=ALGORITHM)
    for token in [None, "", "not-a-jwt", expired, create_refresh_token(me),
                  _token({"sub": "abc", "role": "student", "type": "access"}),
                  _token({"sub": str(me), "role": "lecturer", "type": "access"}),     # wrong role
                  create_access_token(999999, "student"),                             # no such user
                  create_access_token(c.outsider_user_id, "student"),                 # not enrolled
                  create_access_token(c.other_lecturer_user_id, "lecturer")]:         # doesn't teach it
        assert await rejected(c.session_id, token) == 1008, token
    assert await rejected(999999, create_access_token(c.lecturer_user_id, "lecturer")) == 1008
    assert live.hub.count(c.session_id) == 0


async def test_inactive_user_and_admin_are_closed_with_1008(shino_class):
    c = shino_class
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == c.student_user_ids[0]).values(status="inactive"))
        admin = User(email="shino.admin@um.edu.my", password_hash="x", role="admin", name="A",
                     status="active")
        db.add(admin)
        await db.commit()
    assert await rejected(c.session_id, create_access_token(c.student_user_ids[0], "student")) == 1008
    assert await rejected(c.session_id, create_access_token(admin.id, "admin")) == 1008


async def test_connect_sends_the_join_state_and_role(shino_class):
    c = shino_class
    async with ws(c, c.lecturer_user_id, "lecturer") as lec, ws(c, c.student_user_ids[0], "student") as stu:
        a, b = await hello(lec), await hello(stu)
        assert a["role"] == "lecturer" and b["role"] == "student"
        for m in (a, b):
            assert m["status"] == "open" and m["class_status"] == "open"
            assert m["attendance_session_id"] == c.session_id and m["course_code"] == "SH101"
        assert live.hub.count(c.session_id, "lecturer") == 1
        assert live.hub.count(c.session_id, "student") == 1
        assert await lec.drain() == [] and await stu.drain() == []
    await wait_until(lambda: live.hub.count(c.session_id) == 0)


async def test_ended_class_connects_then_closes(shino_class):
    c = shino_class
    await end_class(c.session_id)
    async with ws(c, c.student_user_ids[0], "student") as stu:
        m = await hello(stu)
        assert m["status"] == "closed" and m["closed_reason"] == "class_ended"
        assert await stu.recv() == {"type": "closed", "reason": "class_ended"}
        with pytest.raises(Closed) as exc:
            await stu.recv()
        assert exc.value.code == 1000
    assert live.hub.count(c.session_id) == 0


# ── invalidations, role-separated ───────────────────────────────────────────────

async def test_questions_reach_everyone_without_identity(shino_class):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    async with ws(c, c.lecturer_user_id, "lecturer") as lec, ws(c, s1, "student") as a, \
            ws(c, s2, "student") as b:
        for x in (lec, a, b):
            await hello(x)
        base = f"/interaction/{c.session_id}/questions"
        q = (await call(c, s1, "student", "POST", base, {"text": "Why O(log n)?", "anonymous": True},
                        201)).json()
        for x in (lec, a, b):
            assert await x.drain() == [changed("questions")]       # nothing but the topic

        await call(c, s2, "student", "POST", f"{base}/{q['id']}/upvote", expect=200)
        for x in (lec, a, b):
            assert await x.drain() == [changed("questions")]
        await call(c, s2, "student", "POST", f"{base}/{q['id']}/upvote", expect=200)   # repeat
        for x in (lec, a, b):
            assert await x.drain() == []

        # hiding goes to students too (the question disappears for them), still with no id
        await call(c, c.lecturer_user_id, "lecturer", "PATCH",
                   f"/lecturer/interaction/{c.session_id}/questions/{q['id']}", {"hidden": True}, 200)
        for x in (lec, a, b):
            assert await x.drain() == [changed("questions")]


async def test_polls_drafts_and_hidden_results_stay_with_the_lecturer(shino_class):
    c = shino_class
    s1 = c.student_user_ids[0]
    lurl = f"/lecturer/interaction/{c.session_id}/polls"
    async with ws(c, c.lecturer_user_id, "lecturer") as lec, ws(c, s1, "student") as stu:
        await hello(lec), await hello(stu)
        p = (await call(c, c.lecturer_user_id, "lecturer", "POST", lurl,
                        {"question": "Next?", "options": ["A", "B"], "show_results": False}, 201)).json()
        assert await lec.drain() == [changed("polls")]
        assert await stu.drain() == []                                  # a draft: lecturer only

        await call(c, c.lecturer_user_id, "lecturer", "PATCH", f"{lurl}/{p['id']}",
                   {"show_results": True}, 200)
        assert await lec.drain() == [changed("polls")]
        assert await stu.drain() == []                                  # still a draft
        await call(c, c.lecturer_user_id, "lecturer", "PATCH", f"{lurl}/{p['id']}",
                   {"show_results": False}, 200)
        await lec.drain()

        await call(c, c.lecturer_user_id, "lecturer", "POST", f"{lurl}/{p['id']}/start", expect=200)
        assert await lec.drain() == [changed("polls")]
        assert await stu.drain() == [changed("polls")]

        option = p["options"][0]["id"]
        await call(c, c.student_user_ids[1], "student", "POST",
                   f"/interaction/{c.session_id}/polls/{p['id']}/vote", {"option_ids": [option]}, 200)
        assert await lec.drain() == [changed("polls")]
        assert await stu.drain() == []                                  # results hidden

        await call(c, c.lecturer_user_id, "lecturer", "PATCH", f"{lurl}/{p['id']}",
                   {"show_results": True}, 200)
        assert await stu.drain() == [changed("polls")]
        await lec.drain()
        await call(c, c.lecturer_user_id, "lecturer", "PATCH", f"{lurl}/{p['id']}",
                   {"show_results": True}, 200)                         # no change, no message
        assert await lec.drain() == [] and await stu.drain() == []

        await call(c, c.student_user_ids[2], "student", "POST",
                   f"/interaction/{c.session_id}/polls/{p['id']}/vote", {"option_ids": [option]}, 200)
        assert await stu.drain() == [changed("polls")]                  # results shown now
        await lec.drain()

        await call(c, c.lecturer_user_id, "lecturer", "POST", f"{lurl}/{p['id']}/close", expect=200)
        assert await lec.drain() == [changed("polls")]
        assert await stu.drain() == [changed("polls")]
        await call(c, c.lecturer_user_id, "lecturer", "POST", f"{lurl}/{p['id']}/close", expect=200)
        assert await lec.drain() == [] and await stu.drain() == []      # repeat close


async def test_quick_answers_go_to_the_lecturer_only(shino_class):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    lurl = f"/lecturer/interaction/{c.session_id}/quick-questions"
    async with ws(c, c.lecturer_user_id, "lecturer") as lec, ws(c, s1, "student") as a, \
            ws(c, s2, "student") as b:
        for x in (lec, a, b):
            await hello(x)
        q = (await call(c, c.lecturer_user_id, "lecturer", "POST", lurl, {"prompt": "One word?"}, 201)).json()
        for x in (lec, a, b):
            assert await x.drain() == [changed("quick_questions")]
        await call(c, s1, "student", "POST",
                   f"/interaction/{c.session_id}/quick-questions/{q['id']}/answer", {"text": "trees"}, 200)
        assert await lec.drain() == [changed("quick_questions")]
        assert await a.drain() == [] and await b.drain() == []
        await call(c, c.lecturer_user_id, "lecturer", "POST", f"{lurl}/{q['id']}/close", expect=200)
        for x in (lec, a, b):
            assert await x.drain() == [changed("quick_questions")]


async def test_reactions_and_confusion_go_to_the_lecturer_only(shino_class):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    async with ws(c, c.lecturer_user_id, "lecturer") as lec, ws(c, s2, "student") as stu:
        await hello(lec), await hello(stu)
        await call(c, s1, "student", "POST", f"/interaction/{c.session_id}/reactions",
                   {"kind": "thumbs_up"}, 201)
        assert await lec.drain() == [changed("reactions")]
        # a press that starts a spike: still one confusion message (the spike itself is a notification)
        await call(c, s1, "student", "POST", f"/interaction/{c.session_id}/confusion",
                   {"topic": "recursion"}, 201)
        assert await lec.drain() == [changed("confusion")]
        assert await stu.drain() == []
        # taking it back is told the same way; a lecturer's clear also tells the students (S38g)
        await call(c, s1, "student", "DELETE", f"/interaction/{c.session_id}/reactions", expect=204)
        assert await lec.drain() == [changed("reactions")]
        assert await stu.drain() == []
        await call(c, c.lecturer_user_id, "lecturer", "DELETE",
                   f"/lecturer/interaction/{c.session_id}/confusion", expect=204)
        assert await lec.drain() == [changed("confusion"), changed("signals")]
        assert await stu.drain() == [changed("signals")]
        await call(c, c.lecturer_user_id, "lecturer", "DELETE",
                   f"/lecturer/interaction/{c.session_id}/confusion", expect=204)    # nothing left
        assert await lec.drain() == [] and await stu.drain() == []


async def test_rejected_writes_send_nothing(shino_class):
    c = shino_class
    s1 = c.student_user_ids[0]
    async with ws(c, c.lecturer_user_id, "lecturer") as lec, ws(c, s1, "student") as stu:
        await hello(lec), await hello(stu)
        await call(c, s1, "student", "POST", f"/interaction/{c.session_id}/reactions", {"kind": "clear"}, 201)
        await lec.drain()
        await call(c, s1, "student", "POST", f"/interaction/{c.session_id}/reactions",
                   {"kind": "clear"}, 201)                                          # already on
        await call(c, c.lecturer_user_id, "lecturer", "POST",
                   f"/interaction/{c.session_id}/questions", {"text": "?"}, 403)    # not a student
        await call(c, c.outsider_user_id, "student", "POST",
                   f"/interaction/{c.session_id}/questions", {"text": "hi"}, 403)   # not enrolled
        await call(c, s1, "student", "POST",
                   f"/interaction/{c.session_id}/questions/999999/upvote", expect=404)
        assert await lec.drain() == [] and await stu.drain() == []


async def test_sent_only_after_commit(shino_class, monkeypatch):
    """When the message goes out, a fresh session already sees the question."""
    c = shino_class
    seen: list[int] = []
    real_send = live.hub.send

    async def checking_send(attendance_session_id, message, *, students=True):
        async with AsyncSessionLocal() as db:
            seen.append(len((await db.scalars(select(Question.id).where(
                Question.attendance_session_id == attendance_session_id))).all()))
        await real_send(attendance_session_id, message, students=students)

    monkeypatch.setattr(live.hub, "send", checking_send)
    async with ws(c, c.lecturer_user_id, "lecturer") as lec:
        await hello(lec)
        await call(c, c.student_user_ids[0], "student", "POST",
                   f"/interaction/{c.session_id}/questions", {"text": "Committed?"}, 201)
        assert await lec.drain() == [changed("questions")]
    assert seen == [1]


async def test_one_message_per_topic_per_transaction_and_none_after_rollback(shino_class):
    c = shino_class
    async with ws(c, c.lecturer_user_id, "lecturer") as lec:
        await hello(lec)
        async with AsyncSessionLocal() as db:
            live.changed(db, c.session_id, live.QUESTIONS)
            live.changed(db, c.session_id, live.QUESTIONS)
            live.changed(db, c.session_id, live.POLLS, students=False)
            await db.commit()
            await run_after_commit(db)
            assert await lec.drain() == [changed("questions"), changed("polls")]

            live.changed(db, c.session_id, live.QUESTIONS)     # rolled back: dropped ...
            await db.rollback()
            discard_after_commit(db)
            live.changed(db, c.session_id, live.QUESTIONS)     # ... a new transaction still sends
            await db.commit()
            await run_after_commit(db)
            assert await lec.drain() == [changed("questions")]
        with pytest.raises(ValueError):
            async with AsyncSessionLocal() as db:
                live.changed(db, c.session_id, "who_pressed")


async def test_other_class_sessions_hear_nothing(shino_class):
    c = shino_class
    from app.services import session_schedule
    async with AsyncSessionLocal() as db:
        occ = await db.get(ClassOccurrence, c.other_occurrence_id)
        lec = await db.get(Lecturer, c.other_lecturer_id)
        other = await session_schedule.start_now(db, occ, lec, session_schedule.clock(),
                                                 duration_minutes=60)
        await db.commit()
    async with ws(c, c.other_lecturer_user_id, "lecturer", other.id) as o, \
            ws(c, c.lecturer_user_id, "lecturer") as lec:
        await hello(o), await hello(lec)
        await call(c, c.student_user_ids[0], "student", "POST",
                   f"/interaction/{c.session_id}/questions", {"text": "Mine only"}, 201)
        assert await lec.drain() == [changed("questions")]
        assert await o.drain() == []


# ── open / close ─────────────────────────────────────────────────────────────────

async def test_lecturer_close_and_reopen_keep_the_sockets(shino_class):
    c = shino_class
    async with ws(c, c.lecturer_user_id, "lecturer") as lec, ws(c, c.student_user_ids[0], "student") as stu:
        await hello(lec), await hello(stu)
        await call(c, c.lecturer_user_id, "lecturer", "POST",
                   f"/lecturer/interaction/{c.session_id}/close", expect=200)
        for x in (lec, stu):
            assert await x.drain() == [{"type": "closed", "reason": "lecturer"}]   # still open
        await call(c, c.lecturer_user_id, "lecturer", "POST",
                   f"/lecturer/interaction/{c.session_id}/close", expect=200)       # repeat
        await call(c, c.lecturer_user_id, "lecturer", "POST",
                   f"/lecturer/interaction/{c.session_id}/open", expect=200)
        for x in (lec, stu):
            assert await x.drain() == [{"type": "opened"}]
        await call(c, c.lecturer_user_id, "lecturer", "POST",
                   f"/lecturer/interaction/{c.session_id}/open", expect=200)        # already open
        for x in (lec, stu):
            assert await x.drain() == []
        assert live.hub.count(c.session_id) == 2


async def test_class_end_sends_closed_and_closes_the_sockets(shino_class):
    c = shino_class
    async with ws(c, c.lecturer_user_id, "lecturer") as lec, ws(c, c.student_user_ids[0], "student") as stu:
        await hello(lec), await hello(stu)
        await end_class(c.session_id)                      # M3 ends the class ...
        assert await sessions.sweep() == [c.session_id]    # ... and the sweep tells the clients
        for x in (lec, stu):
            assert await x.drain() == [{"type": "closed", "reason": "class_ended"}, {"__closed__": 1000}]
    assert live.hub.count(c.session_id) == 0


async def test_class_end_after_an_early_close_still_closes_the_sockets(shino_class):
    """The sweep doesn't touch a row the lecturer closed, but connected clients still learn the
    class ended and are disconnected."""
    c = shino_class
    async with ws(c, c.lecturer_user_id, "lecturer") as lec, ws(c, c.student_user_ids[0], "student") as stu:
        await hello(lec), await hello(stu)
        await call(c, c.lecturer_user_id, "lecturer", "POST",
                   f"/lecturer/interaction/{c.session_id}/close", expect=200)
        for x in (lec, stu):
            assert await x.drain() == [{"type": "closed", "reason": "lecturer"}]
        await end_class(c.session_id)
        assert await sessions.sweep() == []                # the row was already closed ...
        for x in (lec, stu):                               # ... yet the clients are told and dropped
            assert await x.drain() == [{"type": "closed", "reason": "class_ended"}, {"__closed__": 1000}]
    assert live.hub.count(c.session_id) == 0
    # connecting afterwards says the same
    async with ws(c, c.student_user_ids[0], "student") as stu:
        await hello(stu)
        assert await stu.recv() == {"type": "closed", "reason": "class_ended"}


async def test_send_failure_drops_the_socket_but_not_the_write(shino_class, monkeypatch):
    c = shino_class
    async with ws(c, c.lecturer_user_id, "lecturer") as lec:
        await hello(lec)
        conn = next(iter(live.hub._conns[c.session_id]))

        async def boom(message):
            raise RuntimeError("socket gone")

        monkeypatch.setattr(conn.ws, "send_json", boom)
        await call(c, c.student_user_ids[0], "student", "POST",
                   f"/interaction/{c.session_id}/questions", {"text": "Still saved"}, 201)
        assert live.hub.count(c.session_id) == 0
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(Question.id).where(Question.text == "Still saved"))
