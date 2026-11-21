"""Module 5 access, privacy-safe projections, cooldowns, and realtime invalidations."""
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from math import ceil

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import after_commit
from app.core.deps import ensure_teaches_occurrence
from app.core.timezone import now_myt
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.interaction import (
    InteractionBallot,
    InteractionEvent,
    InteractionPoll,
    InteractionQuestion,
    InteractionQuickAnswer,
    InteractionQuickPrompt,
)
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.websocket.manager import manager


@dataclass
class InteractionAccess:
    session: AttendanceSession
    student: Student | None = None

    @property
    def is_lecturer(self) -> bool:
        return self.student is None


async def authorize(
    db: AsyncSession, actor: User, session_id: int, *, lock: bool = False
) -> InteractionAccess:
    query = select(AttendanceSession).where(AttendanceSession.id == session_id)
    if lock:
        query = query.with_for_update()
    session = await db.scalar(query)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.occurrence_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session has no class")

    if actor.role == "lecturer":
        await ensure_teaches_occurrence(db, actor, session.occurrence_id)
        return InteractionAccess(session=session)
    if actor.role == "student":
        student = await db.scalar(select(Student).where(Student.user_id == actor.id))
        enrolled = student and await db.scalar(
            select(Enrollment.id).where(
                Enrollment.student_id == student.id,
                Enrollment.occurrence_id == session.occurrence_id,
            )
        )
        if not enrolled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this class")
        return InteractionAccess(session=session, student=student)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Interaction is for lecturers and students")


def require_open(access: InteractionAccess) -> None:
    if access.session.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Class session is not open")


def require_lecturer(access: InteractionAccess) -> None:
    if not access.is_lecturer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lecturer access required")


def require_student(access: InteractionAccess) -> Student:
    if access.student is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access required")
    return access.student


def queue_event(
    db: AsyncSession,
    session_id: int,
    event: str,
    *,
    roles: tuple[str, ...] = ("lecturer", "student"),
) -> None:
    payload = {"event": event, "attendance_session_id": session_id}

    async def _broadcast() -> None:
        await manager.broadcast_interaction(session_id, payload, roles=roles)

    after_commit(db, _broadcast)


async def question_list(db: AsyncSession, access: InteractionAccess) -> list[dict]:
    rows = (await db.execute(
        select(InteractionQuestion, User.name)
        .join(Student, Student.id == InteractionQuestion.student_id)
        .join(User, User.id == Student.user_id)
        .where(InteractionQuestion.attendance_session_id == access.session.id)
    )).all()
    vote_rows = (await db.execute(
        select(InteractionEvent.question_id, func.count())
        .where(
            InteractionEvent.attendance_session_id == access.session.id,
            InteractionEvent.kind == "question.upvoted",
        )
        .group_by(InteractionEvent.question_id)
    )).all()
    votes = dict(vote_rows)
    my_votes = set()
    if access.student is not None:
        my_votes = set((await db.scalars(select(InteractionEvent.question_id).where(
            InteractionEvent.attendance_session_id == access.session.id,
            InteractionEvent.kind == "question.upvoted",
            InteractionEvent.student_id == access.student.id,
        ))).all())
    items = []
    for question, author_name in rows:
        if question.hidden and not access.is_lecturer:
            continue
        mine = access.student is not None and question.student_id == access.student.id
        items.append({
            "id": question.id,
            "text": question.text,
            "anonymous": question.anonymous,
            "author_name": None if question.anonymous else author_name,
            "is_mine": mine,
            "answered": question.answered,
            "pinned": question.pinned,
            "hidden": question.hidden if access.is_lecturer else False,
            "votes": votes.get(question.id, 0),
            "upvoted_by_me": question.id in my_votes,
            "created_at": question.created_at,
        })
    return sorted(items, key=lambda item: (-int(item["pinned"]), -item["votes"], item["created_at"], item["id"]))


async def poll_list(db: AsyncSession, access: InteractionAccess) -> list[dict]:
    polls = (await db.scalars(
        select(InteractionPoll)
        .where(InteractionPoll.attendance_session_id == access.session.id)
        .order_by(InteractionPoll.id)
    )).all()
    ballots = (await db.scalars(
        select(InteractionBallot).join(InteractionPoll).where(
            InteractionPoll.attendance_session_id == access.session.id
        )
    )).all()
    by_poll: dict[int, list[InteractionBallot]] = {}
    for ballot in ballots:
        by_poll.setdefault(ballot.poll_id, []).append(ballot)
    items = []
    for poll in polls:
        if not access.is_lecturer and poll.status == "draft":
            continue
        rows = by_poll.get(poll.id, [])
        own = next((b.option_indexes for b in rows if access.student and b.student_id == access.student.id), None)
        can_see_results = access.is_lecturer or poll.show_results
        effective_status = poll.status if access.session.status == "open" else "closed"
        item = {
            "id": poll.id,
            "prompt": poll.prompt,
            "options": poll.options,
            "multiple": poll.multiple,
            "show_results": poll.show_results,
            "status": effective_status,
            "created_at": poll.created_at,
            "started_at": poll.started_at,
            "closed_at": poll.closed_at,
            "my_option_indexes": own,
            "results": None,
        }
        if can_see_results:
            counts = [0] * len(poll.options)
            for ballot in rows:
                for index in ballot.option_indexes:
                    if 0 <= index < len(counts):
                        counts[index] += 1
            item["results"] = {"respondent_count": len(rows), "option_counts": counts}
        items.append(item)
    return items


