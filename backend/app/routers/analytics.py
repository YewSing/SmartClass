"""Learning analytics (FR-704, FR-705, S40).

Rebuilt on `app/services/attendance_read.py` (course_rates / course_records) so Late counts
as attended and Excused is left out (FR-308), matching the student app's rate. The NFR-04
ownership hole is closed: only the occurrence's lecturer may read its analytics.

The dead student endpoints `GET /student/me/attendance` and `/student/me/attendance/summary`
are removed (the app uses T32's `GET /student/me/attendance/courses` since T39); see the
`TEST-CHANGE:` note in PROGRESS-SHINO.md.
"""

from datetime import date, datetime, time

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
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
    ParticipationBarEntry,
    QuizAtRiskStudent,
    QuizTrendEntry,
    SessionBarEntry,
    StudentSelfViewOut,
)
from app.services.attendance_read import course_records
from app.services.attendance_stats import StatusCounts
from app.models.interaction_live import (
    InteractionIDUSignal,
    InteractionLiveQuestion,
    InteractionLiveQuestionResponse,
    InteractionReaction,
)
from app.models.interaction_poll import InteractionPoll, InteractionPollVote
from app.models.interaction_question import InteractionQuestion
from app.models.interaction import InteractionSession
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt
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

    # Calculate real calendar week relative to the earliest session of this occurrence
    all_dates = [kv[1][0].date for kv in ordered if kv[1][0].date]
    earliest_date = min(all_dates) if all_dates else date.today()

    session_week_map = {}
    for sess_id, sess_rows in ordered:
        s_date = sess_rows[0].date or date.today()
        wk_num = max(1, ((s_date - earliest_date).days // 7) + 1)
        session_week_map[sess_id] = (wk_num, s_date)

    sessions_per_week = {}
    for sess_id, (wk_num, _) in session_week_map.items():
        sessions_per_week[wk_num] = sessions_per_week.get(wk_num, 0) + 1

    session_bars: list[SessionBarEntry] = []
    for sess_id, sess_rows in ordered:
        counts = StatusCounts()
        for r in sess_rows:
            counts.add(r.status)
        wk_num, s_date = session_week_map[sess_id]
        if sessions_per_week[wk_num] > 1:
            lbl = f"Week {wk_num} ({s_date.strftime('%d %b')})"
        else:
            lbl = f"Week {wk_num}"
        session_bars.append(
            SessionBarEntry(
                session_id=sess_id,
                label=lbl,
                date=(s_date.isoformat() if s_date else ""),
                present_count=counts.attended,  # Late counts as attended (FR-308)
                absent_count=counts.absent,
                total=counts.counted_sessions,  # Excused left out (FR-308)
                late_count=counts.late,
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
    ).scalars().all()
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

    # Participation (FR-702): per-student rate over the interaction sessions held for
    # this occurrence — sessions participated / sessions held, at-risk below 80%.
    interaction_query = select(
        InteractionSession.id,
        InteractionSession.occurrence_id,
        InteractionSession.opened_at,
    ).where(InteractionSession.occurrence_id == occurrence_id)
    if from_date:
        interaction_query = interaction_query.where(
            InteractionSession.opened_at >= datetime.combine(from_date, time.min)
        )
    if to_date:
        interaction_query = interaction_query.where(
            InteractionSession.opened_at <= datetime.combine(to_date, time.max)
        )
    interaction_rows = (
        await db.execute(
            interaction_query.order_by(InteractionSession.opened_at, InteractionSession.id)
        )
    ).all()
    interaction_sessions_held = len(interaction_rows)
    session_ids = [iid for iid, _, _ in interaction_rows]

    # Distinct (interaction_id, student_id) participant pairs across the five write tables.
    participants: dict[int, set[int]] = {iid: set() for iid in session_ids}
    if session_ids:
        async def _pairs(stmt):
            for iid, sid in (await db.execute(stmt)).all():
                participants[iid].add(sid)

        await _pairs(
            select(InteractionQuestion.interaction_id, InteractionQuestion.student_id)
            .where(InteractionQuestion.interaction_id.in_(session_ids))
        )
        await _pairs(
            select(InteractionPollVote.poll_id, InteractionPollVote.student_id)
            .join(InteractionPoll, InteractionPoll.id == InteractionPollVote.poll_id)
            .where(InteractionPoll.interaction_id.in_(session_ids))
        )
        await _pairs(
            select(
                InteractionLiveQuestion.interaction_id,
                InteractionLiveQuestionResponse.student_id,
            )
            .join(
                InteractionLiveQuestion,
                InteractionLiveQuestion.id == InteractionLiveQuestionResponse.live_question_id,
            )
            .where(InteractionLiveQuestion.interaction_id.in_(session_ids))
        )
        await _pairs(
            select(InteractionReaction.interaction_id, InteractionReaction.student_id)
            .where(InteractionReaction.interaction_id.in_(session_ids))
        )
        await _pairs(
            select(InteractionIDUSignal.interaction_id, InteractionIDUSignal.student_id)
            .where(InteractionIDUSignal.interaction_id.in_(session_ids))
        )

    inter_dates = [opened_at.date() for _, _, opened_at in interaction_rows if opened_at]
    earliest_inter_date = min(inter_dates) if inter_dates else date.today()
    inter_week_map = {}
    for iid, _occ, opened_at in interaction_rows:
        i_date = opened_at.date() if opened_at else date.today()
        wk_num = max(1, ((i_date - earliest_inter_date).days // 7) + 1)
        inter_week_map[iid] = (wk_num, i_date)

    inter_per_week = {}
    for iid, (wk_num, _) in inter_week_map.items():
        inter_per_week[wk_num] = inter_per_week.get(wk_num, 0) + 1

    participation_bars = [
        ParticipationBarEntry(
            interaction_id=iid,
            label=(
                f"Week {inter_week_map[iid][0]} ({inter_week_map[iid][1].strftime('%d %b')})"
                if inter_per_week[inter_week_map[iid][0]] > 1
                else f"Week {inter_week_map[iid][0]}"
            ),
            date=inter_week_map[iid][1].isoformat() if iid in inter_week_map else "",
            participants=len(participants[iid]),
        )
        for iid, _occ, _opened_at in interaction_rows
    ]

    participation_at_risk: list[AtRiskStudent] = []
    rates: list[float] = []
    if interaction_sessions_held > 0:
        for stu in stu_rows:
            participated = sum(
                1 for iid, _occ, _opened_at in interaction_rows if stu.id in participants[iid]
            )
            rate = round(participated / interaction_sessions_held * 100, 1)
            rates.append(rate)
            if rate < 80.0:
                participation_at_risk.append(
                    AtRiskStudent(
                        student_id=stu.id,
                        matric_no=stu.matric_no,
                        name=stu.user.name,
                        present=participated,
                        total=interaction_sessions_held,
                        rate=rate,
                    )
                )
        participation_at_risk.sort(key=lambda x: x.rate)
        avg_participation_rate = round(sum(rates) / len(rates), 1) if rates else 0.0
    else:
        avg_participation_rate = 0.0

    # Quiz (FR-612/613): per-quiz class averages for the trend graph and very-low-score
    # flagging. Attempt scores are point totals, so each attempt is normalised to a
    # percentage of its quiz's max points before averaging.
    QUIZ_AT_RISK_THRESHOLD = 50.0

    quiz_query = select(Quiz.id, Quiz.title).where(
        Quiz.course_id == course_id, Quiz.status == "published"
    )
    if from_date:
        quiz_query = quiz_query.where(Quiz.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        quiz_query = quiz_query.where(Quiz.created_at <= datetime.combine(to_date, time.max))
    quiz_rows = (
        await db.execute(
            quiz_query.order_by(Quiz.created_at, Quiz.id)
        )
    ).all()

    max_points: dict[int, float] = {}
    if quiz_rows:
        q_rows = (
            await db.execute(
                select(
                    QuizQuestion.quiz_id,
                    func.coalesce(func.sum(func.coalesce(QuizQuestion.score, 1.0)), 0.0),
                )
                .where(QuizQuestion.quiz_id.in_([q[0] for q in quiz_rows]))
                .group_by(QuizQuestion.quiz_id)
            )
        ).all()
        max_points = {quiz_id: pts for quiz_id, pts in q_rows}

    # Graded attempts (score recorded) on those quizzes, joined to their quiz.
    attempt_rows = (
        await db.execute(
            select(QuizAttempt.quiz_id, QuizAttempt.student_id, QuizAttempt.score)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(
                Quiz.course_id == course_id,
                Quiz.status == "published",
                QuizAttempt.score.is_not(None),
            )
        )
    ).all()

    quiz_ids = {q.id for q in quiz_rows}
    attempts_by_quiz: dict[int, list[tuple[int, float]]] = {q.id: [] for q in quiz_rows}
    for quiz_id, student_id, score in attempt_rows:
        if quiz_id in quiz_ids:
            attempts_by_quiz[quiz_id].append((student_id, score))

    # Normalise every attempt to a percentage of its quiz's max points.
    pct_by_quiz: dict[int, list[tuple[int, float]]] = {}
    for quiz_id, title in quiz_rows:
        pts = max_points.get(quiz_id, 0.0) or 0.0
        pct_by_quiz[quiz_id] = [
            (student_id, (score / pts * 100.0) if pts > 0 else 0.0)
            for student_id, score in attempts_by_quiz[quiz_id]
        ]

    quiz_trend = [
        QuizTrendEntry(
            quiz_id=quiz_id,
            title=title,
            average_score=(
                round(sum(p for _, p in pct_by_quiz[quiz_id]) / len(pct_by_quiz[quiz_id]), 1)
                if pct_by_quiz[quiz_id] else None
            ),
            attempts=len(pct_by_quiz[quiz_id]),
        )
        for quiz_id, title in quiz_rows
    ]

    student_scores: dict[int, list[float]] = {}
    for entries in pct_by_quiz.values():
        for student_id, pct in entries:
            student_scores.setdefault(student_id, []).append(pct)

    quiz_at_risk: list[QuizAtRiskStudent] = []
    all_student_averages: list[float] = []
    for stu in stu_rows:
        scores = student_scores.get(stu.id)
        if not scores:
            continue  # no graded quiz yet — nothing to flag
        average = round(sum(scores) / len(scores), 1)
        all_student_averages.append(average)
        if average < QUIZ_AT_RISK_THRESHOLD:
            quiz_at_risk.append(
                QuizAtRiskStudent(
                    student_id=stu.id,
                    matric_no=stu.matric_no,
                    name=stu.user.name,
                    average_score=average,
                    quiz_count=len(scores),
                )
            )
    quiz_at_risk.sort(key=lambda x: x.average_score)

    avg_quiz_score = (
        round(sum(all_student_averages) / len(all_student_averages), 1)
        if all_student_averages
        else None
    )

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
        interaction_sessions_held=interaction_sessions_held,
        avg_participation_rate=avg_participation_rate,
        participation_bars=participation_bars,
        participation_at_risk=participation_at_risk,
        quiz_count=len(quiz_rows),
        avg_quiz_score=avg_quiz_score,
        quiz_trend=quiz_trend,
        quiz_at_risk=quiz_at_risk,
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
    occ_result = await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .where(ClassOccurrence.id == occurrence_id)
    )
    occ = occ_result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    await ensure_teaches_occurrence(db, actor, occurrence_id)

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
    student = (await db.execute(
        select(Student).where(Student.user_id == actor.id)
    )).scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Student profile not found")
    return await student_self_view(db, student.id)


# ── CSV export for the Participation / Quiz / Students tabs (FR-704, FR-705) ──

@router.get("/lecturer/analytics/{occurrence_id}/export-csv")
async def export_analytics_csv(
    occurrence_id: int,
    section: str = Query(..., regex="^(participation|quiz|students)$"),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    """CSV report matching what the lecturer's analytics screen shows."""
    occ_result = await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .where(ClassOccurrence.id == occurrence_id)
    )
    occ = occ_result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Occurrence not found")
    await ensure_teaches_occurrence(db, actor, occurrence_id)

    rows: list[list] = []
    if section == "participation":
        sessions = (await db.execute(
            select(InteractionSession)
            .where(
                InteractionSession.occurrence_id == occurrence_id,
                InteractionSession.opened_at >= datetime.combine(from_date, time.min) if from_date else True,
                InteractionSession.opened_at <= datetime.combine(to_date, time.max) if to_date else True,
            )
            .order_by(InteractionSession.opened_at)
        )).scalars().all()
        header = ["Interaction ID", "Opened at", "Status", "Distinct participants"]
        for s in sessions:
            student_ids = set()
            for model in (InteractionQuestion, InteractionLiveQuestionResponse,
                          InteractionReaction, InteractionIDUSignal):
                ids = (await db.execute(
                    select(model.student_id).where(model.interaction_id == s.id)
                )).scalars().all()
                student_ids.update(ids)
            votes = (await db.execute(
                select(InteractionPollVote.student_id)
                .join(InteractionPoll, InteractionPoll.id == InteractionPollVote.poll_id)
                .where(InteractionPoll.interaction_id == s.id)
            )).scalars().all()
            student_ids.update(votes)
            rows.append([s.id, s.opened_at.isoformat() if s.opened_at else "", s.status, len(student_ids)])
    elif section == "quiz":
        quiz_rows = (await db.execute(
            select(Quiz.id, Quiz.title, Quiz.status)
            .where(Quiz.course_id == occ.course_id, Quiz.status != "deleted")
            .order_by(Quiz.id)
        )).all()
        header = ["Quiz", "Status", "Graded attempts", "Average raw score", "Average %"]
        for quiz_id, title, qstatus in quiz_rows:
            attempts, avg_raw = (await db.execute(
                select(func.count(QuizAttempt.id), func.avg(QuizAttempt.score))
                .where(QuizAttempt.quiz_id == quiz_id)
            )).one()
            max_points = await db.scalar(
                select(func.coalesce(func.sum(QuizQuestion.score), 0.0))
                .where(QuizQuestion.quiz_id == quiz_id)
            ) or 0.0
            avg_pct = (avg_raw / max_points * 100) if avg_raw is not None and max_points else None
            rows.append([
                title, qstatus, attempts or 0,
                round(avg_raw, 1) if avg_raw is not None else "",
                round(avg_pct, 1) if avg_pct is not None else "",
            ])
    else:  # students
        students_result = await db.execute(
            select(Student)
            .options(selectinload(Student.user))
            .join(Enrollment, Enrollment.student_id == Student.id)
            .where(Enrollment.occurrence_id == occurrence_id)
            .order_by(Student.matric_no)
        )
        students = students_result.scalars().all()
        header = ["Matric No", "Name", "Attendance %", "Absences",
                  "Participation actions", "Questions", "Votes", "Quiz average %"]
        for stu in students:
            ind = await student_engagement_indicators(db, occ.course_id, stu.id)
            rows.append([
                stu.matric_no,
                stu.user.name,
                ind["attendance"]["rate"] if ind["attendance"]["rate"] is not None else "",
                ind["attendance"]["absence_frequency"] if ind["attendance"]["absence_frequency"] is not None else "",
                ind["participation"]["frequency"],
                ind["participation"]["questions"],
                ind["participation"]["votes"],
                round(ind["quizzes"]["average_score"], 1) if ind["quizzes"]["average_score"] is not None else "",
            ])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([f"{section} report — {occ.course.code}"])
    writer.writerow(header)
    writer.writerows(rows)
    filename = f"{section}_report_{occ.course.code}_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


