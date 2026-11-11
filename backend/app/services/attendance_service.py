"""
Writes attendance records and broadcasts WebSocket events.
"""
import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.timezone import now_myt
from app.models.attendance import AttendanceRecord
from app.models.class_ import Enrollment
from app.models.session import AttendanceSession
from app.services.session_service import get_session_counts
from app.websocket.manager import manager

_alerted_sessions: set[int] = set()


def status_for_recognition(session: AttendanceSession, detected_at: datetime) -> str:
    """FR-302: Present, or Late when the first recognition is more than
    ATTENDANCE_LATE_AFTER_MINUTES after the session's effective start."""
    start = session.starts_at or session.opened_at
    if start is None:
        return "present"
    late_after = start + timedelta(minutes=settings.ATTENDANCE_LATE_AFTER_MINUTES)
    return "late" if detected_at > late_after else "present"


async def mark_present(
    session_id: int,
    student_id: int,
    db: AsyncSession,
    now: datetime | None = None,
) -> tuple[AttendanceRecord, bool]:
    """
    Insert a 'present' or 'late' record for the student (FR-302).
    Returns (record, was_new) — was_new=False means the student was already recorded.
    Only the first recognition counts: an existing record is never changed.
    """
    existing = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == student_id,
        )
    )
    record = existing.scalar_one_or_none()

    if record:
        return record, False

    now = now or now_myt()
    session = await db.get(AttendanceSession, session_id)
    status = status_for_recognition(session, now) if session else "present"
    record = AttendanceRecord(
        session_id=session_id,
        student_id=student_id,
        status=status,
        detected_at=now,
    )
    db.add(record)
    await db.flush()
    return record, True


async def check_low_attendance_alert(session_id: int, present: int, db: AsyncSession) -> None:
    if session_id in _alerted_sessions:
        return

    result = await db.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session or not session.occurrence_id:
        return

    # Count from the class's effective start, like the Late rule: scheduled sessions open
    # SESSION_EARLY_OPEN_MINUTES early, and an alert then would fire before anyone arrives.
    start = session.starts_at or session.opened_at
    if start is None:
        return
    elapsed_minutes = (now_myt() - start).total_seconds() / 60
    if elapsed_minutes < 1:
        return

    enrolled_result = await db.execute(
        select(func.count()).select_from(Enrollment).where(Enrollment.occurrence_id == session.occurrence_id)
    )
    enrolled = enrolled_result.scalar_one()
    if enrolled == 0:
        return

    if present / enrolled < 0.70:
        await manager.broadcast(session_id, {
            "event": "attendance_alert",
            "type": "low_attendance",
            "present": present,
            "enrolled": enrolled,
            "rate": round(present / enrolled, 2),
        })
        _alerted_sessions.add(session_id)


async def broadcast_attendance_update(
    session_id: int,
    record: AttendanceRecord,
    student_name: str,
    matric_no: str,
    db: AsyncSession,
) -> None:
    counts = await get_session_counts(session_id, db)
    await manager.broadcast(session_id, {
        "event": "attendance_update",
        "session_id": session_id,
        "counts": counts,
        "student": {
            "id": record.student_id,
            "name": student_name,
            "matric_no": matric_no,
            "status": record.status,
            "detected_at": record.detected_at.isoformat() if record.detected_at else None,
            "record_id": record.id,
        },
    })
    # The alert payload key "present" now means attended (Present + Late).
    await check_low_attendance_alert(session_id, counts["present"] + counts["late"], db)


async def sweep_low_attendance_alerts(db: AsyncSession) -> None:
    """
    Check every currently-open session for low attendance. Runs on a timer so the
    alert fires even when no new faces are being detected (the typical low-turnout case).
    """
    result = await db.execute(
        select(AttendanceSession).where(AttendanceSession.status == "open")
    )
    for session in result.scalars().all():
        if session.id in _alerted_sessions:
            continue
        counts = await get_session_counts(session.id, db)
        # The alert payload key "present" now means attended (Present + Late).
        await check_low_attendance_alert(session.id, counts["present"] + counts["late"], db)


async def low_attendance_monitor(interval_seconds: int = 30) -> None:
    """Background loop: periodically sweep open sessions for low attendance."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with AsyncSessionLocal() as db:
                await sweep_low_attendance_alerts(db)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # never let the monitor die on a transient error
            print(f"low_attendance_monitor error: {e}")
