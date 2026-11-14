"""Participation read interface (FR-509, S24) — the FR-509→FR-701 handover.

Read-only service that aggregates a student's (or a class's) participation across the
interaction tables. No permission checks live here: callers (M7 lecturer/student
endpoints) enforce NFR-04.

All counts are per occurrence (class session). An occurrence belongs to a course via
class_occurrences.course_id, and interaction sessions are keyed to an occurrence, so we
join interaction_* → interaction_sessions → class_occurrences to scope by course.
"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import ClassOccurrence
from app.models.interaction_live import (
    InteractionIDUSignal,
    InteractionLiveQuestion,
    InteractionLiveQuestionResponse,
    InteractionReaction,
)
from app.models.interaction_poll import InteractionPoll, InteractionPollVote
from app.models.interaction_question import InteractionQuestion


def _occurrences_in_course(db: AsyncSession, course_id: int):
    """Subquery of occurrence ids belonging to a course."""
    return select(ClassOccurrence.id).where(ClassOccurrence.course_id == course_id)


async def _base_counts(
    db: AsyncSession,
    occurrence_ids,
    student_id: int | None = None,
) -> dict[str, int]:
    """Aggregate participation counts across the five interaction write tables.

    Returns keys: questions, votes, responses, reactions, idu_signals, idu_students.
    When `student_id` is given, only that student's rows are counted.
    """
    occ_sub = occurrence_ids if hasattr(occurrence_ids, "subquery") else occurrence_ids

    questions = await db.scalar(
        select(func.count(InteractionQuestion.id)).where(
            InteractionQuestion.interaction_id.in_(occ_sub),
            *([InteractionQuestion.student_id == student_id] if student_id else []),
        )
    )
    votes = await db.scalar(
        select(func.count(InteractionPollVote.id)).join(
            InteractionPollVote.poll
        ).where(
            InteractionPoll.interaction_id.in_(occ_sub),
            *([InteractionPollVote.student_id == student_id] if student_id else []),
        )
    )
    responses = await db.scalar(
        select(func.count(InteractionLiveQuestionResponse.id)).join(
            InteractionLiveQuestionResponse.live_question
        ).where(
            InteractionLiveQuestion.interaction_id.in_(occ_sub),
            *([InteractionLiveQuestionResponse.student_id == student_id] if student_id else []),
        )
    )
    reactions = await db.scalar(
        select(func.count(InteractionReaction.id)).where(
            InteractionReaction.interaction_id.in_(occ_sub),
            *([InteractionReaction.student_id == student_id] if student_id else []),
        )
    )
    idu_signals = await db.scalar(
        select(func.count(InteractionIDUSignal.id)).where(
            InteractionIDUSignal.interaction_id.in_(occ_sub),
            *([InteractionIDUSignal.student_id == student_id] if student_id else []),
        )
    )
    idu_students = await db.scalar(
        select(func.count(func.distinct(InteractionIDUSignal.student_id))).where(
            InteractionIDUSignal.interaction_id.in_(occ_sub),
            *([InteractionIDUSignal.student_id == student_id] if student_id else []),
        )
    )
    return {
        "questions": questions or 0,
        "votes": votes or 0,
        "responses": responses or 0,
        "reactions": reactions or 0,
        "idu_signals": idu_signals or 0,
        "idu_students": idu_students or 0,
    }


async def get_student_participation_per_course(
    db: AsyncSession, student_id: int, course_id: int
) -> dict:
    """Per student per course: total participation across all of the course's sessions.

    Returns a dict with keys questions, votes, responses, reactions, idu_signals,
    idu_students, plus course_id and student_id for the caller.
    """
    occ_sub = _occurrences_in_course(db, course_id)
    counts = await _base_counts(db, occ_sub, student_id=student_id)
    counts.update({"student_id": student_id, "course_id": course_id})
    return counts


async def get_student_participation_per_session(
    db: AsyncSession, student_id: int, occurrence_id: int
) -> dict:
    """Per student per session: participation in one occurrence."""
    counts = await _base_counts(db, [occurrence_id], student_id=student_id)
    counts.update({"student_id": student_id, "occurrence_id": occurrence_id})
    return counts


async def get_class_participation_per_session(
    db: AsyncSession, occurrence_id: int
) -> dict:
    """Class-level participation counts for one occurrence (no student filter).

    `idu_students` is the number of distinct students who signalled IDU — not the number of
    clicks — so a student who signals repeatedly still counts once (FR-508).
    """
    counts = await _base_counts(db, [occurrence_id])
    counts.update({"occurrence_id": occurrence_id})
    return counts


async def list_class_sessions_with_counts(
    db: AsyncSession, course_id: int
) -> list[dict]:
    """List every occurrence of a course with its class-level participation counts.

    Useful for the M7 lecturer assessment-by-session view. Ordered by occurrence id.
    """
    occ_sub = _occurrences_in_course(db, course_id)
    occurrences = (
        await db.execute(
            select(
                ClassOccurrence.id,
                ClassOccurrence.label,
                ClassOccurrence.type,
                ClassOccurrence.day_of_week,
            )
            .where(ClassOccurrence.id.in_(occ_sub))
            .order_by(ClassOccurrence.id)
        )
    ).all()
    out = []
    for occurrence_id, label, occ_type, day in occurrences:
        entry = await get_class_participation_per_session(db, occurrence_id)
        entry["label"] = label or " ".join(part for part in (occ_type, day) if part)
        out.append(entry)
    return out


async def student_has_participated_in_course(
    db: AsyncSession, student_id: int, course_id: int
) -> bool:
    """Whether a student has any participation record in a course (cheap existence check)."""
    occ_sub = _occurrences_in_course(db, course_id)
    total = await db.scalar(
        select(func.count(InteractionQuestion.id)).where(
            InteractionQuestion.interaction_id.in_(occ_sub),
            InteractionQuestion.student_id == student_id,
        )
    )
    if total:
        return True
    total = await db.scalar(
        select(func.count(InteractionPollVote.id)).join(
            InteractionPollVote.poll
        ).where(
            InteractionPoll.interaction_id.in_(occ_sub),
            InteractionPollVote.student_id == student_id,
        )
    )
    if total:
        return True
    total = await db.scalar(
        select(func.count(InteractionLiveQuestionResponse.id)).join(
            InteractionLiveQuestionResponse.live_question
        ).where(
            InteractionLiveQuestion.interaction_id.in_(occ_sub),
            InteractionLiveQuestionResponse.student_id == student_id,
        )
    )
    if total:
        return True
    total = await db.scalar(
        select(func.count(InteractionReaction.id)).where(
            InteractionReaction.interaction_id.in_(occ_sub),
            InteractionReaction.student_id == student_id,
        )
    )
    if total:
        return True
    total = await db.scalar(
        select(func.count(InteractionIDUSignal.id)).where(
            InteractionIDUSignal.interaction_id.in_(occ_sub),
            InteractionIDUSignal.student_id == student_id,
        )
    )
    return bool(total)
