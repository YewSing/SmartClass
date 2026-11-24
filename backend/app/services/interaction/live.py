"""Live interaction updates over a websocket (FR-516) — S35.

Every open `WS /interaction/{attendance_session_id}/ws` connection is registered here with the
caller's role in that class (`lecturer` or `student`). Messages are invalidations, not data: they
say *what* changed (a topic) and the client re-reads it through the REST endpoints, which already
shape every response per role (no identities, no hidden questions or drafts for students). So no
message carries a student, a user, an item id or any text.

Messages (all JSON):
- `{"type":"connected","role",...state}` once, on connect (see the router).
- `{"type":"changed","topic":<topic>}` after a commit that changed `topic`:
  `questions`, `polls`, `quick_questions` (everyone, or the lecturer only when students can't see the
  change: a draft poll, votes while results are hidden, a quick answer) and `reactions`, `confusion`
  (lecturer only), `signals` (the lecturer cleared everyone's reactions or confusion).
- `{"type":"opened"}` when the lecturer reopens the interaction.
- `{"type":"closed","reason":"lecturer"|"class_ended"|...}` when it closes. When the class itself
  is no longer running the server then closes the socket (1000); after a lecturer's early close the
  socket stays open for a reopen.

Everything is sent only after the DB commit (`after_commit`), so a client that re-reads sees the
change. A topic is sent at most once per transaction and audience. Nothing is queued for closed
sockets: a client re-reads everything after `connected`. The hub lives in the API process (one
uvicorn worker, as for the notification hub).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import _AFTER_COMMIT as _AFTER_COMMIT_KEY
from app.core.database import AsyncSessionLocal, after_commit
from app.models.session import AttendanceSession
from app.services.interaction import sessions

log = logging.getLogger(__name__)

QUESTIONS = "questions"
POLLS = "polls"
QUICK_QUESTIONS = "quick_questions"
REACTIONS = "reactions"
CONFUSION = "confusion"
SIGNALS = "signals"             # the lecturer cleared reactions or confusion: students re-read their own
TOPICS = (QUESTIONS, POLLS, QUICK_QUESTIONS, REACTIONS, CONFUSION, SIGNALS)
LECTURER_ONLY = {REACTIONS, CONFUSION}

SEND_TIMEOUT_SECONDS = 2.0      # a stuck client is dropped instead of holding up the request
_PENDING = "m5_live_pending"    # db.info key: (topic, students) already queued this transaction


@dataclass(eq=False)
class Conn:
    ws: WebSocket
    role: str


class InteractionHub:
    """attendance_session_id -> its open interaction sockets."""

    def __init__(self) -> None:
        self._conns: dict[int, set[Conn]] = {}

    def add(self, attendance_session_id: int, ws: WebSocket, role: str) -> Conn:
        conn = Conn(ws=ws, role=role)
        self._conns.setdefault(attendance_session_id, set()).add(conn)
        return conn

    def remove(self, attendance_session_id: int, conn: Conn) -> None:
        conns = self._conns.get(attendance_session_id)
        if conns is not None:
            conns.discard(conn)
            if not conns:
                self._conns.pop(attendance_session_id, None)

    def count(self, attendance_session_id: int, role: str | None = None) -> int:
        return sum(1 for c in self._conns.get(attendance_session_id, ())
                   if role is None or c.role == role)

    def _targets(self, attendance_session_id: int, students: bool) -> list[Conn]:
        return [c for c in self._conns.get(attendance_session_id, ())
                if c.role == sessions.ROLE_LECTURER or (students and c.role == sessions.ROLE_STUDENT)]

    async def send(self, attendance_session_id: int, message: dict, *, students: bool = True) -> None:
        """Send to the lecturer's sockets, and to the students' when `students`. A socket that
        fails or stalls is dropped."""
        for conn in self._targets(attendance_session_id, students):
            try:
                await asyncio.wait_for(conn.ws.send_json(message), SEND_TIMEOUT_SECONDS)
            except Exception:
                self.remove(attendance_session_id, conn)

    async def close_all(self, attendance_session_id: int, code: int = 1000) -> None:
        for conn in list(self._conns.pop(attendance_session_id, ())):
            try:
                await asyncio.wait_for(conn.ws.close(code=code), SEND_TIMEOUT_SECONDS)
            except Exception:
                pass


hub = InteractionHub()


def changed(db: AsyncSession, attendance_session_id: int, topic: str, *, students: bool = True) -> None:
    """After `db` commits, tell the class's sockets that `topic` changed. Reactions and confusion
    always go to the lecturer only."""
    if topic not in TOPICS:
        raise ValueError(f"unknown interaction topic {topic!r}")
    students = students and topic not in LECTURER_ONLY
    pending: dict = db.info.setdefault(_PENDING, {})
    key = (attendance_session_id, topic, students)
    queued = pending.get(key)
    if queued is not None and queued in db.info.get(_AFTER_COMMIT_KEY, ()):
        return      # the same message is already waiting for this commit

    async def _send() -> None:
        pending.pop(key, None)
        await hub.send(attendance_session_id, {"type": "changed", "topic": topic}, students=students)

    pending[key] = _send
    after_commit(db, _send)


def opened(db: AsyncSession, attendance_session_id: int) -> None:
    """After `db` commits, tell everyone the lecturer reopened the interaction."""
    async def _send() -> None:
        await hub.send(attendance_session_id, {"type": "opened"})

    after_commit(db, _send)


async def announce_closed(attendance_session_id: int) -> None:
    """`sessions.on_closed` listener (after the commit of a lecturer close or the sweep): send
    `closed` with the reason; close the sockets too once the class itself isn't running."""
    if not hub.count(attendance_session_id):
        return
    async with AsyncSessionLocal() as db:
        session = await db.get(AttendanceSession, attendance_session_id)
        if session is None:
            await hub.close_all(attendance_session_id)
            return
        st = await sessions.state(db, session)
    if st.is_open:          # reopened before we got here: nothing to announce
        return
    await hub.send(attendance_session_id, {"type": "closed", "reason": closed_reason(st)})
    if st.class_status != "open":
        await hub.close_all(attendance_session_id)


def closed_reason(st: sessions.InteractionState) -> str | None:
    """The reason a `closed` message gives: once the class itself isn't running that is what
    matters to the client, even if the lecturer had closed the interaction earlier."""
    if st.class_status != "open" and st.closed_reason == "lecturer":
        return "class_ended"
    return st.closed_reason


async def reap_ended() -> None:
    """`sessions.on_sweep` hook: announce and close the sockets of every connected class session
    that is no longer running (covers classes whose interaction the lecturer had closed early)."""
    ids = list(hub._conns)
    if not ids:
        return
    async with AsyncSessionLocal() as db:
        ended = list((await db.scalars(
            select(AttendanceSession.id).where(AttendanceSession.id.in_(ids),
                                               AttendanceSession.status != "open"))).all())
    for attendance_session_id in ended:
        await announce_closed(attendance_session_id)


if announce_closed not in sessions.on_closed:
    sessions.on_closed.append(announce_closed)
if reap_ended not in sessions.on_sweep:
    sessions.on_sweep.append(reap_ended)
