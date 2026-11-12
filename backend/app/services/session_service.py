"""
Business logic for opening and closing attendance sessions.
Closing a session auto-marks all enrolled students who have no attendance record as absent.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from datetime import datetime

from app.core.timezone import now_myt
from app.models.session import AttendanceSession
from app.models.attendance import AttendanceRecord
from app.models.class_ import Enrollment
from app.models.face_review import FaceReviewEntry
from app.services import attendance_moodle_sync


async def close_session(session_id: int, db: AsyncSession, now: datetime | None = None) -> AttendanceSession:
    result = await db.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    session = result.scalar_one()

    session.status = "closed"
    session.closed_at = now or now_myt()
    if session.occurrence_id is not None:
        # Queue the Moodle Attendance sync (FR-311); attendance_moodle_sync picks it up
        session.moodle_sync_status = "pending"
        session.moodle_sync_attempts = 0
        session.moodle_sync_next_at = session.closed_at
        session.moodle_sync_error = None
        attendance_moodle_sync.sync_soon(db, session.id)   # sent as soon as this commits (T38b)

    # Find all enrolled students for this occurrence
    enrolled = await db.execute(
        select(Enrollment.student_id).where(Enrollment.occurrence_id == session.occurrence_id)
    )
    enrolled_ids = {row[0] for row in enrolled.all()}

    # Find students already with a record in this session
    recorded = await db.execute(
        select(AttendanceRecord.student_id).where(AttendanceRecord.session_id == session_id)
    )
    recorded_ids = {row[0] for row in recorded.all()}

    # Bulk-insert absent records for students with no record yet
    absent_ids = enrolled_ids - recorded_ids
    for student_id in absent_ids:
        db.add(AttendanceRecord(session_id=session_id, student_id=student_id, status="absent"))

    await db.flush()
    return session


async def get_session_counts(session_id: int, db: AsyncSession) -> dict:
    occ_result = await db.execute(
        select(AttendanceSession.occurrence_id).where(AttendanceSession.id == session_id)
    )
    occurrence_id = occ_result.scalar_one_or_none()

    enrolled = 0
    if occurrence_id:
        enrolled_result = await db.execute(
            select(func.count()).select_from(Enrollment).where(Enrollment.occurrence_id == occurrence_id)
        )
        enrolled = enrolled_result.scalar_one()

    rows = await db.execute(
        select(AttendanceRecord.status, func.count())
        .where(AttendanceRecord.session_id == session_id)
        .group_by(AttendanceRecord.status)
    )
    by_status = dict(rows.all())
    present, late, excused = (by_status.get(s, 0) for s in ("present", "late", "excused"))

    unid_result = await db.execute(
        select(func.count()).select_from(FaceReviewEntry).where(FaceReviewEntry.session_id == session_id)
    )
    recorded = sum(by_status.values())
    return {
        "present": present,
        "late": late,
        "excused": excused,
        # Enrolled students not counted as present/late/excused (including not yet recorded).
        "absent": max(0, enrolled - present - late - excused),
        # Enrolled students with no record yet: only an open session has any (T38b). The lecturer
        # app shows Absent as `absent - not_recorded` and Not yet as this, like the live roster.
        "not_recorded": max(0, enrolled - recorded),
        "unid": unid_result.scalar_one(),
    }
