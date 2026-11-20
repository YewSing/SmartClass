"""Student "I'm here but wasn't recognised" flags (FR-318, FR-319, FR-407, FR-410, NFR-02).

Students flag from the app; the lecturer who teaches the class confirms or rejects, with an admin
as the fallback. The only face a lecturer ever sees here is the unmatched crop closest to the
flagging student's own enrolled face: no screen asks them to identify an unclaimed face.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import Select, case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import ensure_teaches_occurrence, require_role
from app.models.attendance import AttendanceRecord
from app.models.attendance_flag import FLAG_STATUSES, AttendanceFlag, UnmatchedFace
from app.models.class_ import ClassOccurrence, Course
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.schemas.attendance_flag import ClosestCropOut, FlagOut, RejectFlagRequest, StudentFlagOut
from app.services import attendance_flags, attendance_service

router = APIRouter(tags=["attendance-flags"])

_student = require_role("student")
_lecturer_or_admin = require_role("lecturer", "admin")   # admin = fallback (T43)


def _class_name(course: Course, occ: ClassOccurrence) -> str:
    return f"{course.name} — {occ.label}" if occ.label else course.name


def _flag_rows() -> Select:
    return (
        select(AttendanceFlag, AttendanceSession, ClassOccurrence, Course, Student, User, AttendanceRecord.status)
        .join(AttendanceSession, AttendanceSession.id == AttendanceFlag.session_id)
        .join(ClassOccurrence, ClassOccurrence.id == AttendanceSession.occurrence_id)
        .join(Course, Course.id == ClassOccurrence.course_id)
        .join(Student, Student.id == AttendanceFlag.student_id)
        .join(User, User.id == Student.user_id)
        .outerjoin(AttendanceRecord, (AttendanceRecord.session_id == AttendanceFlag.session_id)
                   & (AttendanceRecord.student_id == AttendanceFlag.student_id))
    )


async def _flag_out(db: AsyncSession, row) -> FlagOut:
    flag, session, occ, course, student, user, record_status = row
    crop = None
    if flag.status == "pending":
        found = await attendance_flags.closest_crop(db, flag.session_id, flag.student_id)
        if found is not None:
            crop = ClosestCropOut(id=found[0], similarity=round(found[1], 4))
    return FlagOut(
        id=flag.id, session_id=flag.session_id, session_status=session.status,
        class_code=course.code, class_name=_class_name(course, occ), class_date=session.class_date,
        student_id=student.id, name=user.name, matric_no=student.matric_no,
        flagged_at=flag.flagged_at, status=flag.status, record_status=record_status,
        reject_reason=flag.reject_reason, resolved_at=flag.resolved_at, closest_crop=crop,
    )


async def _student_of(db: AsyncSession, user: User) -> Student:
    student = await db.scalar(select(Student).where(Student.user_id == user.id))
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    return student


async def _get_flag(db: AsyncSession, actor: User, flag_id: int):
    """The flag's row, or 404; 403 unless the actor teaches its class or is an admin (NFR-04)."""
    row = (await db.execute(_flag_rows().where(AttendanceFlag.id == flag_id))).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")
    if actor.role != "admin":
        await ensure_teaches_occurrence(db, actor, row[1].occurrence_id)
    return row


# ── Student ──────────────────────────────────────────────────────────────────

@router.post("/student/me/sessions/{session_id}/flag", response_model=StudentFlagOut,
             status_code=status.HTTP_201_CREATED)
