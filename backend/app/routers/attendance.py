import csv
import io

from app.core.timezone import now_myt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_role, get_current_user
from app.models.user import User, Student, Lecturer
from app.models.class_ import Enrollment, ClassOccurrence
from app.models.session import AttendanceSession
from app.models.attendance import AttendanceRecord
from app.schemas.session import AttendanceStudentOut, OverrideRequest
from app.services.audit_service import write_log
from app.services.session_service import get_session_counts
from app.websocket.manager import manager

router = APIRouter(tags=["attendance"])

_lecturer_or_admin = require_role("lecturer", "admin")


@router.get("/lecturer/sessions/{session_id}/attendance", response_model=list[AttendanceStudentOut])
async def get_session_attendance(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    """Full student roster for a session with their current attendance status."""
    session_result = await db.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # All enrolled students in this class
    enrolled = await db.execute(
        select(Student)
        .options(selectinload(Student.user))
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.occurrence_id == session.occurrence_id)
        .order_by(Student.matric_no)
    )
    students = enrolled.scalars().all()

    # Existing attendance records for this session
    records_result = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
    )
    records_by_student: dict[int, AttendanceRecord] = {r.student_id: r for r in records_result.scalars().all()}

    out = []
    for stu in students:
        rec = records_by_student.get(stu.id)
        out.append(AttendanceStudentOut(
            record_id=rec.id if rec else None,
            student_id=stu.id,
            matric_no=stu.matric_no,
            name=stu.user.name,
            status=rec.status if rec else "not_recorded",
            detected_at=rec.detected_at if rec else None,
            overridden=bool(rec and rec.override_by),
        ))
    return out


@router.put("/attendance/{record_id}/override", response_model=AttendanceStudentOut)
async def override_attendance(
    record_id: int,
    body: OverrideRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    if body.status not in ("present", "absent"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status must be 'present' or 'absent'")

    result = await db.execute(
        select(AttendanceRecord)
        .options(selectinload(AttendanceRecord.student).selectinload(Student.user))
        .where(AttendanceRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")

    old_status = record.status

    # Audit log and status update in same flush — rolled back together on error (NFR-05)
    await write_log(
        db, actor.id, "ATTENDANCE_OVERRIDE", "attendance_record", record_id,
        old_val={"status": old_status}, new_val={"status": body.status},
    )
    record.status = body.status
    record.override_by = actor.id
    record.override_at = now_myt()
    await db.flush()

    counts = await get_session_counts(record.session_id, db)
    await manager.broadcast(record.session_id, {
        "event": "attendance_override",
        "session_id": record.session_id,
        "counts": counts,
        "student": {
            "id": record.student_id,
            "name": record.student.user.name,
            "matric_no": record.student.matric_no,
            "status": record.status,
            "record_id": record.id,
        },
    })

    return AttendanceStudentOut(
        record_id=record.id,
        student_id=record.student_id,
        matric_no=record.student.matric_no,
        name=record.student.user.name,
        status=record.status,
        detected_at=record.detected_at,
        overridden=True,
    )


@router.get("/lecturer/sessions/{session_id}/export")
async def export_session(
    session_id: int,
    format: str = Query("csv", pattern="^(csv)$"),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    session_result = await db.execute(
        select(AttendanceSession)
        .options(selectinload(AttendanceSession.occurrence).selectinload(ClassOccurrence.course))
        .where(AttendanceSession.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    enrolled = await db.execute(
        select(Student)
        .options(selectinload(Student.user))
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.occurrence_id == session.occurrence_id)
        .order_by(Student.matric_no)
    )
    students = enrolled.scalars().all()

    records_result = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
    )
    records_by_student: dict[int, AttendanceRecord] = {r.student_id: r for r in records_result.scalars().all()}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Matric No", "Name", "Status", "Detected At", "Overridden"])

    for stu in students:
        rec = records_by_student.get(stu.id)
        writer.writerow([
            stu.matric_no,
            stu.user.name,
            rec.status if rec else "absent",
            rec.detected_at.isoformat() if rec and rec.detected_at else "",
            "Yes" if rec and rec.override_by else "No",
        ])

    filename = f"attendance_{session.occurrence.course.code}_{session.opened_at.strftime('%Y%m%d')}.csv"
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
