"""Student "I'm here but wasn't recognised" flags and the unmatched faces kept for them (T43).

FR-318: during an open session, an enrolled student with no record flags once; the lecturer's live
channel is told. FR-319: the lecturer confirms (Present or Late from the flag time, source
`student_flag`, audited, re-sent to Moodle when the session was already synced) or rejects with a
reason; the student sees the result. A flag still pending at close leaves the student Absent and
stays in the lecturer's list.

FR-407: a face a device saw that matched nobody enrolled is kept as evidence, never as a task: the
lecturer sees only the crop closest to a flagging student's own enrolled face, with its similarity.
FR-410 / NFR-02: that crop is deleted when the flag is resolved; every crop of a session goes once
the session is over with no flag pending, and any crop after FACE_UNMATCHED_RETENTION_DAYS.
"""
import asyncio
import logging
from datetime import datetime, timedelta

import numpy as np
from fastapi import HTTPException, status
from sqlalchemy import and_, delete, exists, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, after_commit
from app.core.timezone import now_myt
from app.models.attendance import AttendanceRecord
from app.models.attendance_flag import AttendanceFlag, UnmatchedFace
from app.models.class_ import Enrollment
from app.models.session import AttendanceSession
from app.models.user import Student, User
from app.services import attendance_moodle_sync, attendance_service
from app.services.audit_service import write_log
from app.websocket.manager import manager

logger = logging.getLogger(__name__)


def clock() -> datetime:
    """Current naive MYT time. Tests monkeypatch this (controlled clock)."""
    return now_myt()


# ── Unmatched faces (FR-407) ─────────────────────────────────────────────────

_NEAREST_IN_SESSION = text(
    "SELECT id, (1 - (embedding <=> CAST(:vec AS vector))) AS similarity "
    "FROM unmatched_faces WHERE session_id = :sid "
    "ORDER BY embedding <=> CAST(:vec AS vector) LIMIT 1"
)


async def store_unmatched(db: AsyncSession, session_id: int, camera_id: int | None, embedding: np.ndarray,
                          image: bytes, similarity: float | None, now: datetime) -> bool:
    """Keep a crop that matched no enrolled student. Returns True when a new crop was stored.

    A person standing at the door is seen in many frames, so a crop within FACE_UNMATCHED_SAME_PERSON
    of one already kept for this session only refreshes that one's `last_seen_at`. At most
    FACE_UNMATCHED_MAX_PER_SESSION crops are kept per session.
    """
    vec = str([float(x) for x in embedding])
    nearest = (await db.execute(_NEAREST_IN_SESSION, {"vec": vec, "sid": session_id})).fetchone()
    if nearest is not None and float(nearest.similarity) >= settings.FACE_UNMATCHED_SAME_PERSON:
        kept = await db.get(UnmatchedFace, nearest.id)
        kept.last_seen_at = now
        return False

    count = await db.scalar(select(func.count()).select_from(UnmatchedFace)
                            .where(UnmatchedFace.session_id == session_id))
    if count >= settings.FACE_UNMATCHED_MAX_PER_SESSION:
        return False

    db.add(UnmatchedFace(session_id=session_id, camera_id=camera_id, embedding=[float(x) for x in embedding],
                         image=image, similarity=similarity, captured_at=now, last_seen_at=now))
    return True


_CLOSEST_TO_STUDENT = text(
    "SELECT uf.id, (1 - (uf.embedding <=> fe.embedding)) AS similarity "
    "FROM unmatched_faces uf "
    "JOIN face_embeddings fe ON fe.student_id = :student_id "
    "WHERE uf.session_id = :sid "
    "ORDER BY uf.embedding <=> fe.embedding LIMIT 1"
)


async def closest_crop(db: AsyncSession, session_id: int, student_id: int) -> tuple[int, float] | None:
    """(crop id, similarity) of the session's unmatched crop closest to the student's enrolled face.

    None when the session kept no crop or the student has no enrolled face.
    """
    row = (await db.execute(_CLOSEST_TO_STUDENT, {"sid": session_id, "student_id": student_id})).fetchone()
    return (row.id, float(row.similarity)) if row is not None else None


async def purge_unmatched(db: AsyncSession, now: datetime | None = None) -> int:
    """Delete crops past the retention period, and every crop of a session that is no longer open
    and has no flag pending (NFR-02). Returns how many were deleted. The caller commits."""
    now = now or clock()
    cutoff = now - timedelta(days=settings.FACE_UNMATCHED_RETENTION_DAYS)
    session_over = and_(
        exists().where(AttendanceSession.id == UnmatchedFace.session_id, AttendanceSession.status != "open"),
        ~exists().where(AttendanceFlag.session_id == UnmatchedFace.session_id, AttendanceFlag.status == "pending"),
    )
    result = await db.execute(delete(UnmatchedFace).where(or_(UnmatchedFace.captured_at < cutoff, session_over)))
    return result.rowcount or 0


async def unmatched_face_cleanup_loop() -> None:
    """Background task started in main.py; FACE_UNMATCHED_CLEANUP_INTERVAL_SECONDS <= 0 disables it."""
    if settings.FACE_UNMATCHED_CLEANUP_INTERVAL_SECONDS <= 0:
        return
    while True:
        try:
            async with AsyncSessionLocal() as db:
                deleted = await purge_unmatched(db)
                await db.commit()
            if deleted:
                logger.info("Deleted %d unmatched face crop(s)", deleted)
        except asyncio.CancelledError:
            raise
        except Exception:   # never let the job die on a transient error
            logger.exception("Unmatched face cleanup failed")
        await asyncio.sleep(settings.FACE_UNMATCHED_CLEANUP_INTERVAL_SECONDS)


