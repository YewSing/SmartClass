import csv
import io
from datetime import date

from app.core.timezone import now_myt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import after_commit, get_db
from app.core.deps import ensure_teaches_occurrence, require_role
from app.models.user import User, Student
from app.models.class_ import Enrollment, ClassOccurrence
from app.models.session import AttendanceSession
from app.models.attendance import AttendanceRecord, ATTENDANCE_STATUSES
from app.schemas.session import AttendanceStudentOut, OverrideRequest, SessionOverrideRequest
from app.services import attendance_moodle_sync
from app.services.attendance_stats import class_report, resolve_date_range, session_date, session_label
from app.services.audit_service import write_log
from app.services.session_service import get_session_counts
from app.websocket.manager import manager

router = APIRouter(tags=["attendance"])

_lecturer = require_role("lecturer")

_LETTER = {"present": "P", "late": "L", "excused": "E", "absent": "A"}


async def _get_taught_session(db: AsyncSession, actor: User, session_id: int) -> AttendanceSession:
    """The session, or 404 if unknown and 403 if the actor doesn't teach its class."""
    session = await db.scalar(
        select(AttendanceSession)
        .options(selectinload(AttendanceSession.occurrence).selectinload(ClassOccurrence.course))
        .where(AttendanceSession.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await ensure_teaches_occurrence(db, actor, session.occurrence_id)
    return session


@router.get("/lecturer/sessions/{session_id}/attendance", response_model=list[AttendanceStudentOut])
async def get_session_attendance(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Full student roster for a session with their current attendance status."""
    session = await _get_taught_session(db, actor, session_id)

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


def _announce_override(db: AsyncSession, session_id: int, counts: dict, student: dict,
                       session: AttendanceSession) -> None:
    """After the override commits: tell the session's screens, and re-send a closed session to
    Moodle at once (FR-312, T38b)."""
    payload = {"event": "attendance_override", "session_id": session_id, "counts": counts, "student": student}
    if session.moodle_sync_status is not None:
        payload["moodle_sync_status"] = session.moodle_sync_status

    async def _broadcast() -> None:
        await manager.broadcast(session_id, payload)

    after_commit(db, _broadcast)
    if session.moodle_sync_status == "pending":
        attendance_moodle_sync.sync_soon(db, session_id)


@router.put("/attendance/{record_id}/override", response_model=AttendanceStudentOut)
async def override_attendance(
    record_id: int,
    body: OverrideRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Override one record's status. An optional reason (FR-305) is audited."""
    if body.status not in ATTENDANCE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Status must be one of: present, late, excused, absent")

    result = await db.execute(
        select(AttendanceRecord)
        .options(selectinload(AttendanceRecord.student).selectinload(Student.user))
        .where(AttendanceRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")
    session = await _get_taught_session(db, actor, record.session_id)

    old_status = record.status

    # Audit log and status update in same flush — rolled back together on error (NFR-05)
    await write_log(
        db, actor.id, "ATTENDANCE_OVERRIDE", "attendance_record", record_id,
        old_val={"status": old_status}, new_val={"status": body.status, "reason": body.reason},
    )
    record.status = body.status
    record.override_by = actor.id
    record.override_at = now_myt()
    attendance_moodle_sync.queue_resync(session, record.override_at)  # FR-312
    await db.flush()

    counts = await get_session_counts(record.session_id, db)
    _announce_override(db, record.session_id, counts, {
        "id": record.student_id,
        "name": record.student.user.name,
        "matric_no": record.student.matric_no,
        "status": record.status,
        "record_id": record.id,
    }, session)

    return AttendanceStudentOut(
        record_id=record.id,
        student_id=record.student_id,
        matric_no=record.student.matric_no,
        name=record.student.user.name,
        status=record.status,
        detected_at=record.detected_at,
        overridden=True,
    )


@router.put("/lecturer/sessions/{session_id}/attendance/override", response_model=AttendanceStudentOut)
async def override_session_attendance(
    session_id: int,
    body: SessionOverrideRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Create-or-update an attendance record for a student who has no existing record (not_recorded → any of the four statuses).

    An optional reason (FR-305) is audited.
    """
    if body.status not in ATTENDANCE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Status must be one of: present, late, excused, absent")
    session = await _get_taught_session(db, actor, session_id)

    student_result = await db.execute(
        select(Student)
        .options(selectinload(Student.user))
        .where(Student.id == body.student_id)
    )
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    rec_result = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.session_id == session_id, AttendanceRecord.student_id == body.student_id)
    )
    record = rec_result.scalar_one_or_none()

    now = now_myt()
    if record:
        old_status = record.status
        record.status = body.status
        record.override_by = actor.id
        record.override_at = now
        await db.flush()
    else:
        record = AttendanceRecord(
            session_id=session_id,
            student_id=body.student_id,
            status=body.status,
            override_by=actor.id,
            override_at=now,
        )
        db.add(record)
        await db.flush()  # assigns record.id
        old_status = "not_recorded"

    await write_log(db, actor.id, "ATTENDANCE_OVERRIDE", "attendance_record", record.id,
        old_val={"status": old_status}, new_val={"status": body.status, "reason": body.reason})
    attendance_moodle_sync.queue_resync(session, now)  # FR-312
    await db.flush()

    counts = await get_session_counts(session_id, db)
    _announce_override(db, session_id, counts, {
        "id": record.student_id,
        "name": student.user.name,
        "matric_no": student.matric_no,
        "status": record.status,
        "record_id": record.id,
    }, session)

    return AttendanceStudentOut(
        record_id=record.id,
        student_id=record.student_id,
        matric_no=student.matric_no,
        name=student.user.name,
        status=record.status,
        overridden=True,
    )


@router.get("/lecturer/sessions/{session_id}/export")
async def export_session(
    session_id: int,
    format: str = Query("csv", pattern="^(csv)$"),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    session = await _get_taught_session(db, actor, session_id)

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
            rec.status if rec else ("absent" if session.status == "closed" else "not_recorded"),
            rec.detected_at.isoformat() if rec and rec.detected_at else "",
            "Yes" if rec and rec.override_by else "No",
        ])

    d = session_date(session) or now_myt().date()
    filename = f"attendance_{session.occurrence.course.code}_{d.strftime('%Y%m%d')}.csv"
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/lecturer/occurrences/{occ_id}/attendance/export")
async def export_occurrence(
    occ_id: int,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    from_date: date | None = Query(None),   # older name, used by the lecturer app's Analytics screen
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    occ_result = await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .where(ClassOccurrence.id == occ_id)
    )
    occ = occ_result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Occurrence not found")
    await ensure_teaches_occurrence(db, actor, occ_id)

    try:
        start, end = resolve_date_range(from_, to, from_date, to_date)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    sessions, rows = await class_report(db, occ_id, start, end)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Matric No", "Name"]
        + [session_label(s) for s in sessions]
        + ["Present", "Late", "Excused", "Absent", "Total", "Rate"]
    )

    for row in rows:
        counts = row["counts"]
        writer.writerow([
            row["matric_no"],
            row["name"],
            *[_LETTER[x] for x in row["statuses"]],
            counts.present,
            counts.late,
            counts.excused,
            counts.absent,
            f"{counts.attended}/{counts.counted_sessions}",
            f"{counts.rate}%" if counts.rate is not None else "",
        ])

    today = now_myt().date()
    first_day = session_date(sessions[0]) if sessions else None
    last_day = session_date(sessions[-1]) if sessions else None
    start_day = start or first_day or today
    end_day = end or last_day or today
    filename = (
        f"attendance_report_{occ.course.code}_{start_day:%Y%m%d}_{end_day:%Y%m%d}.csv"
    )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
