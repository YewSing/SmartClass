"""S12: live notifications over `WS /notifications/ws` (FR-213).

The websocket is driven in-process through a tiny ASGI client (`WSClient`), so it runs on the
test's own event loop next to asyncpg; nothing leaves the process.
"""
import asyncio
import json
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from jose import jwt
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import ALGORITHM, create_access_token, create_refresh_token
from app.core.timezone import now_myt
from app.main import app
from app.models.notification import Notification
from app.models.user import User
from app.services import notify
from app.services.notifications import live

pytestmark = pytest.mark.db

QUIZ = {"quiz_id": 7, "quiz_title": "Week 3 quiz", "course_code": "SH101"}
QUIET = 0.3     # how long "nothing arrives" is waited for


class Closed(Exception):
    def __init__(self, code: int):
        super().__init__(code)
        self.code = code


class WSClient:
    """A minimal ASGI websocket client for one connection to the app."""

    def __init__(self, token: str | None):
        self.query = urlencode({"token": token}) if token is not None else ""
        self._in: asyncio.Queue = asyncio.Queue()
        self._out: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> "WSClient":
        scope = {
            "type": "websocket", "asgi": {"version": "3.0"}, "scheme": "ws", "http_version": "1.1",
            "path": "/notifications/ws", "raw_path": b"/notifications/ws", "root_path": "",
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

    async def nothing(self) -> bool:
        """True if no message arrives within QUIET seconds."""
        try:
            await asyncio.wait_for(self._out.get(), QUIET)
        except asyncio.TimeoutError:
            return True
        return False

    async def __aexit__(self, *exc) -> None:
        await self._in.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(self._task, 5)


def ws(user_id: int, role: str) -> WSClient:
    return WSClient(create_access_token(user_id, role))


async def connected(c: WSClient) -> int:
    msg = await c.recv()
    assert msg["type"] == "connected"
    return msg["unread_count"]


async def rejected(token: str | None) -> int:
    async with WSClient(token) as c:
        with pytest.raises(Closed) as exc:
            await c.recv()
    return exc.value.code


async def wait_until(cond, timeout: float = 5) -> None:
    for _ in range(int(timeout / 0.02)):
        if cond():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met")


# ── authentication ───────────────────────────────────────────────────────────────

def _token(payload: dict, minutes: int = 15) -> str:
    return jwt.encode({**payload, "exp": now_myt() + timedelta(minutes=minutes)},
                      settings.SECRET_KEY, algorithm=ALGORITHM)


async def test_bad_tokens_are_closed_with_1008(shino_class):
    me = shino_class.student_user_ids[0]
    expired = jwt.encode({"sub": str(me), "role": "student", "type": "access", "exp": 1},
                         settings.SECRET_KEY, algorithm=ALGORITHM)
    for token in [None, "", "not-a-jwt", expired, create_refresh_token(me),
                  _token({"sub": "abc", "role": "student", "type": "access"}),
                  _token({"sub": str(me), "role": "lecturer", "type": "access"}),   # wrong role
                  create_access_token(999999, "student")]:                          # no such user
        assert await rejected(token) == 1008, token
    assert not live.hub.is_connected(me)


async def test_inactive_user_is_closed_with_1008(shino_class):
    me = shino_class.student_user_ids[0]
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == me).values(status="inactive"))
        await db.commit()
    assert await rejected(create_access_token(me, "student")) == 1008


async def test_connect_sends_the_current_unread_count(shino_class):
    me = shino_class.student_user_ids[0]
    await notify.emit("quiz.published", [me], QUIZ)
    async with ws(me, "student") as c:
        assert await connected(c) == 1
        assert await c.nothing()
    for role, uid in [("lecturer", shino_class.lecturer_user_id)]:
        async with ws(uid, role) as c:
            assert await connected(c) == 0


# ── delivery ─────────────────────────────────────────────────────────────────────

async def test_delivered_to_every_connection_of_the_recipient_only(shino_class):
    me, other = shino_class.student_user_ids[:2]
    async with ws(me, "student") as a, ws(me, "student") as b, ws(other, "student") as o:
        for c in (a, b, o):
            assert await connected(c) == 0
        await notify.emit("quiz.published", [me], QUIZ)
        for c in (a, b):
            msg = await c.recv()
            assert msg["type"] == "notification" and msg["unread_count"] == 1
            n = msg["notification"]
            assert n["event"] == "quiz.published" and n["priority"] == "important"
            assert n["read"] is False and "Week 3 quiz" in n["title"] + n["message"]
            assert set(n) == {"id", "event", "priority", "title", "message", "link", "read",
                              "read_at", "created_at"}
        assert await o.nothing()


