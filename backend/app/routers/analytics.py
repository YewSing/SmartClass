"""Learning analytics (FR-704, FR-705, S40).

Rebuilt on `app/services/attendance_read.py` (course_rates / course_records) so Late counts
as attended and Excused is left out (FR-308), matching the student app's rate. The NFR-04
ownership hole is closed: only the occurrence's lecturer may read its analytics.

The dead student endpoints `GET /student/me/attendance` and `/student/me/attendance/summary`
are removed (the app uses T32's `GET /student/me/attendance/courses` since T39); see the
`TEST-CHANGE:` note in PROGRESS-SHINO.md.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import ensure_teaches_occurrence, get_current_user, require_role
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.user import Student, User
from app.schemas.analytics import (
    AtRiskStudent,
    ClassAssessmentSessionOut,
    ClassAssessmentTopicOut,
    ClassSessionTrendOut,
    EngagementAttendanceOut,
    EngagementIndicatorOut,
    EngagementParticipationOut,
    EngagementQuizzesOut,
    LecturerAnalyticsOut,
    SessionBarEntry,
    StudentSelfViewOut,
)
from app.services.attendance_read import course_records
from app.services.attendance_stats import StatusCounts
from app.services.class_read import (
    class_assessment_by_session,
    class_assessment_by_topic,
    class_trend_per_session,
)
from app.services.engagement_read import (
    student_engagement_indicators,
    student_self_view,
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
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    occ_result = await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .where(ClassOccurrence.id == occurrence_id)
    )
    occ = occ_result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Occurrence not found")

    # NFR-04: close the ownership hole — only the occurrence's lecturer may read its analytics.
    await ensure_teaches_occurrence(db, actor, occurrence_id)

    course_id = occ.course_id

    # Count through the attendance read interface (Late counts as attended, Excused left out).
    rows = await course_records(db, course_id, from_date=from_date, to_date=to_date)
    occ_rows = [r for r in rows if r.occurrence_id == occurrence_id]

    # True enrollment count for this occurrence (students with no record still count as enrolled).
    enrolled_count = len(
        (
            await db.execute(select(Enrollment.id).where(Enrollment.occurrence_id == occurrence_id))
        ).scalars().all()
    )
    enrolled_student_ids = sorted({r.student_id for r in occ_rows})
    enrolled_count = max(enrolled_count, len(enrolled_student_ids))

    # Group rows by closed session (course_records only returns closed sessions).
    sessions_map: dict[int, list] = {}
    for r in occ_rows:
        sessions_map.setdefault(r.session_id, []).append(r)
    ordered = sorted(
        sessions_map.items(),
        key=lambda kv: (
            kv[1][0].date or date.min,
            kv[1][0].starts_at or datetime.min,
            kv[0],
        ),
    )

    session_bars: list[SessionBarEntry] = []
    for i, (sess_id, sess_rows) in enumerate(ordered, start=1):
        counts = StatusCounts()
        for r in sess_rows:
            counts.add(r.status)
        session_bars.append(
            SessionBarEntry(
                session_id=sess_id,
                label=f"Week {i}",
                date=(sess_rows[0].date.isoformat() if sess_rows[0].date else ""),
                present_count=counts.attended,  # Late counts as attended (FR-308)
                absent_count=counts.absent,
                total=counts.counted_sessions,  # Excused left out (FR-308)
            )
        )

    sessions_held = len(session_bars)

    # Per-student rate for this occurrence (attendance_read semantics).
    student_counts = {sid: StatusCounts() for sid in enrolled_student_ids}
    for sess_id, sess_rows in ordered:
        row_by_student = {r.student_id: r.status for r in sess_rows}
        for sid in enrolled_student_ids:
            student_counts[sid].add(row_by_student.get(sid, "absent"))

    avg_rate = 0.0
    if sessions_held > 0 and enrolled_count > 0:
        valid = [c.rate for c in student_counts.values() if c.rate is not None]
        if valid:
            avg_rate = round(sum(valid) / len(valid), 1)

    # At-risk: rate < 80%.
    at_risk: list[AtRiskStudent] = []
    stu_rows = (
        await db.execute(
            select(Student)
            .options(selectinload(Student.user))
            .join(Enrollment, Enrollment.student_id == Student.id)
            .where(Enrollment.occurrence_id == occurrence_id)
            .order_by(Student.matric_no)
        )
    ).scalars.all()
    for stu in stu_rows:
        c = student_counts.get(stu.id)
        rate = c.rate if c else None
        if rate is not None and rate < 80.0:
            at_risk.append(
                AtRiskStudent(
                    student_id=stu.id,
                    matric_no=stu.matric_no,
                    name=stu.user.name,
                    present=c.attended if c else 0,
                    total=c.counted_sessions if c else sessions_held,
                    rate=rate,
                )
            )
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


# ── S41: per-student engagement indicators (FR-701, FR-702, FR-703) ──────────

@router.get(
    "/lecturer/analytics/{occurrence_id}/students",
    response_model=list[EngagementIndicatorOut],
)
async def lecturer_student_engagement(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    """Per-student engagement indicators for students of a class the lecturer teaches (NFR-04)."""
    await ensure_teaches_occurrence(db, actor, occurrence_id)
    occ_result = await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .where(ClassOccurrence.id == occurrence_id)
    )
    occ = occ_result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    students_result = await db.execute(
        select(Student)
        .options(selectinload(Student.user))
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.occurrence_id == occurrence_id)
        .order_by(Student.matric_no)
    )
    students = students_result.scalars().all()

    out = []
    for stu in students:
        indicators = await student_engagement_indicators(db, occ.course_id, stu.id)
        out.append(
            EngagementIndicatorOut(
                student_id=stu.id,
                student_name=stu.user.name,
                matric_no=stu.matric_no,
                course_id=occ.course_id,
                attendance=EngagementAttendanceOut(
                    rate=indicators["attendance"]["rate"],
                    absence_frequency=indicators["attendance"]["absence_frequency"],
                ),
                participation=EngagementParticipationOut(
                    frequency=indicators["participation"]["frequency"],
                    questions=indicators["participation"]["questions"],
                    votes=indicators["participation"]["votes"],
                    responses=indicators["participation"]["responses"],
                    reactions=indicators["participation"]["reactions"],
                    idu_signals=indicators["participation"]["idu_signals"],
                ),
                quizzes=EngagementQuizzesOut(
                    scores=indicators["quizzes"]["scores"],
                    average_score=indicators["quizzes"]["average_score"],
                    trend=indicators["quizzes"]["trend"],
                ),
            )
        )
    return out


# ── S42: class-level trends + assessment (FR-704, FR-705) ───────────────────

@router.get(
    "/lecturer/analytics/{occurrence_id}/trend",
    response_model=list[ClassSessionTrendOut],
)
async def lecturer_class_trend(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    """Per-session attendance rate + participation series for one class (FR-704)."""
    await ensure_teaches_occurrence(db, actor, occurrence_id)
    return await class_trend_per_session(db, occurrence_id)


@router.get(
    "/lecturer/analytics/{occurrence_id}/assessment-by-topic",
    response_model=list[ClassAssessmentTopicOut],
)
async def lecturer_assessment_by_topic(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    """Class assessment performance by quiz topic for the course of this class (FR-705)."""
    await ensure_teaches_occurrence(db, actor, occurrence_id)
    occ_result = await db.execute(
        select(ClassOccurrence).where(ClassOccurrence.id == occurrence_id)
    )
    occ = occ_result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return await class_assessment_by_topic(db, occ.course_id)


@router.get(
    "/lecturer/analytics/{occurrence_id}/assessment-by-session",
    response_model=list[ClassAssessmentSessionOut],
)
async def lecturer_assessment_by_session(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    """Class average quiz score per session for one class (FR-705)."""
    await ensure_teaches_occurrence(db, actor, occurrence_id)
    return await class_assessment_by_session(db, occurrence_id)


# ── S43: student self view (FR-706) ──────────────────────────────────────────

@router.get(
    "/student/me/analytics",
    response_model=StudentSelfViewOut,
)
async def student_self_analytics(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """The student's own attendance status and engagement indicators (FR-706).

    Only the requesting student's data is returned; a student cannot read another
    student's indicators.
    """
    return await student_self_view(db, actor.id)


