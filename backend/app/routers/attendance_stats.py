"""Attendance rate + history endpoints (FR-307–FR-309)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import ensure_teaches_occurrence, require_role
from app.models.class_ import ClassOccurrence
from app.models.user import Student, User
from app.schemas.attendance_stats import (
    ClassAttendanceRatesOut,
    ClassAttendanceReportOut,
    ClassStudentRateOut,
    ReportSessionOut,
    ReportStudentRowOut,
    StudentCourseAttendanceOut,
    StudentSessionHistoryOut,
)
from app.services.attendance_stats import (
    class_report,
    class_student_rates,
    counts_out,
    resolve_date_range,
    session_date,
    session_label,
    student_course_history,
)

router = APIRouter(tags=["attendance"])

_student_only = require_role("student")
_lecturer = require_role("lecturer")


@router.get("/student/me/attendance/courses", response_model=list[StudentCourseAttendanceOut])
async def my_course_attendance(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_student_only),
):
    """The logged-in student's counts, rate and session history per course (FR-309)."""
    student = (await db.execute(select(Student).where(Student.user_id == user.id))).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    courses = await student_course_history(db, student.id)
    return [
        StudentCourseAttendanceOut(
            **counts_out(course["counts"]),
            course_id=course["course_id"],
            course_code=course["course_code"],
            course_name=course["course_name"],
            sessions=[StudentSessionHistoryOut(**item) for item in course["sessions"]],
        )
        for course in courses
    ]


@router.get(
    "/lecturer/classes/{occurrence_id}/attendance/rates",
    response_model=ClassAttendanceRatesOut,
)
async def class_attendance_rates(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Per-student counts and rate for one class the lecturer teaches."""
    occ = (await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .where(ClassOccurrence.id == occurrence_id)
    )).scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    await ensure_teaches_occurrence(db, actor, occurrence_id)

    closed_sessions, rows = await class_student_rates(db, occurrence_id)
    return ClassAttendanceRatesOut(
        occurrence_id=occ.id,
        course_code=occ.course.code,
        course_name=occ.course.name,
        closed_sessions=closed_sessions,
        students=[
            ClassStudentRateOut(
                **counts_out(row["counts"]),
                student_id=row["student_id"],
                matric_no=row["matric_no"],
                name=row["name"],
            )
            for row in rows
        ],
    )


@router.get(
    "/lecturer/classes/{occurrence_id}/attendance/report",
    response_model=ClassAttendanceReportOut,
)
async def class_attendance_report(
    occurrence_id: int,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Students × closed sessions for one class over an inclusive date range (FR-310)."""
    occ = (await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .where(ClassOccurrence.id == occurrence_id)
    )).scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    await ensure_teaches_occurrence(db, actor, occurrence_id)

    try:
        start, end = resolve_date_range(from_, to)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    sessions, rows = await class_report(db, occurrence_id, start, end)
    return ClassAttendanceReportOut(
        occurrence_id=occ.id,
        course_code=occ.course.code,
        course_name=occ.course.name,
        from_date=start,
        to_date=end,
        sessions=[
            ReportSessionOut(
                session_id=s.id,
                date=session_date(s),
                starts_at=s.starts_at or s.opened_at,
                label=session_label(s),
            )
            for s in sessions
        ],
        students=[
            ReportStudentRowOut(
                **counts_out(row["counts"]),
                student_id=row["student_id"],
                matric_no=row["matric_no"],
                name=row["name"],
                statuses=row["statuses"],
            )
            for row in rows
        ],
    )
