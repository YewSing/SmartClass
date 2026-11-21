"""Internal, read-only M5 facts for Module 7. No anonymous author identity is returned."""
from sqlalchemy import case, distinct, func, select

from app.models.class_ import Enrollment
from app.models.interaction import (
    InteractionBallot,
    InteractionEvent,
    InteractionPoll,
    InteractionQuestion,
    InteractionQuickAnswer,
    InteractionQuickPrompt,
)
from app.models.session import AttendanceSession


async def student_counts(db, occurrence_id: int) -> list[dict]:
    """Per-student engagement for one occurrence.

    Anonymous questions are deliberately absent from individual figures (FR-504/FR-713).
    """
    session_ids = select(AttendanceSession.id).where(AttendanceSession.occurrence_id == occurrence_id)
    enrolled_ids = list((await db.scalars(
        select(Enrollment.student_id).where(Enrollment.occurrence_id == occurrence_id)
    )).all())
    event_rows = (await db.execute(
        select(
            InteractionEvent.student_id,
            func.count(distinct(case((InteractionEvent.kind.in_(("poll.answered", "poll.revised")),
                                      InteractionEvent.poll_id)))).label("polls_answered"),
            func.count(case((InteractionEvent.kind == "reaction.sent", 1))).label("reactions"),
            func.count(case((InteractionEvent.kind == "confusion.reported", 1))).label("confusion_signals"),
        )
        .where(
            InteractionEvent.attendance_session_id.in_(session_ids),
            InteractionEvent.student_id.in_(enrolled_ids),
            InteractionEvent.kind.in_((
                "poll.answered", "poll.revised", "reaction.sent", "confusion.reported",
            )),
        )
        .group_by(InteractionEvent.student_id)
    )).all()
    visible_questions = dict((await db.execute(
        select(InteractionQuestion.student_id, func.count())
        .where(
            InteractionQuestion.attendance_session_id.in_(session_ids),
            InteractionQuestion.student_id.in_(enrolled_ids),
            InteractionQuestion.anonymous.is_(False),
        )
        .group_by(InteractionQuestion.student_id)
    )).all())
    quick_answers = dict((await db.execute(
        select(InteractionQuickAnswer.student_id, func.count())
        .join(InteractionQuickPrompt)
        .where(
            InteractionQuickPrompt.attendance_session_id.in_(session_ids),
            InteractionQuickAnswer.student_id.in_(enrolled_ids),
        )
        .group_by(InteractionQuickAnswer.student_id)
    )).all())
    events = {row[0]: row[1:] for row in event_rows}
    return [{
        "student_id": student_id,
        "polls_answered": polls,
        "questions_submitted": visible_questions.get(student_id, 0),
        "reactions": reactions,
        "confusion_signals": confusion,
        "quick_answers": quick_answers.get(student_id, 0),
    } for student_id in enrolled_ids
      for polls, reactions, confusion in [events.get(student_id, (0, 0, 0))]]


async def class_totals(db, occurrence_id: int) -> dict:
    """Class aggregates may include anonymous questions, but never their authors."""
    session_ids = select(AttendanceSession.id).where(AttendanceSession.occurrence_id == occurrence_id)
    questions = await db.scalar(select(func.count()).select_from(InteractionQuestion).where(
        InteractionQuestion.attendance_session_id.in_(session_ids)
    )) or 0
    ballots = await db.scalar(
        select(func.count()).select_from(InteractionBallot)
        .join(InteractionPoll, InteractionPoll.id == InteractionBallot.poll_id)
        .where(InteractionPoll.attendance_session_id.in_(session_ids))
    ) or 0
    event_rows = dict((await db.execute(
        select(InteractionEvent.kind, func.count())
        .where(InteractionEvent.attendance_session_id.in_(session_ids))
        .group_by(InteractionEvent.kind)
    )).all())
    return {"questions_submitted": questions, "events": event_rows, "ballots": ballots}