async def quick_prompt_list(db: AsyncSession, access: InteractionAccess) -> list[dict]:
    prompts = (await db.scalars(
        select(InteractionQuickPrompt)
        .where(InteractionQuickPrompt.attendance_session_id == access.session.id)
        .order_by(InteractionQuickPrompt.id)
    )).all()
    answer_rows = (await db.execute(
        select(InteractionQuickAnswer.quick_prompt_id, InteractionQuickAnswer.student_id)
        .join(InteractionQuickPrompt)
        .where(InteractionQuickPrompt.attendance_session_id == access.session.id)
    )).all()
    counts = Counter(prompt_id for prompt_id, _ in answer_rows)
    answered = {(prompt_id, student_id) for prompt_id, student_id in answer_rows}
    return [{
        "id": prompt.id,
        "prompt": prompt.prompt,
        "max_length": prompt.max_length,
        "status": prompt.status if access.session.status == "open" else "closed",
        "created_at": prompt.created_at,
        "answer_count": counts[prompt.id] if access.is_lecturer else None,
        "answered_by_me": bool(access.student and (prompt.id, access.student.id) in answered),
    } for prompt in prompts]


async def state(db: AsyncSession, access: InteractionAccess) -> dict:
    return {
        "attendance_session_id": access.session.id,
        "status": access.session.status,
        "can_participate": access.session.status == "open",
        "questions": await question_list(db, access),
        "polls": await poll_list(db, access),
        "quick_prompts": await quick_prompt_list(db, access),
    }


async def signal_summary(db: AsyncSession, session_id: int) -> dict:
    rows = (await db.scalars(
        select(InteractionEvent).where(
            InteractionEvent.attendance_session_id == session_id,
            InteractionEvent.kind.in_(("reaction.sent", "confusion.reported")),
        ).order_by(InteractionEvent.occurred_at)
    )).all()
    reactions = Counter(row.reaction for row in rows if row.kind == "reaction.sent")
    timeline = Counter(
        row.occurred_at.replace(second=0, microsecond=0).isoformat()
        for row in rows if row.kind == "confusion.reported"
    )
    session = await db.get(AttendanceSession, session_id)
    since = now_myt() - timedelta(seconds=settings.INTERACTION_CONFUSION_WINDOW_SECONDS)
    active_students = {
        row.student_id for row in rows
        if row.kind == "confusion.reported" and row.student_id is not None and row.occurred_at >= since
    }
    enrolled_count = 0
    if session is not None and session.occurrence_id is not None:
        enrolled_count = await db.scalar(select(func.count()).select_from(Enrollment).where(
            Enrollment.occurrence_id == session.occurrence_id
        )) or 0
    return {
        "reactions": dict(reactions),
        "confusion_total": sum(timeline.values()),
        "active_confused_students": len(active_students),
        "confusion_rate": round((len(active_students) / enrolled_count) * 100, 1) if enrolled_count else 0,
        "confusion_timeline": [{"minute": minute, "count": count} for minute, count in timeline.items()],
    }


async def enforce_cooldown(
    db: AsyncSession,
    *,
    session_id: int,
    student_id: int,
    kind: str,
    seconds: int,
) -> None:
    latest = await db.scalar(select(func.max(InteractionEvent.occurred_at)).where(
        InteractionEvent.attendance_session_id == session_id,
        InteractionEvent.student_id == student_id,
        InteractionEvent.kind == kind,
    ))
    now = now_myt()
    if latest is not None:
        remaining = seconds - (now - latest).total_seconds()
        if remaining > 0:
            retry = max(1, ceil(remaining))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before trying again",
                headers={"Retry-After": str(retry)},
            )


async def confusion_crosses_threshold(
    db: AsyncSession, *, session_id: int, occurrence_id: int, student_id: int
) -> tuple[bool, int]:
    now = now_myt()
    since = now - timedelta(seconds=settings.INTERACTION_CONFUSION_WINDOW_SECONDS)
    enrolled_ids = set((await db.scalars(select(Enrollment.student_id).where(
        Enrollment.occurrence_id == occurrence_id
    ))).all())
    before_ids = set((await db.scalars(select(InteractionEvent.student_id).where(
        InteractionEvent.attendance_session_id == session_id,
        InteractionEvent.kind == "confusion.reported",
        InteractionEvent.occurred_at >= since,
        InteractionEvent.student_id.in_(enrolled_ids),
    ))).all())
    threshold = ceil(len(enrolled_ids) * settings.INTERACTION_CONFUSION_SHARE) if enrolled_ids else 0
    after_count = len(before_ids | {student_id})
    return bool(threshold and len(before_ids) < threshold <= after_count), after_count


async def lecturer_user_id(db: AsyncSession, session: AttendanceSession) -> int | None:
    return await db.scalar(
        select(Lecturer.user_id)
        .join(ClassOccurrence, ClassOccurrence.lecturer_id == Lecturer.id)
        .where(ClassOccurrence.id == session.occurrence_id)
    )


async def enrolled_user_ids(db: AsyncSession, occurrence_id: int) -> list[int]:
    return list((await db.scalars(
        select(Student.user_id).join(Enrollment).where(Enrollment.occurrence_id == occurrence_id)
    )).all())

