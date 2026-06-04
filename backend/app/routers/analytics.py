from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_role, get_current_user
from app.models.user import User, Student, Lecturer
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.session import AttendanceSession
from app.models.attendance import AttendanceRecord
from app.schemas.analytics import (
    LecturerAnalyticsOut, SessionBarEntry, AtRiskStudent,
    StudentAttendanceGroupOut, StudentAttendanceSessionOut, StudentAttendanceSummaryOut,
)

router = APIRouter(tags=["analytics"])

_lecturer_or_admin = require_role("lecturer", "admin")


def _occ_label(occ: ClassOccurrence) -> str:
    base = occ.course.name
    if occ.label:
        return f"{base} — {occ.label}"
    return base


@router.get("/lecturer/analytics", response_model=LecturerAnalyticsOut)
async def lecturer_analytics(
    occurrence_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    occ_result = await db.execute(
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.enrollments),
            selectinload(ClassOccurrence.course),
        )
        .where(ClassOccurrence.id == occurrence_id)
    )
    occ = occ_result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Occurrence not found")

    enrolled_count = len(occ.enrollments)

    sessions_result = await db.execute(
        select(AttendanceSession)
        .where(
            AttendanceSession.occurrence_id == occurrence_id,
            AttendanceSession.status == "closed",
        )
        .order_by(AttendanceSession.opened_at)
    )
    closed_sessions = sessions_result.scalars().all()

    session_bars: list[SessionBarEntry] = []
    for i, sess in enumerate(closed_sessions, start=1):
        records_result = await db.execute(
            select(AttendanceRecord).where(AttendanceRecord.session_id == sess.id)
        )
        records = records_result.scalars().all()
        present = sum(1 for r in records if r.status == "present")
        absent = sum(1 for r in records if r.status in ("absent", "unidentified"))
        session_bars.append(SessionBarEntry(
            session_id=sess.id,
            label=f"Week {i}",
            date=sess.opened_at.date().isoformat(),
            present_count=present,
            absent_count=absent,
            total=present + absent,
        ))

    sessions_held = len(closed_sessions)
    avg_rate = 0.0
    if sessions_held > 0 and enrolled_count > 0:
        total_present = sum(b.present_count for b in session_bars)
        avg_rate = round((total_present / (sessions_held * enrolled_count)) * 100, 1)

    enrolled_students = await db.execute(
        select(Student)
        .options(selectinload(Student.user))
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.occurrence_id == occurrence_id)
    )
    students = enrolled_students.scalars().all()

    at_risk: list[AtRiskStudent] = []
    if sessions_held > 0:
        for stu in students:
            present_count_result = await db.execute(
                select(func.count(AttendanceRecord.id)).where(
                    AttendanceRecord.student_id == stu.id,
                    AttendanceRecord.session_id.in_([s.id for s in closed_sessions]),
                    AttendanceRecord.status == "present",
                )
            )
            present_count = present_count_result.scalar_one()
            rate = round((present_count / sessions_held) * 100, 1)
            if rate < 80.0:
                at_risk.append(AtRiskStudent(
                    student_id=stu.id,
                    matric_no=stu.matric_no,
                    name=stu.user.name,
                    present=present_count,
                    total=sessions_held,
                    rate=rate,
                ))
        at_risk.sort(key=lambda x: x.rate)

    return LecturerAnalyticsOut(
        occurrence_id=occurrence_id,
        class_id=occurrence_id,
        class_code=occ.course.code,
        class_name=_occ_label(occ),
        enrolled_count=enrolled_count,
        sessions_held=sessions_held,
        avg_attendance_rate=avg_rate,
        sessions=session_bars,
        at_risk_students=at_risk,
    )


@router.get("/student/me/attendance/summary", response_model=StudentAttendanceSummaryOut)
async def student_attendance_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stu_result = await db.execute(select(Student).where(Student.user_id == current_user.id))
    student = stu_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    records_result = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.student_id == student.id)
    )
    records = records_result.scalars().all()

    present = sum(1 for r in records if r.status == "present")
    absent = sum(1 for r in records if r.status in ("absent", "unidentified"))
    total = present + absent
    rate_pct = f"{round((present / total) * 100, 1)}%" if total > 0 else "N/A"

    return StudentAttendanceSummaryOut(present=present, absent=absent, total=total, rate=rate_pct)


@router.get("/student/me/attendance", response_model=list[StudentAttendanceGroupOut])
async def student_attendance_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stu_result = await db.execute(select(Student).where(Student.user_id == current_user.id))
    student = stu_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    enrolled_result = await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
        .where(Enrollment.student_id == student.id)
        .order_by(ClassOccurrence.id)
    )
    occurrences = enrolled_result.scalars().all()

    groups: list[StudentAttendanceGroupOut] = []
    for occ in occurrences:
        sessions_result = await db.execute(
            select(AttendanceSession)
            .where(
                AttendanceSession.occurrence_id == occ.id,
                AttendanceSession.status == "closed",
            )
            .order_by(AttendanceSession.opened_at.desc())
        )
        sessions = sessions_result.scalars().all()

        session_items: list[StudentAttendanceSessionOut] = []
        present = 0
        absent = 0

        for sess in sessions:
            rec_result = await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.session_id == sess.id,
                    AttendanceRecord.student_id == student.id,
                )
            )
            rec = rec_result.scalar_one_or_none()
            stu_status = rec.status if rec else "absent"
            if stu_status == "present":
                present += 1
            else:
                absent += 1

            session_items.append(StudentAttendanceSessionOut(
                session_id=sess.id,
                date=sess.opened_at.date().isoformat(),
                class_code=occ.course.code,
                class_name=_occ_label(occ),
                status=stu_status,
                detected_at=rec.detected_at if rec else None,
                overridden=bool(rec and rec.override_by),
            ))

        total = present + absent
        rate = round((present / total) * 100, 1) if total > 0 else 0.0

        groups.append(StudentAttendanceGroupOut(
            occurrence_id=occ.id,
            class_id=occ.id,
            class_code=occ.course.code,
            class_name=_occ_label(occ),
            present=present,
            absent=absent,
            total=total,
            rate=rate,
            sessions=session_items,
        ))

    return groups