async def test_each_recipient_gets_their_own_row_and_count(shino_class):
    a_id, b_id = shino_class.student_user_ids[:2]
    await notify.emit("quiz.published", [b_id], {**QUIZ, "quiz_id": 1})   # b already has one
    async with ws(a_id, "student") as a, ws(b_id, "student") as b:
        await connected(a), await connected(b)
        await notify.emit("quiz.published", [a_id, b_id], QUIZ)
        ma, mb = await a.recv(), await b.recv()
    assert (ma["unread_count"], mb["unread_count"]) == (1, 2)
    async with AsyncSessionLocal() as db:
        owner = {r.id: r.user_id for r in (await db.scalars(select(Notification))).all()}
    assert owner[ma["notification"]["id"]] == a_id and owner[mb["notification"]["id"]] == b_id


async def test_sent_only_after_commit(shino_class, monkeypatch):
    """When the message is sent, a fresh session already sees the row."""
    me = shino_class.student_user_ids[0]
    seen: list[bool] = []
    real_send = live.hub.send

    async def checking_send(user_id, message):
        async with AsyncSessionLocal() as db:
            nid = message["notification"]["id"]
            seen.append(await db.scalar(select(Notification.id).where(Notification.id == nid)) == nid)
        await real_send(user_id, message)

    monkeypatch.setattr(live.hub, "send", checking_send)
    async with ws(me, "student") as c:
        await connected(c)
        await notify.emit("quiz.published", [me], QUIZ)
        assert (await c.recv())["type"] == "notification"
    assert seen == [True]


async def test_nothing_sent_when_nothing_is_stored(shino_class):
    """A duplicate (dropped by FR-216) or an unknown event stores nothing and sends nothing."""
    me = shino_class.student_user_ids[0]
    await notify.emit("quiz.published", [me], QUIZ)
    async with ws(me, "student") as c:
        assert await connected(c) == 1
        await notify.emit("quiz.published", [me], QUIZ)        # same subject inside the window
        await notify.emit("no.such.event", [me], QUIZ)
        assert await c.nothing()


async def test_publish_failure_never_fails_the_event(shino_class, monkeypatch):
    me = shino_class.student_user_ids[0]

    async def boom(user_id, message):
        raise RuntimeError("socket gone")

    async with ws(me, "student") as c:
        await connected(c)
        monkeypatch.setattr(live.hub, "send", boom)
        await notify.emit("quiz.published", [me], QUIZ)        # must not raise
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(Notification.id).where(Notification.user_id == me))


async def test_reconnect_gets_nothing_stale(shino_class):
    me = shino_class.student_user_ids[0]
    async with ws(me, "student") as c:
        await connected(c)
    await wait_until(lambda: not live.hub.is_connected(me))
    await notify.emit("quiz.published", [me], QUIZ)            # while no screen is open
    async with ws(me, "student") as c:
        assert await connected(c) == 1                         # the count is current ...
        assert await c.nothing()                               # ... but nothing is replayed


async def test_closed_connection_is_dropped_from_the_hub(shino_class):
    me = shino_class.student_user_ids[0]
    async with ws(me, "student") as c:
        await connected(c)
        assert live.hub.is_connected(me)
    await wait_until(lambda: not live.hub.is_connected(me))


# ── read state ───────────────────────────────────────────────────────────────────

async def test_read_and_read_all_update_other_screens(shino_class):
    me = shino_class.student_user_ids[0]
    await notify.emit("quiz.published", [me], QUIZ)
    await notify.emit("quiz.published", [me], {**QUIZ, "quiz_id": 8})
    await notify.emit("quiz.published", [me], {**QUIZ, "quiz_id": 9})
    async with AsyncSessionLocal() as db:
        first = await db.scalar(select(Notification.id).where(Notification.user_id == me)
                                .order_by(Notification.id))
    async with ws(me, "student") as c, shino_class.client(me, "student") as http:
        assert await connected(c) == 3
        assert (await http.post(f"/notifications/{first}/read")).status_code == 200
        assert await c.recv() == {"type": "unread_count", "unread_count": 2}
        assert (await http.post("/notifications/read-all")).json()["marked"] == 2
        assert await c.recv() == {"type": "unread_count", "unread_count": 0}
        assert (await http.post("/notifications/read-all")).json()["marked"] == 0
        assert await c.nothing()                               # nothing changed, nothing sent


async def test_someone_elses_read_sends_nothing(shino_class):
    me, other = shino_class.student_user_ids[:2]
    await notify.emit("quiz.published", [me], QUIZ)
    async with AsyncSessionLocal() as db:
        nid = await db.scalar(select(Notification.id).where(Notification.user_id == me))
    async with ws(me, "student") as c, shino_class.client(other, "student") as http:
        await connected(c)
        assert (await http.post(f"/notifications/{nid}/read")).status_code == 404
        assert (await http.post("/notifications/read-all")).status_code == 200
        assert await c.nothing()
