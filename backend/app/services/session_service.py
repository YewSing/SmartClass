"""
Business logic for opening and closing attendance sessions.
Closing a session auto-marks all enrolled students who have no attendance record as absent.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.timezone import now_myt
from app.models.session import AttendanceSession
from app.models.attendance import AttendanceRecord
from app.models.class_ import Enrollment
from app.models.face_review import FaceReviewEntry


async def close_session(session_id: int, db: AsyncSession) -> AttendanceSession:
    result = await db.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    session = result.scalar_one()

    session.status = "closed"
    session.closed_at = now_myt()

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

    present_result = await db.execute(
        select(func.count()).select_from(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.status == "present",
        )
    )
    present = present_result.scalar_one()

    unid_result = await db.execute(
        select(func.count()).select_from(FaceReviewEntry).where(FaceReviewEntry.session_id == session_id)
    )
    return {
        "present": present,
        "absent": max(0, enrolled - present),
        "unid": unid_result.scalar_one(),
    }
