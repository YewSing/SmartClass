"""Interaction session lifecycle and access (FR-501, FR-502) — S30.

The interaction belongs to one M3 class session (`AttendanceSession`) and follows it:

- While the class session is `open`, the interaction is open unless the teaching lecturer closed
  it early; the lecturer may reopen it while the class is still running (FR-501).
- The moment the class session is not `open` (ended, cancelled, needs confirmation, or not started
  yet) the interaction counts as closed, whatever its row says. Every write checks this through
  `require_open`, which holds a share lock on the class session row so M3 cannot close the class
  half-way through the write (its UPDATE waits for the write to commit, or the write sees it closed).
- `sweep()` (a background loop, every `INTERACTION_SWEEP_SECONDS`) writes `closed/class_ended` onto
  the rows of ended classes and tells the `on_closed` listeners after its commit, so connected
  clients (S35 websocket) learn it within the interval.

Nothing here opens, extends or closes the class session itself; no M3 code calls this module.

Access (NFR-04, FR-502): the lecturer assigned to the class, or an active student enrolled in it.
Everyone else, and an unknown class session id, gets 403 (ids can't be probed).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, after_commit
from app.core.deps import ensure_teaches_occurrence
from app.core.timezone import now_myt
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.interaction import InteractionSession
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.services.audit_service import write_log

log = logging.getLogger(__name__)

ROLE_LECTURER = "lecturer"
ROLE_STUDENT = "student"

# Called with the attendance_session_id after a commit that closed an interaction (lecturer close
# or sweep). S35's websocket registers here to send `closed`. A failing listener is logged only.
ClosedListener = Callable[[int], Awaitable[None]]
on_closed: list[ClosedListener] = []


def clock() -> datetime:
    """Current naive MYT time. Tests monkeypatch this."""
    return now_myt()


def _forbidden() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                         detail="You are not part of this class")


def closed_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interaction is closed")


@dataclass
class Member:
    """Who is acting in this interaction: `role` is `lecturer` or `student`; `student_id` is the
    caller's students.id (None for the lecturer)."""
    user_id: int
    role: str
    student_id: int | None = None


@dataclass
class InteractionState:
    attendance_session_id: int
    occurrence_id: int | None
    course_code: str | None
    course_name: str | None
    class_status: str               # the M3 session status
    status: str                     # open | closed (effective)
    closed_reason: str | None       # lecturer | class_ended | not_started | None while open
    opened_at: datetime | None
    closed_at: datetime | None

    @property
    def is_open(self) -> bool:
        return self.status == "open"


# ── access ───────────────────────────────────────────────────────────────────

async def authorize(db: AsyncSession, actor: User, attendance_session_id: int) -> tuple[AttendanceSession, Member]:
    """The class session and the caller's role in it; 403 for anyone who isn't the teaching
    lecturer or an enrolled student, and for an unknown id."""
    session = await db.get(AttendanceSession, attendance_session_id)
    if session is None:
        raise _forbidden()
    if actor.role == ROLE_LECTURER:
        if session.occurrence_id is not None:
            try:
                await ensure_teaches_occurrence(db, actor, session.occurrence_id)
            except HTTPException:
                raise _forbidden() from None
        else:   # a class session without a timetable class: only the lecturer who ran it
            lecturer_id = await db.scalar(select(Lecturer.id).where(Lecturer.user_id == actor.id))
            if lecturer_id is None or lecturer_id != session.lecturer_id:
                raise _forbidden()
        return session, Member(user_id=actor.id, role=ROLE_LECTURER)
    if actor.role == ROLE_STUDENT and session.occurrence_id is not None:
        student_id = await db.scalar(
            select(Student.id).join(Enrollment, Enrollment.student_id == Student.id)
            .where(Student.user_id == actor.id, Enrollment.occurrence_id == session.occurrence_id))
        if student_id is not None:
            return session, Member(user_id=actor.id, role=ROLE_STUDENT, student_id=student_id)
    raise _forbidden()


def require_lecturer(member: Member) -> None:
    if member.role != ROLE_LECTURER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only the class's lecturer can do this")


# ── state ────────────────────────────────────────────────────────────────────

def effective(session: AttendanceSession, row: InteractionSession | None) -> tuple[str, str | None]:
    """(status, closed_reason) from the class session and the interaction row."""
    if session.status == "open":
        if row is not None and row.status == "closed":
            return "closed", row.closed_reason or "lecturer"
        return "open", None
    if session.status == "scheduled":
        return "closed", "not_started"
    if row is not None and row.status == "closed" and row.closed_reason:
        return "closed", row.closed_reason
    return "closed", "class_ended"


async def _row(db: AsyncSession, attendance_session_id: int, lock: str | None = None) -> InteractionSession | None:
    stmt = select(InteractionSession).where(InteractionSession.attendance_session_id == attendance_session_id)
    if lock == "update":
        stmt = stmt.with_for_update()
    elif lock == "share":
        stmt = stmt.with_for_update(read=True)
    stmt = stmt.execution_options(populate_existing=True)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _ensure_row(db: AsyncSession, session: AttendanceSession) -> None:
    """Create the open row of a running class (idempotent, safe under concurrency)."""
    await db.execute(
        insert(InteractionSession)
        .values(attendance_session_id=session.id, status="open", opened_at=session.opened_at or clock())
        .on_conflict_do_nothing(index_elements=["attendance_session_id"]))