async def flag_not_recognised(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """"I'm here but wasn't recognised" (FR-318): once per session, while it is open, with no record."""
    student = await _student_of(db, actor)
    flag = await attendance_flags.create_flag(db, student, session_id)
    row = (await db.execute(_flag_rows().where(AttendanceFlag.id == flag.id))).one()
    lecturer_view = await _flag_out(db, row)
    attendance_flags.announce(db, session_id, "attendance_flagged", lecturer_view.model_dump(mode="json"))
    return _student_out(row)


def _student_out(row) -> StudentFlagOut:
    flag, session, occ, course, *_ = row
    return StudentFlagOut(
        id=flag.id, session_id=flag.session_id, class_code=course.code, class_name=_class_name(course, occ),
        class_date=session.class_date, flagged_at=flag.flagged_at, status=flag.status,
        record_status=flag.record_status, reject_reason=flag.reject_reason, resolved_at=flag.resolved_at,
    )


@router.get("/student/me/flags", response_model=list[StudentFlagOut])
async def my_flags(
    session_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """The student's own flags and their results, newest first (FR-319)."""
    student = await _student_of(db, actor)
    q = _flag_rows().where(AttendanceFlag.student_id == student.id)
    if session_id is not None:
        q = q.where(AttendanceFlag.session_id == session_id)
    rows = (await db.execute(q.order_by(AttendanceFlag.flagged_at.desc(), AttendanceFlag.id.desc()))).all()
    return [_student_out(row) for row in rows]


# ── Lecturer (admin fallback) ────────────────────────────────────────────────

@router.get("/lecturer/flags", response_model=list[FlagOut])
async def list_flags(
    session_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    """Flags in the classes the lecturer teaches (all of them for an admin), pending first.

    Pending flags stay here after the session closes (FR-319).
    """
    if status_filter is not None and status_filter not in FLAG_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="status must be pending, confirmed or rejected")
    q = _flag_rows()
    if actor.role != "admin":
        lecturer = await db.scalar(select(Lecturer).where(Lecturer.user_id == actor.id))
        if lecturer is None:
            return []
        q = q.where(ClassOccurrence.lecturer_id == lecturer.id)
    if session_id is not None:
        session = await db.get(AttendanceSession, session_id)
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if actor.role != "admin":
            await ensure_teaches_occurrence(db, actor, session.occurrence_id)
        q = q.where(AttendanceFlag.session_id == session_id)
    if status_filter is not None:
        q = q.where(AttendanceFlag.status == status_filter)
    q = q.order_by(case((AttendanceFlag.status == "pending", 0), else_=1),
                   AttendanceFlag.flagged_at.desc(), AttendanceFlag.id.desc())
    return [await _flag_out(db, row) for row in (await db.execute(q)).all()]


@router.get("/lecturer/flags/{flag_id}/crop", responses={200: {"content": {"image/jpeg": {}}}})
async def flag_crop(
    flag_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    """The unmatched crop closest to the flagging student's enrolled face (FR-407); 404 if none."""
    flag = (await _get_flag(db, actor, flag_id))[0]
    found = await attendance_flags.closest_crop(db, flag.session_id, flag.student_id) \
        if flag.status == "pending" else None
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No face crop for this flag")
    image = await db.scalar(select(UnmatchedFace.image).where(UnmatchedFace.id == found[0]))
    return Response(content=image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/lecturer/flags/{flag_id}/confirm", response_model=FlagOut)
async def confirm_flag(
    flag_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    """Confirm: Present or Late from the flag time, source `student_flag`, audited (FR-319)."""
    flag, session, _occ, _course, student, user, _status = await _get_flag(db, actor, flag_id)
    record = await attendance_flags.confirm_flag(db, flag, session, actor)
    await attendance_service.broadcast_attendance_update(session.id, record, user.name, student.matric_no, db)
    out = await _flag_out(db, (await db.execute(_flag_rows().where(AttendanceFlag.id == flag_id))).one())
    attendance_flags.announce(db, session.id, "attendance_flag_resolved", out.model_dump(mode="json"),
                              student_user_id=user.id)
    return out


@router.post("/lecturer/flags/{flag_id}/reject", response_model=FlagOut)
async def reject_flag(
    flag_id: int,
    body: RejectFlagRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    """Reject with a reason the student sees (FR-319). The student stays as they were (Absent if no record)."""
    flag, session, _occ, _course, _student, user, _status = await _get_flag(db, actor, flag_id)
    await attendance_flags.reject_flag(db, flag, session, actor, body.reason)
    out = await _flag_out(db, (await db.execute(_flag_rows().where(AttendanceFlag.id == flag_id))).one())
    attendance_flags.announce(db, session.id, "attendance_flag_resolved", out.model_dump(mode="json"),
                              student_user_id=user.id)
    return out
