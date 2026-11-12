"""Sessions from the class schedule (FR-301, FR-315–FR-317).

Rules:
- R1 – one row per scheduled class date. A row with `source="schedule"` is "the class on
  `class_date`"; the job never creates a second one (a partial unique index backs this up).
- R2 – the job opens. For every occurrence with a schedule and a lecturer, for today and
  tomorrow (a class may start just after midnight), if the class is within the early-open
  window and it has no schedule row for that date and no open session, it inserts one.
  So at most one scheduled session per class per day: editing the weekly time after today's
  class ran opens nothing more today (Start now does). A `scheduled` row (left by the one-class
  time change removed in T38b) still opens the same way.
- R3 – the job closes. An open row whose `ends_at` has passed becomes `closed` when it has
  at least one attendance record or the lecturer acted during the class; otherwise it becomes
  `needs_confirmation` (nobody is marked Absent without the lecturer confirming, FR-317).
  A `scheduled` row whose whole slot was missed becomes `needs_confirmation` too.
- R4 – a lecturer action (`lecturer_action_at`) is start now or extend while the session is
  open. Overrides already create an attendance record, so they count through the record check.
  Unidentified faces are not recognitions.
- R5 – a class without a schedule is never opened by the job; Start now works.
- R6 – the job never touches `ClassOccurrence` columns.
- T38b removed changing or cancelling one class (FR-316): a class that didn't happen is
  confirmed "Not held" (FR-317). Old `scheduled`/`cancelled` rows still load and behave as before.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, run_after_commit
from app.core.timezone import now_myt
from app.models.attendance import AttendanceRecord
from app.models.camera import Camera
from app.models.class_ import ClassOccurrence
from app.models.session import AttendanceSession
from app.models.user import Lecturer
from app.services import session_service
from app.services.audit_service import write_log
from app.websocket.manager import manager

log = logging.getLogger(__name__)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]   # index == date.weekday()


def clock() -> datetime:
    """Current naive MYT time. Tests monkeypatch this (controlled clock)."""
    return now_myt()


def parse_hhmm(value: str) -> time:
    """"08:00" -> time(8, 0); ValueError otherwise."""
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid time {value!r}; expected HH:MM") from exc


def scheduled_times(occ: ClassOccurrence, d: date) -> tuple[datetime, datetime] | None:
    """The weekly slot of `occ` on date `d`, or None when there is no class that day."""
    if not occ.has_schedule or DAYS[d.weekday()] != occ.day_of_week:
        return None
    return (datetime.combine(d, parse_hhmm(occ.start_time)),
            datetime.combine(d, parse_hhmm(occ.end_time)))


def early() -> timedelta:
    return timedelta(minutes=settings.SESSION_EARLY_OPEN_MINUTES)


async def camera_id_for_room(db: AsyncSession, room: str | None) -> int | None:
    """The camera registered to a room, if any."""
    if not room:
        return None
    cam = (await db.execute(select(Camera).where(Camera.room == room))).scalar_one_or_none()
    return cam.id if cam else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def _schedule_row(db: AsyncSession, occurrence_id: int, class_date: date) -> AttendanceSession | None:
    return (await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.occurrence_id == occurrence_id,
            AttendanceSession.class_date == class_date,
            AttendanceSession.source == "schedule",
        )
    )).scalar_one_or_none()


async def _has_records(db: AsyncSession, session_id: int) -> bool:
    return (await db.scalar(
        select(AttendanceRecord.id).where(AttendanceRecord.session_id == session_id).limit(1)
    )) is not None


@dataclass
class TickReport:
    opened: list[int] = field(default_factory=list)
    closed: list[int] = field(default_factory=list)
    needs_confirmation: list[int] = field(default_factory=list)


async def open_session_for(db: AsyncSession, occ: ClassOccurrence, d: date,
                           start: datetime, end: datetime, now: datetime) -> AttendanceSession:
    """Insert and flush the scheduled session of `occ` on date `d` (R2)."""
    session = AttendanceSession(
        occurrence_id=occ.id,
        lecturer_id=occ.lecturer_id,
        camera_id=await camera_id_for_room(db, occ.room),
        class_date=d,
        starts_at=start,
        ends_at=end,
        source="schedule",
        status="open",
        opened_at=now,
    )
    db.add(session)
    await db.flush()
    return session


async def tick(db: AsyncSession, now: datetime | None = None) -> TickReport:
    """One pass of R3 then R2. Flushes, does not commit. `now` defaults to clock()."""
    now = now or clock()
    report = TickReport()

    # R3 – close what has ended.
    open_rows = (await db.execute(
        select(AttendanceSession).where(AttendanceSession.status == "open")
    )).scalars().all()
    for session in open_rows:
        if session.ends_at is None or session.ends_at > now:
            continue  # legacy rows without an end are never auto-closed
        if await _has_records(db, session.id) or session.lecturer_action_at is not None:
            await session_service.close_session(session.id, db, now)
            report.closed.append(session.id)
        else:
            session.status = "needs_confirmation"
            session.closed_at = now
            report.needs_confirmation.append(session.id)

    missed = (await db.execute(
        select(AttendanceSession).where(AttendanceSession.status == "scheduled")
    )).scalars().all()
    for session in missed:
        if session.ends_at is not None and session.ends_at <= now:
            session.status = "needs_confirmation"
            session.closed_at = now
            report.needs_confirmation.append(session.id)

    await db.flush()

    # R2 – open what has started.
    occurrences = (await db.execute(
        select(ClassOccurrence).where(ClassOccurrence.lecturer_id.is_not(None))
    )).scalars().all()
    for occ in occurrences:
        if not occ.has_schedule:
            continue  # R5

        for d in (now.date(), now.date() + timedelta(days=1)):
            times = scheduled_times(occ, d)
            if times is None:
                continue
            start, end = times
            if not (start - early() <= now < end):
                continue
            if await _schedule_row(db, occ.id, d) is not None:
                continue
            if await db.scalar(select(AttendanceSession.id).where(
                AttendanceSession.occurrence_id == occ.id,
                AttendanceSession.status == "open",
            )) is not None:
                continue
            session = await open_session_for(db, occ, d, start, end, now)
            report.opened.append(session.id)

        pending = (await db.execute(
            select(AttendanceSession).where(
                AttendanceSession.occurrence_id == occ.id,
                AttendanceSession.status == "scheduled",
                AttendanceSession.starts_at.is_not(None),
                AttendanceSession.ends_at.is_not(None),
            )
        )).scalars().all()
        for session in pending:
            if not (session.starts_at - early() <= now < session.ends_at):
                continue
            if await db.scalar(select(AttendanceSession.id).where(
                AttendanceSession.occurrence_id == occ.id,
                AttendanceSession.status == "open",
            )) is not None:
                continue
            session.status = "open"
            session.opened_at = now
            session.camera_id = await camera_id_for_room(db, occ.room)
            report.opened.append(session.id)

    await db.flush()
    return report


async def session_scheduler_loop() -> None:
    """Background task started in main.py; SESSION_SCHEDULER_INTERVAL_SECONDS <= 0 disables it."""
    if settings.SESSION_SCHEDULER_INTERVAL_SECONDS <= 0:
        return
    while True:
        try:
            async with AsyncSessionLocal() as db:
                try:
                    report = await tick(db)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
                await run_after_commit(db)   # closed sessions go to Moodle now (T38b)
            for sid in report.closed + report.needs_confirmation:
                async with AsyncSessionLocal() as db:
                    counts = await session_service.get_session_counts(sid, db)
                    sync_status = await db.scalar(select(AttendanceSession.moodle_sync_status)
                                                  .where(AttendanceSession.id == sid))
                await manager.broadcast(sid, {
                    "event": "session_closed",
                    "status": "closed" if sid in report.closed else "needs_confirmation",
                    "counts": counts,
                    "final": True,
                    "moodle_sync_status": sync_status,
                })
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Session scheduler failed: %s", exc.__class__.__name__)
        await asyncio.sleep(settings.SESSION_SCHEDULER_INTERVAL_SECONDS)


# ── Lecturer operations (routers call these; none changes the weekly schedule) ──

async def set_weekly_schedule(db: AsyncSession, occ: ClassOccurrence, body, actor) -> ClassOccurrence:
    """Set or clear the weekly slot. Existing session rows are not changed."""
    old = {
        "day_of_week": occ.day_of_week,
        "start_time": occ.start_time,
        "end_time": occ.end_time,
        "room": occ.room,
    }
    occ.day_of_week = body.day_of_week
    occ.start_time = body.start_time
    occ.end_time = body.end_time
    occ.room = body.room
    new = {
        "day_of_week": occ.day_of_week,
        "start_time": occ.start_time,
        "end_time": occ.end_time,
        "room": occ.room,
    }
    await db.flush()
    await write_log(db, actor.id, "CLASS_SCHEDULE_SET", "class_occurrence", occ.id, old, new)
    await db.flush()
    return occ


def _scheduled_length(occ: ClassOccurrence) -> timedelta:
    start = parse_hhmm(occ.start_time)
    end = parse_hhmm(occ.end_time)
    return timedelta(hours=end.hour - start.hour, minutes=end.minute - start.minute)


async def start_now(db: AsyncSession, occ: ClassOccurrence, lec: Lecturer,
                    now: datetime, duration_minutes: int | None) -> AttendanceSession:
    """Start the class now (FR-316). Uses today's slot when there is one, else a manual row."""
    if await db.scalar(select(AttendanceSession.id).where(
        AttendanceSession.occurrence_id == occ.id,
        AttendanceSession.status == "open",
    )) is not None:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT,
                            detail="A session is already open for this occurrence")

    today = now.date()
    if duration_minutes:
        length = timedelta(minutes=duration_minutes)
    elif occ.has_schedule:
        length = _scheduled_length(occ)
    else:
        length = timedelta(minutes=settings.SESSION_DEFAULT_MINUTES)

    row = await _schedule_row(db, occ.id, today)
    if row is not None and row.status == "scheduled":
        row.starts_at = now
        if duration_minutes:
            row.ends_at = now + length
        elif row.ends_at is None or row.ends_at <= now:
            row.ends_at = now + length
        session = row
    else:
        times = scheduled_times(occ, today)
        if row is None and times is not None and now < times[1]:
            session = AttendanceSession(
                occurrence_id=occ.id,
                source="schedule",
                class_date=today,
                starts_at=now,
                ends_at=(now + length) if duration_minutes else times[1],
            )
        else:
            session = AttendanceSession(
                occurrence_id=occ.id,
                source="manual",
                class_date=today,
                starts_at=now,
                ends_at=now + length,
            )
        db.add(session)

    session.status = "open"
    session.opened_at = now
    session.lecturer_id = lec.id
    session.camera_id = await camera_id_for_room(db, occ.room)
    session.lecturer_action_at = now
    await db.flush()
    await write_log(db, lec.user_id, "SESSION_START_NOW", "attendance_session", session.id, None, {
        "starts_at": _iso(session.starts_at),
        "ends_at": _iso(session.ends_at),
        "source": session.source,
    })
    await db.flush()
    return session


