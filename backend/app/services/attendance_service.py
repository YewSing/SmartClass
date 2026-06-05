"""
Writes attendance records and broadcasts WebSocket events.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.timezone import now_myt
from app.models.attendance import AttendanceRecord
from app.models.user import Student, User
from app.services.session_service import get_session_counts
from app.websocket.manager import manager


async def mark_present(
    session_id: int,
    student_id: int,
    db: AsyncSession,
) -> tuple[AttendanceRecord, bool]:
    """
    Insert a 'present' record for the student.
    Returns (record, was_new) — was_new=False means the student was already present.
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

    record = AttendanceRecord(
        session_id=session_id,
        student_id=student_id,
        status="present",
        detected_at=now_myt(),
    )
    db.add(record)
    await db.flush()
    return record, True


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
