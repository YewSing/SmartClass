"""Closed sessions -> Moodle Attendance (`mod_attendance`) (FR-311, NFR-20, NFR-22).

Rules:
- Closing a session (session_service.close_session) queues it: `moodle_sync_status = "pending"`.
  The background loop sends every `pending`/`failed` session whose `moodle_sync_next_at` has come.
- The Moodle course is `Course.moodle_course_id`, else the course with shortname == code (the id
  is then stored). Its Attendance activity is the first `attendance` module in the course.
- The Moodle session is the stored `moodle_session_id`; else one in the activity whose
  description is this session's marker and whose start time matches (a crash between creating it
  and committing the id must not make a second one); else a new one is created.
- Each student's status maps one-to-one to the session status set's acronym (P/L/E/A). Only a
  record whose status differs from `moodle_status_sent` is sent, and `moodle_status_sent` is
  stored after each successful call, so running a sync twice sends nothing the second time.
- Students without a Moodle account (`users.moodle_user_id`) can't be sent; they are skipped
  and counted in `moodle_sync_error` on the synced session.
- Any failure makes the session `failed`, keeps what was already sent, and schedules the next try
  after RETRY_BASE * 2^(attempts-1) seconds, capped at RETRY_MAX. Retries never stop (NFR-20).
"""
import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.timezone import MYT, now_myt
from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Course
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.services.kb.moodle_client import MoodleClient, MoodleError

log = logging.getLogger(__name__)

# SmartClass status -> mod_attendance status acronym (the plugin's default status set)
STATUS_ACRONYMS = {"present": "P", "late": "L", "excused": "E", "absent": "A"}
DUE_STATUSES = ("pending", "failed")

_run_lock = asyncio.Lock()


class SyncError(Exception):
    """A sync problem worth showing the lecturer (no secrets in the message)."""


def clock() -> datetime:
    """Current naive MYT time. Tests monkeypatch this (controlled clock)."""
    return now_myt()


def retry_delay(attempts: int) -> timedelta:
    """Wait before try number `attempts + 1`, after `attempts` failures in a row (attempts >= 1)."""
    seconds = settings.MOODLE_ATTENDANCE_RETRY_BASE_SECONDS * 2 ** max(0, attempts - 1)
    return timedelta(seconds=min(seconds, settings.MOODLE_ATTENDANCE_RETRY_MAX_SECONDS))


def moodle_timestamp(value: datetime) -> int:
    """Naive MYT datetime -> Unix time."""
    return int(value.replace(tzinfo=MYT).timestamp())


def session_marker(session: AttendanceSession, course: Course) -> str:
    """The Moodle session description; also how a lost `moodle_session_id` is found again."""
    return f"SmartClass {course.code} session #{session.id}"


def _error_text(exc: Exception) -> str:
    # httpx errors can carry request details; only the class name is kept (NFR-08)
    if isinstance(exc, (SyncError, MoodleError)):
        return str(exc)[:255]
    return exc.__class__.__name__


async def _moodle_course_id(db: AsyncSession, client: MoodleClient, course: Course) -> int:
    if course.moodle_course_id is None:
        course_id = await client.get_course_id(course.code)
        if course_id is None:
            raise SyncError(f"Course {course.code} is not in Moodle")
        course.moodle_course_id = course_id
        await db.flush()
    return course.moodle_course_id


async def _attendance_id(client: MoodleClient, course_id: int, code: str) -> int:
    sections = await client.call("core_course_get_contents", courseid=course_id)
    for section in sections:
        for module in section.get("modules", []):
            if module.get("modname") == "attendance":
                return int(module["instance"])
    raise SyncError(f"Moodle course {code} has no Attendance activity")


async def _find_or_create_moodle_session(client: MoodleClient, session: AttendanceSession, course: Course,
                                         attendance_id: int) -> dict:
    """The Moodle session record (get_session shape) for `session`; stores its id on `session`."""
    if session.moodle_session_id is not None:
        try:
            found = await client.call("mod_attendance_get_session", sessionid=session.moodle_session_id)
            if int(found.get("attendanceid", 0)) == attendance_id:
                return found
        except MoodleError as exc:
            if "invalidrecord" not in str(exc):
                raise
        session.moodle_session_id = None   # deleted in Moodle or moved: find or create it again

    start = session.starts_at or session.opened_at or session.closed_at
    end = session.ends_at or session.closed_at or start
    sessiontime = moodle_timestamp(start)
    marker = session_marker(session, course)

    for found in await client.call("mod_attendance_get_sessions", attendanceid=attendance_id):
        if found.get("description") == marker and int(found.get("sessdate", 0)) == sessiontime:
            session.moodle_session_id = int(found["id"])
            return found

    added = await client.call("mod_attendance_add_session", attendanceid=attendance_id, description=marker,
                              sessiontime=sessiontime, duration=max(0, int((end - start).total_seconds())),
                              addcalendarevent=0)
    session.moodle_session_id = int(added["sessionid"])
    return await client.call("mod_attendance_get_session", sessionid=session.moodle_session_id)


def _status_ids(moodle_session: dict) -> dict[str, int]:
    """SmartClass status -> Moodle status id, from the session's own status set."""
    statusset = int(moodle_session.get("statusset") or 0)
    by_acronym = {s["acronym"]: int(s["id"]) for s in moodle_session.get("statuses", [])
                  if not int(s.get("deleted") or 0) and int(s.get("setnumber") or 0) == statusset}
    missing = [a for a in STATUS_ACRONYMS.values() if a not in by_acronym]
    if missing:
        raise SyncError(f"Moodle Attendance has no status {', '.join(missing)}")
    return {status: by_acronym[acronym] for status, acronym in STATUS_ACRONYMS.items()}