# ── Flags (FR-318, FR-319) ───────────────────────────────────────────────────

def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def create_flag(db: AsyncSession, student: Student, session_id: int) -> AttendanceFlag:
    """The student flags that they are in class but weren't recognised (FR-318)."""
    session = await db.get(AttendanceSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    enrolled = await db.scalar(select(Enrollment.id).where(
        Enrollment.occurrence_id == session.occurrence_id, Enrollment.student_id == student.id))
    if session.occurrence_id is None or enrolled is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this class")
    if session.status != "open":
        raise _conflict("You can only flag while the session is open")
    record = await db.scalar(select(AttendanceRecord).where(
        AttendanceRecord.session_id == session_id, AttendanceRecord.student_id == student.id))
    if record is not None:
        raise _conflict(f"Your attendance is already recorded ({record.status})")
    if await db.scalar(select(AttendanceFlag.id).where(
            AttendanceFlag.session_id == session_id, AttendanceFlag.student_id == student.id)) is not None:
        raise _conflict("You have already flagged this session")

    flag = AttendanceFlag(session_id=session_id, student_id=student.id, flagged_at=clock(), status="pending")
    try:
        async with db.begin_nested():   # a double tap racing this one hits the unique constraint
            db.add(flag)
    except IntegrityError:
        raise _conflict("You have already flagged this session") from None
    return flag


async def _delete_evidence(db: AsyncSession, session: AttendanceSession, crop_id: int | None) -> None:
    """The crop shown with a resolved flag goes at once (FR-410); a session that is over with no
    flag left pending loses all its crops."""
    if crop_id is not None:
        await db.execute(delete(UnmatchedFace).where(UnmatchedFace.id == crop_id))
    if session.status != "open":
        pending = await db.scalar(select(AttendanceFlag.id).where(
            AttendanceFlag.session_id == session.id, AttendanceFlag.status == "pending").limit(1))
        if pending is None:
            await db.execute(delete(UnmatchedFace).where(UnmatchedFace.session_id == session.id))


def _absent_from_close(record: AttendanceRecord) -> bool:
    """The Absent that closing a session writes for everyone unrecorded (no detection, no override)."""
    return (record.status == "absent" and record.detected_at is None and record.override_by is None
            and record.source is None)


async def confirm_flag(db: AsyncSession, flag: AttendanceFlag, session: AttendanceSession,
                       actor: User) -> AttendanceRecord:
    """Record Present or Late from the flag time, source `student_flag` (FR-319). The caller checks access."""
    if flag.status != "pending":
        raise _conflict(f"This flag is already {flag.status}")
    record = await db.scalar(select(AttendanceRecord).where(
        AttendanceRecord.session_id == flag.session_id, AttendanceRecord.student_id == flag.student_id))
    if record is not None and not _absent_from_close(record):
        # recognised or overridden since; never changed here (NFR-22)
        raise _conflict(f"The student already has a record ({record.status}); reject the flag or use override")

    now = clock()
    crop = await closest_crop(db, flag.session_id, flag.student_id)
    old_status = record.status if record is not None else "not_recorded"
    if record is None:
        record = AttendanceRecord(session_id=flag.session_id, student_id=flag.student_id)
        db.add(record)
    record.status = attendance_service.status_for_recognition(session, flag.flagged_at)
    record.detected_at = flag.flagged_at
    record.override_by = actor.id
    record.override_at = now
    record.source = "student_flag"
    flag.status = "confirmed"
    flag.record_status = record.status
    flag.resolved_by = actor.id
    flag.resolved_at = now
    await db.flush()

    await write_log(db, actor.id, "ATTENDANCE_FLAG_CONFIRM", "attendance_flag", flag.id,
                    old_val={"status": old_status},
                    new_val={"status": record.status, "record_id": record.id, "student_id": flag.student_id})
    attendance_moodle_sync.queue_resync(session, now)   # FR-312: a synced session is sent again
    await _delete_evidence(db, session, crop[0] if crop else None)
    await db.flush()
    if session.moodle_sync_status == "pending":
        attendance_moodle_sync.sync_soon(db, session.id)
    return record


async def reject_flag(db: AsyncSession, flag: AttendanceFlag, session: AttendanceSession,
                      actor: User, reason: str) -> None:
    """Reject with a reason the student sees (FR-319). The caller checks access."""
    if flag.status != "pending":
        raise _conflict(f"This flag is already {flag.status}")
    crop = await closest_crop(db, flag.session_id, flag.student_id)
    flag.status = "rejected"
    flag.reject_reason = reason
    flag.resolved_by = actor.id
    flag.resolved_at = clock()
    await write_log(db, actor.id, "ATTENDANCE_FLAG_REJECT", "attendance_flag", flag.id,
                    new_val={"reason": reason, "student_id": flag.student_id})
    await _delete_evidence(db, session, crop[0] if crop else None)
    await db.flush()


def announce(db: AsyncSession, session_id: int, event: str, flag: dict,
             student_user_id: int | None = None) -> None:
    """Tell the session's lecturer screens and, if given, the student's own channel once `db`
    commits (`attendance_flagged` / `attendance_flag_resolved`)."""
    payload = {"event": event, "session_id": session_id, "flag": flag}

    async def _broadcast() -> None:
        await manager.broadcast(session_id, payload)
        if student_user_id is not None:
            await manager.send_to_user(student_user_id, payload)

    after_commit(db, _broadcast)