async def _lock_class(db: AsyncSession, attendance_session_id: int) -> AttendanceSession:
    """Share-lock the class session row and read its current status (M3's close waits for us)."""
    stmt = (select(AttendanceSession).where(AttendanceSession.id == attendance_session_id)
            .with_for_update(read=True).execution_options(populate_existing=True))
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise _forbidden()
    return session


async def state(db: AsyncSession, session: AttendanceSession) -> InteractionState:
    row = await _row(db, session.id)
    st, reason = effective(session, row)
    course = None
    if session.occurrence_id is not None:
        course = (await db.execute(
            select(Course.code, Course.name).join(ClassOccurrence, ClassOccurrence.course_id == Course.id)
            .where(ClassOccurrence.id == session.occurrence_id))).first()
    if st == "open":
        opened_at, closed_at = (row.opened_at if row else None) or session.opened_at, None
    else:
        opened_at = row.opened_at if row else None
        closed_at = (row.closed_at if row is not None and row.status == "closed" else None) or session.closed_at
    return InteractionState(
        attendance_session_id=session.id, occurrence_id=session.occurrence_id,
        course_code=course[0] if course else None, course_name=course[1] if course else None,
        class_status=session.status, status=st, closed_reason=reason,
        opened_at=opened_at, closed_at=closed_at)


async def join(db: AsyncSession, session: AttendanceSession) -> InteractionState:
    """The state a joining client sees. A running class gets its row here, so the sweep can
    later close it and tell connected clients."""
    if session.status == "open":
        await _ensure_row(db, session)
    return await state(db, session)


# ── writes ───────────────────────────────────────────────────────────────────

async def require_open(db: AsyncSession, attendance_session_id: int) -> InteractionSession:
    """Call first in every interaction write (S31–S33). Share-locks the class session and the
    interaction row until the transaction ends, so neither M3's close nor the lecturer's close can
    slip in between the check and the write. 409 when closed."""
    session = await _lock_class(db, attendance_session_id)
    if session.status != "open":
        raise closed_error()
    await _ensure_row(db, session)
    row = await _row(db, attendance_session_id, lock="share")
    if row is None or row.status != "open":
        raise closed_error()
    return row


async def open_interaction(db: AsyncSession, actor: User, attendance_session_id: int) -> None:
    """Lecturer (re)opens the interaction of a running class. 409 when the class isn't open."""
    session = await _lock_class(db, attendance_session_id)
    if session.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="The class is not running, so interaction can't be opened")
    await _ensure_row(db, session)
    row = await _row(db, attendance_session_id, lock="update")
    if row.status == "open":
        return
    row.status, row.closed_reason, row.closed_at, row.closed_by_user_id = "open", None, None, None
    row.opened_at = clock()
    await write_log(db, actor.id, "INTERACTION_OPENED", "attendance_session", attendance_session_id,
                    {"status": "closed"}, {"status": "open"})
    await db.flush()


async def close_interaction(db: AsyncSession, actor: User, attendance_session_id: int) -> None:
    """Lecturer closes the interaction early (idempotent). The class session keeps running."""
    session = await _lock_class(db, attendance_session_id)
    if session.status != "open":
        return   # already closed by the class itself
    await _ensure_row(db, session)
    row = await _row(db, attendance_session_id, lock="update")
    if row.status == "closed":
        return
    row.status, row.closed_reason, row.closed_at, row.closed_by_user_id = "closed", "lecturer", clock(), actor.id
    await write_log(db, actor.id, "INTERACTION_CLOSED", "attendance_session", attendance_session_id,
                    {"status": "open"}, {"status": "closed", "reason": "lecturer"})
    await db.flush()

    async def _announce() -> None:
        await _notify_closed([attendance_session_id])

    after_commit(db, _announce)


# ── sweep ────────────────────────────────────────────────────────────────────

async def _notify_closed(ids: list[int]) -> None:
    for attendance_session_id in ids:
        for listener in list(on_closed):
            try:
                await listener(attendance_session_id)
            except Exception as exc:   # a listener must never break the sweep or a request
                log.warning("interaction closed listener failed: %s", exc.__class__.__name__)


async def sweep() -> list[int]:
    """Close (in the table) every open interaction whose class session is no longer open, then
    tell the listeners. Returns the attendance_session_ids it closed."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(InteractionSession)
            .where(InteractionSession.status == "open",
                   InteractionSession.attendance_session_id == AttendanceSession.id,
                   AttendanceSession.status != "open")
            .values(status="closed", closed_reason="class_ended",
                    closed_at=func.coalesce(AttendanceSession.closed_at, clock()))
            .returning(InteractionSession.attendance_session_id)
            .execution_options(synchronize_session=False))
        ids = [r[0] for r in result.all()]
        await db.commit()
    if ids:
        await _notify_closed(ids)
    return ids


async def interaction_sweep_loop() -> None:
    """Background task started in main.py. `INTERACTION_SWEEP_SECONDS` <= 0 turns it off."""
    if settings.INTERACTION_SWEEP_SECONDS <= 0:
        return
    while True:
        try:
            closed = await sweep()
            if closed:
                log.info("interaction sweep: closed %d interaction(s) of ended classes", len(closed))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("interaction sweep failed")
        await _sleep(settings.INTERACTION_SWEEP_SECONDS)


_sleep = asyncio.sleep   # tests replace this (not asyncio.sleep itself)
