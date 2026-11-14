"""Class-level engagement trends + assessment by topic/session (FR-704, FR-705, S42).

Read-only aggregation for one class (occurrence): per-session attendance rate +
participation series (trend), and class assessment performance grouped by quiz topic
and by session (from quiz_read's topic/source tags).

No permission checks inside: callers (M7 lecturer endpoint) enforce NFR-04.
"""


from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt, QuizAnswer
from app.models.session import AttendanceSession
from app.services.attendance_stats import StatusCounts


async def class_trend_per_session(
    db: AsyncSession, occurrence_id: int
) -> list[dict]:
    """Per closed session of one occurrence: attendance rate + participation count,
    ordered oldest first."""
    sessions = (await db.execute(
        select(AttendanceSession)
        .where(
            AttendanceSession.occurrence_id == occurrence_id,
            AttendanceSession.status == "closed",
        )
        .order_by(AttendanceSession.opened_at)
    )).scalars().all()

    if not sessions:
        return []

    closed_ids = [s.id for s in sessions]

    # per-session attendance counts
    counts: dict[int, StatusCounts] = {sid: StatusCounts() for sid in closed_ids}
    if closed_ids:
        rows = (await db.execute(
            select(AttendanceRecord.session_id, AttendanceRecord.status)
            .where(AttendanceRecord.session_id.in_(closed_ids))
        )).all()
        for session_id, status in rows:
            counts[session_id].add(status)

    # per-session participation count (questions + votes + responses + reactions + idu)
    from app.models.interaction import InteractionSession
    from app.models.interaction_live import (
        InteractionIDUSignal,
        InteractionLiveQuestion,
        InteractionLiveQuestionResponse,
        InteractionReaction,
    )
    from app.models.interaction_poll import InteractionPoll, InteractionPollVote
    from app.models.interaction_question import InteractionQuestion

    interaction_rows = (await db.execute(
        select(InteractionSession.id, InteractionSession.opened_at).where(
            InteractionSession.occurrence_id == occurrence_id
        )
    )).all()
    # An interaction session belongs to the occurrence, not to one attendance session;
    # attribute it to the attendance session of the same day (one class per day in practice).
    part_by_date: dict = {}
    for isid, opened_at in interaction_rows:
        q_count = await db.scalar(
            select(func.count(InteractionQuestion.id)).where(
                InteractionQuestion.interaction_id == isid
            )
        )
        v_count = await db.scalar(
            select(func.count(InteractionPollVote.id)).join(
                InteractionPollVote.poll
            ).where(InteractionPoll.interaction_id == isid)
        )
        r_count = await db.scalar(
            select(func.count(InteractionLiveQuestionResponse.id)).join(
                InteractionLiveQuestionResponse.live_question
            ).where(InteractionLiveQuestion.interaction_id == isid)
        )
        rxn_count = await db.scalar(
            select(func.count(InteractionReaction.id)).where(
                InteractionReaction.interaction_id == isid
            )
        )
        idu_count = await db.scalar(
            select(func.count(InteractionIDUSignal.id)).where(
                InteractionIDUSignal.interaction_id == isid
            )
        )
        total = (q_count or 0) + (v_count or 0) + (r_count or 0) + \
            (rxn_count or 0) + (idu_count or 0)
        if opened_at is not None:
            day = opened_at.date()
            part_by_date[day] = part_by_date.get(day, 0) + total

    out = []
    for i, sess in enumerate(sessions, start=1):
        c = counts.get(sess.id, StatusCounts())
        rate = c.rate
        out.append({
            "session": i,
            "session_id": sess.id,
            "date": sess.opened_at.date().isoformat() if sess.opened_at else None,
            "attendance_rate": rate,
            "attended": c.attended,
            "counted_sessions": c.counted_sessions,
            "participation": part_by_date.get(sess.opened_at.date(), 0) if sess.opened_at else 0,
        })
    return out


async def class_assessment_by_topic(
    db: AsyncSession, course_id: int
) -> list[dict]:
    """Class average score per quiz topic across published quizzes of the course."""
    result = await db.execute(
        select(QuizQuestion.topic, QuizAnswer.score)
        .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
        .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
        .join(Quiz, Quiz.id == QuizQuestion.quiz_id)
        .where(
            Quiz.status == "published",
            Quiz.course_id == course_id,
            QuizQuestion.type == "mcq",
            QuizAnswer.score.is_not(None),
        )
    )
    rows = result.all()
    by_topic: dict[str, list[float]] = {}
    for topic, score in rows:
        if topic is None:
            continue
        by_topic.setdefault(topic, []).append(score)
    out = []
    for topic, scores in by_topic.items():
        out.append({
            "topic": topic,
            "average_score": round(sum(scores) / len(scores), 1),
            "question_count": len(scores),
        })
    out.sort(key=lambda x: -x["average_score"])
    return out


async def class_assessment_by_session(
    db: AsyncSession, occurrence_id: int
) -> list[dict]:
    """Per closed session of one occurrence: class average quiz score for quizzes
    taken in that session (assessment linked by attempt date vs session date)."""
    sessions = (await db.execute(
        select(AttendanceSession)
        .where(
            AttendanceSession.occurrence_id == occurrence_id,
            AttendanceSession.status == "closed",
        )
        .order_by(AttendanceSession.opened_at)
    )).scalars().all()

    if not sessions:
        return []

    # attempts submitted on each session date
    session_dates = {s.id: (s.opened_at.date() if s.opened_at else None) for s in sessions}

    result = await db.execute(
        select(QuizAttempt.submitted_at, QuizAnswer.score)
        .join(QuizAnswer, QuizAnswer.attempt_id == QuizAttempt.id)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(
            Quiz.status == "published",
            QuizAttempt.status.in_(("submitted", "auto_submitted")),
            QuizAnswer.score.is_not(None),
        )
    )
    rows = result.all()
    by_session: dict[int, list[float]] = {sid: [] for sid in session_dates}
    for submitted_at, score in rows:
        if submitted_at is None:
            continue
        d = submitted_at.date()
        for sid, sd in session_dates.items():
            if sd == d:
                by_session[sid].append(score)
                break

    out = []
    for i, sess in enumerate(sessions, start=1):
        scores = by_session.get(sess.id, [])
        out.append({
            "session": i,
            "session_id": sess.id,
            "date": sess.opened_at.date().isoformat() if sess.opened_at else None,
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "quiz_count": len(scores),
        })
    return out