async def _taken_by(db: AsyncSession, client: MoodleClient, session: AttendanceSession) -> int:
    """The lecturer's Moodle user id, else the service account's."""
    moodle_id = await db.scalar(
        select(User.moodle_user_id).join(Lecturer, Lecturer.user_id == User.id)
        .where(Lecturer.id == session.lecturer_id)
    )
    if moodle_id:
        return int(moodle_id)
    info = await client.call("core_webservice_get_site_info")
    return int(info["userid"])


async def _send(db: AsyncSession, client: MoodleClient, session: AttendanceSession) -> int:
    """Push the session's records. Returns how many students were skipped (no Moodle account)."""
    occ = await db.get(ClassOccurrence, session.occurrence_id)
    course = await db.get(Course, occ.course_id)
    course_id = await _moodle_course_id(db, client, course)
    attendance_id = await _attendance_id(client, course_id, course.code)
    moodle_session = await _find_or_create_moodle_session(client, session, course, attendance_id)
    await db.flush()   # keep the Moodle session id even if a later call fails
    status_ids = _status_ids(moodle_session)
    statusset = int(moodle_session.get("statusset") or 0)

    rows = (await db.execute(
        select(AttendanceRecord, User.moodle_user_id)
        .join(Student, Student.id == AttendanceRecord.student_id)
        .join(User, User.id == Student.user_id)
        .where(AttendanceRecord.session_id == session.id)
        .order_by(AttendanceRecord.id)
    )).all()
    skipped = sum(1 for _, moodle_id in rows if moodle_id is None)
    to_send = [(rec, moodle_id) for rec, moodle_id in rows
               if moodle_id is not None and rec.moodle_status_sent != rec.status]
    if not to_send:
        return skipped

    taken_by = await _taken_by(db, client, session)
    for rec, moodle_id in to_send:
        await client.call("mod_attendance_update_user_status", sessionid=session.moodle_session_id,
                          studentid=moodle_id, takenbyid=taken_by, statusid=status_ids[rec.status],
                          statusset=statusset)
        rec.moodle_status_sent = rec.status
        await db.flush()
    return skipped


async def sync_session(db: AsyncSession, session_id: int, client: MoodleClient,
                       now: datetime | None = None) -> str:
    """Sync one session and record the outcome on it. Flushes, does not commit.
    Returns the new sync status ("synced" or "failed")."""
    now = now or clock()
    session = await db.get(AttendanceSession, session_id)
    try:
        if session.status != "closed" or session.occurrence_id is None:
            raise SyncError("Only a closed class session can be sent to Moodle")
        skipped = await _send(db, client, session)
    except (SyncError, MoodleError, httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        session.moodle_sync_attempts += 1
        session.moodle_sync_status = "failed"
        session.moodle_sync_error = _error_text(exc)
        session.moodle_sync_next_at = now + retry_delay(session.moodle_sync_attempts)
        await db.flush()
        log.warning("Moodle attendance sync of session %s failed (attempt %s): %s",
                    session_id, session.moodle_sync_attempts, session.moodle_sync_error)
        return "failed"

    session.moodle_sync_status = "synced"
    session.moodle_synced_at = now
    session.moodle_sync_attempts = 0
    session.moodle_sync_next_at = None
    session.moodle_sync_error = (f"{skipped} student(s) have no Moodle account and were not sent"
                                 if skipped else None)
    await db.flush()
    return "synced"


async def due_session_ids(db: AsyncSession, now: datetime) -> list[int]:
    return list((await db.execute(
        select(AttendanceSession.id)
        .where(AttendanceSession.moodle_sync_status.in_(DUE_STATUSES),
               AttendanceSession.moodle_sync_next_at.is_not(None),
               AttendanceSession.moodle_sync_next_at <= now)
        .order_by(AttendanceSession.moodle_sync_next_at, AttendanceSession.id)
    )).scalars())


async def run_due(client: MoodleClient | None = None, now: datetime | None = None) -> dict[int, str]:
    """Sync every due session, each in its own transaction. Returns session id -> outcome."""
    now = now or clock()
    async with _run_lock:
        async with AsyncSessionLocal() as db:
            ids = await due_session_ids(db, now)
        if not ids:
            return {}
        if client is None:
            async with MoodleClient(timeout=30.0) as own:
                return await _run_ids(own, ids, now)
        return await _run_ids(client, ids, now)


async def _run_ids(client: MoodleClient, ids: list[int], now: datetime) -> dict[int, str]:
    results = {}
    for session_id in ids:
        async with AsyncSessionLocal() as db:
            try:
                results[session_id] = await sync_session(db, session_id, client, now)
                await db.commit()
            except Exception:
                await db.rollback()
                raise
    return results


async def attendance_moodle_sync_loop() -> None:
    """Background task started in main.py; disabled without a Moodle token."""
    if not settings.MOODLE_TOKEN or settings.MOODLE_ATTENDANCE_SYNC_INTERVAL_SECONDS <= 0:
        return
    while True:
        try:
            results = await run_due()
            if results:
                log.info("Moodle attendance sync: %s", results)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Moodle attendance sync loop failed: %s", exc.__class__.__name__)
        await asyncio.sleep(settings.MOODLE_ATTENDANCE_SYNC_INTERVAL_SECONDS)
