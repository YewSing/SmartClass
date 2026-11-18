"""Student participation history (FR-509 read side).

Read-only endpoints over the interaction tables so the student app's Participation
summary screens render from real data. NFR-04: a student sees only their own activity,
only in sessions of classes they are enrolled in — enforced here, not in the service
layer.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_role
from app.models.class_ import Enrollment
from app.models.interaction import InteractionSession
from app.models.interaction_live import (
    InteractionIDUSignal,
    InteractionLiveQuestion,
    InteractionLiveQuestionResponse,
    InteractionReaction,
)
from app.models.interaction_poll import InteractionPoll, InteractionPollVote
from app.models.interaction_question import InteractionQuestion
from app.models.user import User
from app.routers.interactions import _load_options, _student_row
from app.schemas.participation import (
    ParticipationLiveItemOut,
    ParticipationPollItemOut,
    ParticipationPollOptionOut,
    ParticipationQuestionItemOut,
    ParticipationSessionDetailOut,
    ParticipationSessionOut,
    ParticipationStatsOut,
)

router = APIRouter(tags=["participation"])

_student = require_role("student")


_COUNT_KEYS = ("questions", "votes", "responses", "reactions", "idu_signals")


async def _counts_by_interaction(
    db: AsyncSession, interaction_ids, student_id: int
) -> dict[int, dict[str, int]]:
    """The student's own activity counts per interaction session, in one grouped query
    per write table (no lazy loads — these run inside async handlers)."""
    ids = list(interaction_ids)
    if not ids:
        return {}
    sid = student_id

    async def _grouped(stmt):
        result = await db.execute(stmt)
        return {k: c for k, c in result.all()}

    questions = await _grouped(
        select(InteractionQuestion.interaction_id, func.count())
        .where(InteractionQuestion.interaction_id.in_(ids),
               InteractionQuestion.student_id == sid)
        .group_by(InteractionQuestion.interaction_id)
    )
    votes = await _grouped(
        select(InteractionPoll.interaction_id, func.count())
        .join(InteractionPollVote, InteractionPollVote.poll_id == InteractionPoll.id)
        .where(InteractionPoll.interaction_id.in_(ids),
               InteractionPollVote.student_id == sid)
        .group_by(InteractionPoll.interaction_id)
    )
    responses = await _grouped(
        select(InteractionLiveQuestion.interaction_id, func.count())
        .join(InteractionLiveQuestionResponse,
              InteractionLiveQuestionResponse.live_question_id == InteractionLiveQuestion.id)
        .where(InteractionLiveQuestion.interaction_id.in_(ids),
               InteractionLiveQuestionResponse.student_id == sid)
        .group_by(InteractionLiveQuestion.interaction_id)
    )
    reactions = await _grouped(
        select(InteractionReaction.interaction_id, func.count())
        .where(InteractionReaction.interaction_id.in_(ids),
               InteractionReaction.student_id == sid)
        .group_by(InteractionReaction.interaction_id)
    )
    idu = await _grouped(
        select(InteractionIDUSignal.interaction_id, func.count())
        .where(InteractionIDUSignal.interaction_id.in_(ids),
               InteractionIDUSignal.student_id == sid)
        .group_by(InteractionIDUSignal.interaction_id)
    )

    return {
        i: {
            "questions": questions.get(i, 0),
            "votes": votes.get(i, 0),
            "responses": responses.get(i, 0),
            "reactions": reactions.get(i, 0),
            "idu_signals": idu.get(i, 0),
        }
        for i in ids
    }


@router.get("/student/me/participation/sessions", response_model=list[ParticipationSessionOut])
async def list_my_participation_sessions(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """Every interaction session (open or closed) of the student's enrolled classes,
    newest first, with the student's own per-session activity counts."""
    student = await _student_row(db, actor)
    result = await db.execute(
        select(InteractionSession)
        .join(Enrollment, Enrollment.occurrence_id == InteractionSession.occurrence_id)
        .where(Enrollment.student_id == student.id)
        .options(*_load_options())
        .order_by(InteractionSession.opened_at.desc())
    )
    sessions = result.scalars().all()
    counts = await _counts_by_interaction(db, (s.id for s in sessions), student.id)
    out = []
    for i in sessions:
        occ = i.occurrence
        out.append(
            ParticipationSessionOut(
                id=i.id,
                occurrence_id=i.occurrence_id,
                class_code=occ.course.code,
                class_name=occ.course.name,
                status=i.status,
                opened_at=i.opened_at,
                closed_at=i.closed_at,
                **counts.get(i.id, {k: 0 for k in _COUNT_KEYS}),
            )
        )
    return out


@router.get("/student/me/participation/sessions/{interaction_id}",
            response_model=ParticipationSessionDetailOut)
async def get_my_participation_session(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """Full participation detail of one session for the requesting student: their counts,
    the polls with the class distribution and their choice, live questions and their
    responses, and their own questions. Readable while open or closed."""
    student = await _student_row(db, actor)
    result = await db.execute(
        select(InteractionSession)
        .options(*_load_options(),
                 selectinload(InteractionSession.live_questions)
                 .selectinload(InteractionLiveQuestion.responses))
        .where(InteractionSession.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    if not interaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Interaction session not found")
    enrolled = await db.scalar(
        select(Enrollment.id).where(
            Enrollment.student_id == student.id,
            Enrollment.occurrence_id == interaction.occurrence_id,
        )
    )
    if not enrolled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You are not enrolled in this class")

    sid = student.id

    polls = [
        ParticipationPollItemOut(
            id=p.id,
            question=p.question,
            is_open=p.is_open,
            my_option=next(
                (o.option_text for o in p.options
                 for v in o.votes if v.student_id == sid),
                None,
            ),
            options=[
                ParticipationPollOptionOut(option_text=o.option_text, votes=len(o.votes))
                for o in sorted(p.options, key=lambda o: o.position)
            ],
        )
        for p in sorted(interaction.polls, key=lambda p: p.opened_at)
    ]

    live_items = [
        ParticipationLiveItemOut(
            id=lq.id,
            question=lq.question,
            my_response=next((r.response for r in lq.responses if r.student_id == sid), None),
        )
        for lq in sorted(interaction.live_questions, key=lambda q: q.asked_at)
    ]

    my_questions = [
        ParticipationQuestionItemOut(id=q.id, text=q.text, anonymous=q.anonymous, answered=q.answered)
        for q in sorted(interaction.questions, key=lambda q: q.created_at)
        if q.student_id == sid
    ]

    participants = await db.scalar(
        select(func.count(func.distinct(InteractionQuestion.student_id))).where(
            InteractionQuestion.interaction_id == interaction_id
        )
    )

    occ = interaction.occurrence
    counts = await _counts_by_interaction(db, [interaction.id], sid)
    return ParticipationSessionDetailOut(
        id=interaction.id,
        occurrence_id=interaction.occurrence_id,
        class_code=occ.course.code,
        class_name=occ.course.name,
        status=interaction.status,
        opened_at=interaction.opened_at,
        closed_at=interaction.closed_at,
        stats=ParticipationStatsOut(**counts[interaction.id]),
        class_participants=participants or 0,
        polls=polls,
        live_questions=live_items,
        my_questions=my_questions,
    )