async def extend(db: AsyncSession, session: AttendanceSession, minutes: int,
                 now: datetime, actor_id: int) -> AttendanceSession:
    """Push the effective end out by `minutes` (FR-315)."""
    if session.status not in ("open", "scheduled"):
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="Session is not open")
    if session.ends_at is None:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT,
                            detail="This session has no end time")

    old = {"ends_at": _iso(session.ends_at)}
    session.ends_at = session.ends_at + timedelta(minutes=minutes)
    if session.status == "open":
        session.lecturer_action_at = now
    await db.flush()
    await write_log(db, actor_id, "SESSION_EXTENDED",
                    "attendance_session", session.id, old, {"ends_at": _iso(session.ends_at)})
    await db.flush()
    return session


async def confirm(db: AsyncSession, session: AttendanceSession, held: bool,
                  now: datetime, actor_id: int) -> AttendanceSession:
    """The lecturer confirms a `needs_confirmation` class was held or not (FR-317)."""
    if session.status != "needs_confirmation":
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT,
                            detail="Session is not waiting for confirmation")

    if held:
        job_closed_at = session.closed_at
        await session_service.close_session(session.id, db, now)
        session.closed_at = job_closed_at  # keep the end the job recorded
        action = "SESSION_CONFIRMED_HELD"
    else:
        session.status = "cancelled"
        action = "SESSION_CONFIRMED_NOT_HELD"

    await db.flush()
    await write_log(db, actor_id, action,
                    "attendance_session", session.id,
                    {"status": "needs_confirmation"}, {"status": session.status})
    await db.flush()
    return session
