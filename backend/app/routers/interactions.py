"""Interaction questions (FR-502, FR-503, FR-509 part).

POST   /student/interactions/{interaction_id}/questions  {text, anonymous}
GET    /lecturer/interactions/{interaction_id}/questions  (lecturer view)
POST   /lecturer/interactions/{interaction_id}/questions/{question_id}/answered

NFR-04: only the occurrence's lecturer may list/answer; only an enrolled student may ask,
and only while the session is open. The student's identity is always stored but stripped
from responses when anonymous. New questions are broadcast on the interaction's websocket
room after commit.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload

from app.core.database import after_commit, get_db
from app.core.deps import ensure_teaches_occurrence, require_role
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.interaction import InteractionSession
from app.models.interaction_live import (
    InteractionIDUSignal,
    InteractionLiveQuestion,
    InteractionLiveQuestionResponse,
    InteractionReaction,
)
from app.models.interaction_poll import InteractionPoll, InteractionPollOption, InteractionPollVote
from app.models.interaction_question import InteractionQuestion
from app.models.user import Lecturer, Student, User
from app.schemas.interaction import (
    AskLiveQuestionRequest,
    AskQuestionRequest,
    CreatePollRequest,
    InteractionIDUOut,
    InteractionLiveQuestionOut,
    InteractionLiveQuestionResponseOut,
    InteractionPollOptionOut,
    InteractionPollOut,
    InteractionQuestionOut,
    OpenInteractionRequest,
    REACTION_SET,
    ReactionCountOut,
    RespondLiveQuestionRequest,
    SendIDURequest,
    SendReactionRequest,
    StudentInteractionOut,
    StudentInteractionStateOut,
    StudentLiveQuestionOut,
    StudentPollOptionOut,
    StudentPollOut,
    VoteRequest,
)
from app.websocket.manager import manager

router = APIRouter(tags=["interactions"])

_student = require_role("student")
_lecturer = require_role("lecturer")


def _question_out(
    q: InteractionQuestion, hide_identity: bool, student_name: str | None = None
) -> InteractionQuestionOut:
    if hide_identity:
        student_id, name = None, None
    else:
        student_id = q.student_id
        # `q.__dict__` avoids a lazy load (async SQLAlchemy raises MissingGreenlet).
        loaded_student = q.__dict__.get("student")
        name = student_name or (
            loaded_student.user.name if loaded_student and loaded_student.__dict__.get("user") else None
        )
    return InteractionQuestionOut(
        id=q.id,
        interaction_id=q.interaction_id,
        text=q.text,
        anonymous=q.anonymous,
        answered=q.answered,
        created_at=q.created_at,
        student_id=student_id,
        student_name=name,
        answered_by=q.answered_by,
        answered_at=q.answered_at,
    )


def _load_options():
    """Eager loads shared by every interaction query (no lazy loads in async handlers)."""
    return (
        selectinload(InteractionSession.occurrence).selectinload(ClassOccurrence.course),
        selectinload(InteractionSession.polls)
        .selectinload(InteractionPoll.options)
        .selectinload(InteractionPollOption.votes),
        selectinload(InteractionSession.live_questions),
        selectinload(InteractionSession.questions),
    )


async def _load_interaction(db: AsyncSession, interaction_id: int) -> InteractionSession | None:
    result = await db.execute(
        select(InteractionSession)
        .options(*_load_options())
        .where(InteractionSession.id == interaction_id)
    )
    return result.scalar_one_or_none()


def _latest_poll(i: InteractionSession) -> InteractionPoll | None:
    polls = sorted(i.polls, key=lambda p: p.opened_at, reverse=True)
    for p in polls:
        if p.is_open:
            return p
    return polls[0] if polls else None


def _latest_live_question(i: InteractionSession) -> InteractionLiveQuestion | None:
    questions = sorted(i.live_questions, key=lambda q: q.asked_at, reverse=True)
    for q in questions:
        if q.is_active:
            return q
    return questions[0] if questions else None


def _student_poll_out(poll: InteractionPoll, my_option_id: int | None = None) -> StudentPollOut:
    return StudentPollOut(
        id=poll.id,
        question=poll.question,
        is_open=poll.is_open,
        my_option_id=my_option_id,
        options=[
            StudentPollOptionOut(id=o.id, option_text=o.option_text, votes=len(o.votes))
            for o in sorted(poll.options, key=lambda o: o.position)
        ],
    )


def _interaction_out(i: InteractionSession) -> StudentInteractionOut:
    occ = i.occurrence
    poll = _latest_poll(i)
    live = _latest_live_question(i)
    return StudentInteractionOut(
        id=i.id,
        occurrence_id=i.occurrence_id,
        class_code=occ.course.code,
        class_name=occ.course.name,
        status=i.status,
        opened_at=i.opened_at,
        closed_by=i.closed_by,
        closed_at=i.closed_at,
        current_poll=_student_poll_out(poll) if poll else None,
        live_question=(
            StudentLiveQuestionOut(id=live.id, question=live.question, is_active=live.is_active)
            if live
            else None
        ),
    )


async def _student_row(db: AsyncSession, actor: User) -> Student:
    student = (await db.execute(select(Student).where(Student.user_id == actor.id))).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    return student


async def _get_interaction_for_student(
    db: AsyncSession, student: Student, interaction_id: int
) -> InteractionSession:
    """The interaction, 404 if unknown, 403 if the student isn't enrolled (any status)."""
    interaction = await _load_interaction(db, interaction_id)
    if not interaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction session not found")
    enrolled = await db.scalar(
        select(Enrollment.id).where(
            Enrollment.student_id == student.id,
            Enrollment.occurrence_id == interaction.occurrence_id,
        )
    )
    if not enrolled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this class")
    return interaction


async def _get_open_interaction_for_student(
    db: AsyncSession, student: Student, interaction_id: int
) -> InteractionSession:
    """The interaction, 404 if unknown, 409 if closed, 403 if the student isn't enrolled."""
    interaction = await _get_interaction_for_student(db, student, interaction_id)
    if interaction.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not open")
    return interaction


async def _get_taught_interaction(
    db: AsyncSession, actor: User, interaction_id: int
) -> InteractionSession:
    """The interaction, 404 if unknown, 403 unless `actor` teaches its class (NFR-04)."""
    interaction = await _load_interaction(db, interaction_id)
    if not interaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction session not found")
    await ensure_teaches_occurrence(db, actor, interaction.occurrence_id)
    return interaction


# ── session lifecycle (FR-501) ───────────────────────────────────────────────

@router.post("/lecturer/interactions", response_model=StudentInteractionOut,
             status_code=status.HTTP_201_CREATED)
async def open_interaction(
    body: OpenInteractionRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Open an interaction session for a class the lecturer teaches (FR-501, UC-501)."""
    occurrence = await db.get(ClassOccurrence, body.occurrence_id)
    if not occurrence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class occurrence not found")
    await ensure_teaches_occurrence(db, actor, body.occurrence_id)

    interaction = InteractionSession(
        occurrence_id=body.occurrence_id,
        status="open",
        opened_by=actor.id,
    )
    db.add(interaction)
    await db.flush()
    interaction = await _load_interaction(db, interaction.id)

    async def _announce() -> None:
        await manager.broadcast(interaction.id, {
            "event": "interaction_opened",
            "interaction_id": interaction.id,
            "occurrence_id": interaction.occurrence_id,
            "status": "open",
        })

    after_commit(db, _announce)
    return _interaction_out(interaction)


@router.post("/lecturer/interactions/{interaction_id}/close",
             response_model=StudentInteractionOut)
async def close_interaction(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Close an open interaction session (FR-501). Reopening creates a new row; history is kept."""
    interaction = await _get_taught_interaction(db, actor, interaction_id)
    if interaction.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is already closed")

    interaction.status = "closed"
    interaction.closed_by = actor.id
    interaction.closed_at = datetime.now()

    open_polls = (
        await db.execute(
            select(InteractionPoll).where(
                InteractionPoll.interaction_id == interaction_id,
                InteractionPoll.is_open.is_(True),
            )
        )
    ).scalars().all()
    for poll in open_polls:
        poll.is_open = False
        poll.closed_by = actor.id
        poll.closed_at = interaction.closed_at

    await db.flush()
    interaction = await _load_interaction(db, interaction_id)

    async def _announce() -> None:
        await manager.broadcast(interaction.id, {
            "event": "interaction_closed",
            "interaction_id": interaction.id,
            "status": "closed",
        })

    after_commit(db, _announce)
    return _interaction_out(interaction)


@router.get("/lecturer/interactions/open", response_model=list[StudentInteractionOut])
async def list_all_open_interactions(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Every open interaction session across the lecturer's classes, newest first.

    Powers the lecturer Home card (UC-501): shows 'Live' without picking a class first.
    """
    lec = (await db.execute(select(Lecturer).where(Lecturer.user_id == actor.id))).scalar_one_or_none()
    if not lec:
        return []
    result = await db.execute(
        select(InteractionSession)
        .join(ClassOccurrence, ClassOccurrence.id == InteractionSession.occurrence_id)
        .where(
            ClassOccurrence.lecturer_id == lec.id,
            InteractionSession.status == "open",
        )
        .options(*_load_options())
        .order_by(InteractionSession.opened_at.desc())
    )
    return [_interaction_out(i) for i in result.scalars().all()]


@router.get("/lecturer/interactions", response_model=list[StudentInteractionOut])
async def list_lecturer_interactions(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Open interaction sessions for a class the lecturer teaches (FR-501)."""
    await ensure_teaches_occurrence(db, actor, occurrence_id)
    result = await db.execute(
        select(InteractionSession)
        .where(
            InteractionSession.occurrence_id == occurrence_id,
            InteractionSession.status == "open",
        )
        .options(*_load_options())
        .order_by(InteractionSession.opened_at.desc())
    )
    return [_interaction_out(i) for i in result.scalars().all()]


@router.get("/lecturer/interactions/{interaction_id}", response_model=StudentInteractionOut)
async def get_lecturer_interaction(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """One interaction session (lecturer view, any status) — used to resolve the live screen."""
    interaction = await _get_taught_interaction(db, actor, interaction_id)
    return _interaction_out(interaction)


@router.get("/student/interactions", response_model=list[StudentInteractionOut])
async def list_student_interactions(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """Open interaction sessions for classes the student is enrolled in (FR-501)."""
    student = await _student_row(db, actor)
    result = await db.execute(
        select(InteractionSession)
        .join(Enrollment, Enrollment.occurrence_id == InteractionSession.occurrence_id)
        .where(
            Enrollment.student_id == student.id,
            InteractionSession.status == "open",
        )
        .options(*_load_options())
        .order_by(InteractionSession.opened_at.desc())
    )
    return [_interaction_out(i) for i in result.scalars().all()]


@router.get("/student/interactions/{interaction_id}",
            response_model=StudentInteractionStateOut)
async def get_student_interaction(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """Full state for one interaction session, scoped to the requesting student.

    Polls carry per-option counts and this student's vote; reactions carry the class
    counts and this student's current reaction; IDU carries the distinct-student count and
    whether this student already signalled; questions are only this student's own.
    Readable while closed too, so the screen can show the final state.
    """
    student = await _student_row(db, actor)
    interaction = await _get_interaction_for_student(db, student, interaction_id)

    poll = _latest_poll(interaction)
    my_option_id = None
    if poll:
        my_option_id = await db.scalar(
            select(InteractionPollVote.option_id).where(
                InteractionPollVote.poll_id == poll.id,
                InteractionPollVote.student_id == student.id,
            )
        )

    live = _latest_live_question(interaction)
    my_response = None
    if live:
        my_response = await db.scalar(
            select(InteractionLiveQuestionResponse.response).where(
                InteractionLiveQuestionResponse.live_question_id == live.id,
                InteractionLiveQuestionResponse.student_id == student.id,
            )
        )

    my_reaction = await db.scalar(
        select(InteractionReaction.reaction).where(
            InteractionReaction.interaction_id == interaction_id,
            InteractionReaction.student_id == student.id,
        )
    )
    count_rows = await db.execute(
        select(InteractionReaction.reaction, func.count(InteractionReaction.student_id))
        .where(InteractionReaction.interaction_id == interaction_id)
        .group_by(InteractionReaction.reaction)
    )
    reaction_counts = {r: c for r, c in count_rows.all()}

    idu_distinct = await db.scalar(
        select(func.count(InteractionIDUSignal.student_id)).where(
            InteractionIDUSignal.interaction_id == interaction_id
        )
    )
    has_idu = await db.scalar(
        select(InteractionIDUSignal.id).where(
            InteractionIDUSignal.interaction_id == interaction_id,
            InteractionIDUSignal.student_id == student.id,
        )
    )

    own_questions = await db.execute(
        select(InteractionQuestion)
        .where(
            InteractionQuestion.interaction_id == interaction_id,
            InteractionQuestion.student_id == student.id,
        )
        .order_by(desc(InteractionQuestion.created_at))
    )

    # Whole-session feed (FR-502/503): every question with its answered state.
    session_questions = await db.execute(
        select(InteractionQuestion)
        .options(selectinload(InteractionQuestion.student).selectinload(Student.user))
        .where(InteractionQuestion.interaction_id == interaction_id)
        .order_by(desc(InteractionQuestion.created_at))
    )

    occ = interaction.occurrence
    return StudentInteractionStateOut(
        id=interaction.id,
        occurrence_id=interaction.occurrence_id,
        class_code=occ.course.code,
        class_name=occ.course.name,
        status=interaction.status,
        opened_at=interaction.opened_at,
        closed_by=interaction.closed_by,
        closed_at=interaction.closed_at,
        current_poll=_student_poll_out(poll, my_option_id) if poll else None,
        live_question=(
            StudentLiveQuestionOut(
                id=live.id,
                question=live.question,
                is_active=live.is_active,
                my_response=my_response,
            )
            if live
            else None
        ),
        my_reaction=my_reaction,
        reaction_counts=reaction_counts,
        idu_distinct_students=idu_distinct or 0,
        idu_has_signal=has_idu is not None,
        my_questions=[_question_out(q, hide_identity=q.anonymous) for q in own_questions.scalars().all()],
        questions=[
            _question_out(q, hide_identity=q.anonymous)
            for q in session_questions.scalars().all()
        ],
    )


@router.post("/student/interactions/{interaction_id}/questions",
             response_model=InteractionQuestionOut, status_code=status.HTTP_201_CREATED)
async def ask_question(
    interaction_id: int,
    body: AskQuestionRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """A student asks a question in an open interaction session (FR-502)."""
    student = await _student_row(db, actor)
    interaction = await _get_open_interaction_for_student(db, student, interaction_id)

    question = InteractionQuestion(
        interaction_id=interaction.id,
        student_id=student.id,
        text=body.text,
        anonymous=body.anonymous,
    )
    db.add(question)
    await db.flush()
    await db.refresh(question)

    async def _announce() -> None:
        await manager.broadcast(interaction.id, {
            "event": "question_asked",
            "interaction_id": interaction.id,
            "question_id": question.id,
            "anonymous": question.anonymous,
            "created_at": question.created_at.isoformat() if question.created_at else None,
        })

    after_commit(db, _announce)
    return _question_out(question, hide_identity=question.anonymous, student_name=actor.name)


@router.get("/lecturer/interactions/{interaction_id}/questions",
            response_model=list[InteractionQuestionOut])
async def list_questions(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """All questions for an interaction session (lecturer view; identity stripped when anonymous)."""
    await _get_taught_interaction(db, actor, interaction_id)
    result = await db.execute(
        select(InteractionQuestion)
        .options(selectinload(InteractionQuestion.student).selectinload(Student.user))
        .where(InteractionQuestion.interaction_id == interaction_id)
        .order_by(desc(InteractionQuestion.created_at))
    )
    questions = result.scalars().all()
    return [_question_out(q, hide_identity=q.anonymous) for q in questions]


@router.post("/lecturer/interactions/{interaction_id}/questions/{question_id}/answered",
             response_model=InteractionQuestionOut)
async def mark_question_answered(
    interaction_id: int,
    question_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Mark a question as answered (lecturer only)."""
    await _get_taught_interaction(db, actor, interaction_id)
    question = (await db.execute(
        select(InteractionQuestion)
        .options(selectinload(InteractionQuestion.student).selectinload(Student.user))
        .where(InteractionQuestion.id == question_id)
    )).scalar_one_or_none()
    if not question or question.interaction_id != interaction_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    if question.answered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Question already marked answered")

    lecturer = (await db.execute(select(Lecturer).where(Lecturer.user_id == actor.id))).scalar_one()
    question.answered = True
    question.answered_by = lecturer.id
    question.answered_at = datetime.now()
    await db.flush()

    async def _announce() -> None:
        await manager.broadcast(interaction_id, {
            "event": "question_answered",
            "interaction_id": interaction_id,
            "question_id": question.id,
        })
    after_commit(db, _announce)

    return _question_out(question, hide_identity=question.anonymous)


async def _load_poll(db: AsyncSession, poll_id: int) -> InteractionPoll | None:
    result = await db.execute(
        select(InteractionPoll)
        .options(selectinload(InteractionPoll.options).selectinload(InteractionPollOption.votes))
        .where(InteractionPoll.id == poll_id)
    )
    return result.scalar_one_or_none()


def _poll_out(poll: InteractionPoll) -> InteractionPollOut:
    return InteractionPollOut(
        id=poll.id,
        interaction_id=poll.interaction_id,
        question=poll.question,
        is_open=poll.is_open,
        opened_by=poll.opened_by,
        opened_at=poll.opened_at,
        closed_by=poll.closed_by,
        closed_at=poll.closed_at,
        options=[
            InteractionPollOptionOut(
                id=o.id,
                poll_id=o.poll_id,
                option_text=o.option_text,
                position=o.position,
                votes=len(o.votes),
            )
            for o in sorted(poll.options, key=lambda o: o.position)
        ],
    )


@router.post("/lecturer/interactions/{interaction_id}/polls",
             response_model=InteractionPollOut, status_code=status.HTTP_201_CREATED)
async def create_poll(
    interaction_id: int,
    body: CreatePollRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """A lecturer creates a live poll (2+ options) in an open interaction session (FR-504)."""
    interaction = await _get_taught_interaction(db, actor, interaction_id)
    if interaction.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not open")

    lecturer = (await db.execute(select(Lecturer).where(Lecturer.user_id == actor.id))).scalar_one()
    poll = InteractionPoll(
        interaction_id=interaction.id,
        question=body.question,
        is_open=True,
        opened_by=lecturer.id,
    )
    db.add(poll)
    await db.flush()
    for position, option_text in enumerate(body.options):
        db.add(InteractionPollOption(poll_id=poll.id, option_text=option_text, position=position))
    await db.flush()
    poll = await _load_poll(db, poll.id)

    async def _announce() -> None:
        await manager.broadcast(interaction.id, {
            "event": "poll_created",
            "interaction_id": interaction.id,
            "poll_id": poll.id,
            "question": poll.question,
        })

    after_commit(db, _announce)
    return _poll_out(poll)


@router.get("/lecturer/interactions/{interaction_id}/polls",
            response_model=list[InteractionPollOut])
async def list_polls(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """All polls for an interaction session with live per-option counts (lecturer view)."""
    await _get_taught_interaction(db, actor, interaction_id)
    result = await db.execute(
        select(InteractionPoll)
        .options(selectinload(InteractionPoll.options).selectinload(InteractionPollOption.votes))
        .where(InteractionPoll.interaction_id == interaction_id)
        .order_by(desc(InteractionPoll.opened_at))
    )
    polls = result.scalars().all()
    return [_poll_out(poll) for poll in polls]


@router.post("/lecturer/interactions/{interaction_id}/polls/{poll_id}/close",
             response_model=InteractionPollOut)
async def close_poll(
    interaction_id: int,
    poll_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Close voting on a live poll — FR-504. The session itself stays open."""
    interaction = await _get_taught_interaction(db, actor, interaction_id)
    poll = await db.get(InteractionPoll, poll_id)
    if not poll or poll.interaction_id != interaction_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poll not found")
    if not poll.is_open:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poll is already closed")

    lecturer = (await db.execute(select(Lecturer).where(Lecturer.user_id == actor.id))).scalar_one()
    poll.is_open = False
    poll.closed_by = lecturer.id
    poll.closed_at = datetime.now()
    await db.flush()
    poll = await _load_poll(db, poll_id)

    async def _announce() -> None:
        await manager.broadcast(interaction.id, {
            "event": "poll_closed",
            "interaction_id": interaction.id,
            "poll_id": poll.id,
        })

    after_commit(db, _announce)
    return _poll_out(poll)


@router.post("/student/polls/{poll_id}/vote",
             response_model=InteractionPollOut, status_code=status.HTTP_201_CREATED)
async def vote_poll(
    poll_id: int,
    body: VoteRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """A student votes once for one poll option while the poll is open (FR-505)."""
    student = await _student_row(db, actor)

    poll = await db.get(InteractionPoll, poll_id)
    if not poll:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poll not found")
    interaction = await db.get(InteractionSession, poll.interaction_id)
    if not interaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction session not found")
    if not poll.is_open or interaction.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Poll is not open")

    enrolled = await db.scalar(
        select(Enrollment.id).where(
            Enrollment.student_id == student.id,
            Enrollment.occurrence_id == interaction.occurrence_id,
        )
    )
    if not enrolled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this class")

    existing = await db.scalar(
        select(InteractionPollVote.id).where(
            InteractionPollVote.poll_id == poll_id,
            InteractionPollVote.student_id == student.id,
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already voted in this poll")

    option = await db.get(InteractionPollOption, body.option_id)
    if not option or option.poll_id != poll_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option not found")

    vote = InteractionPollVote(poll_id=poll_id, option_id=body.option_id, student_id=student.id)
    db.add(vote)
    await db.flush()
    poll = await _load_poll(db, poll_id)

    async def _announce() -> None:
        await manager.broadcast(interaction.id, {
            "event": "poll_vote",
            "interaction_id": interaction.id,
            "poll_id": poll_id,
            "option_id": body.option_id,
        })

    after_commit(db, _announce)
    return _poll_out(poll)


# ── live question (FR-506) ──────────────────────────────────────────────────

def _live_question_out(q: InteractionLiveQuestion, responses) -> InteractionLiveQuestionOut:
    return InteractionLiveQuestionOut(
        id=q.id,
        interaction_id=q.interaction_id,
        question=q.question,
        asked_by=q.asked_by,
        asked_at=q.asked_at,
        is_active=q.is_active,
        responses=[
            InteractionLiveQuestionResponseOut(
                id=r.id,
                live_question_id=r.live_question_id,
                student_id=r.student_id,
                student_name=r.student.user.name if r.student else "",
                response=r.response,
                responded_at=r.responded_at,
            )
            for r in responses
        ],
    )


@router.post("/lecturer/interactions/{interaction_id}/live-question",
             response_model=InteractionLiveQuestionOut, status_code=status.HTTP_201_CREATED)
async def ask_live_question(
    interaction_id: int,
    body: AskLiveQuestionRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """The lecturer posts a live question to the class (FR-506)."""
    interaction = await _get_taught_interaction(db, actor, interaction_id)
    if interaction.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not open")

    # Close any previously active live question so only one is live at a time.
    active = await db.scalar(
        select(InteractionLiveQuestion).where(
            InteractionLiveQuestion.interaction_id == interaction_id,
            InteractionLiveQuestion.is_active == True,  # noqa: E712
        )
    )
    if active:
        active.is_active = False
        await db.flush()

    question = InteractionLiveQuestion(
        interaction_id=interaction_id,
        question=body.question,
        asked_by=actor.id,
        is_active=True,
    )
    db.add(question)
    await db.flush()
    await db.refresh(question)

    async def _announce() -> None:
        await manager.broadcast(interaction.id, {
            "event": "live_question_posted",
            "interaction_id": interaction_id,
            "live_question_id": question.id,
            "question": question.question,
        })

    after_commit(db, _announce)
    result = await db.execute(
        select(InteractionLiveQuestionResponse)
        .where(InteractionLiveQuestionResponse.live_question_id == question.id)
    )
    return _live_question_out(question, result.scalars().all())


@router.get("/lecturer/interactions/{interaction_id}/live-question",
            response_model=InteractionLiveQuestionOut)
async def get_live_question(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """The lecturer's current live question with responses (FR-506)."""
    await _get_taught_interaction(db, actor, interaction_id)
    result = await db.execute(
        select(InteractionLiveQuestion)
        .where(InteractionLiveQuestion.interaction_id == interaction_id)
        .order_by(InteractionLiveQuestion.asked_at.desc())
        .limit(1)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No live question")
    result = await db.execute(
        select(InteractionLiveQuestionResponse)
        .options(selectinload(InteractionLiveQuestionResponse.student).selectinload(Student.user))
        .where(InteractionLiveQuestionResponse.live_question_id == question.id)
        .order_by(InteractionLiveQuestionResponse.responded_at)
    )
    responses = result.scalars().all()
    return _live_question_out(question, responses)


@router.post("/student/interactions/{interaction_id}/live-question/{live_question_id}/response",
             response_model=InteractionLiveQuestionResponseOut, status_code=status.HTTP_201_CREATED)
async def respond_to_live_question(
    interaction_id: int,
    live_question_id: int,
    body: RespondLiveQuestionRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """A student responds to the live question (FR-506)."""
    student = await _student_row(db, actor)
    interaction = await _get_open_interaction_for_student(db, student, interaction_id)

    question = await db.get(InteractionLiveQuestion, live_question_id)
    if not question or question.interaction_id != interaction_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live question not found")
    if not question.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Live question is not active")

    existing = await db.scalar(
        select(InteractionLiveQuestionResponse.id).where(
            InteractionLiveQuestionResponse.live_question_id == live_question_id,
            InteractionLiveQuestionResponse.student_id == student.id,
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already responded to this question")

    response = InteractionLiveQuestionResponse(
        live_question_id=live_question_id,
        student_id=student.id,
        response=body.response,
    )
    db.add(response)
    await db.flush()
    await db.refresh(response)

    async def _announce() -> None:
        await manager.broadcast(interaction.id, {
            "event": "live_question_response",
            "interaction_id": interaction_id,
            "live_question_id": live_question_id,
            "response_id": response.id,
            "student_id": student.id,
        })

    after_commit(db, _announce)
    return InteractionLiveQuestionResponseOut(
        id=response.id,
        live_question_id=response.live_question_id,
        student_id=response.student_id,
        student_name=actor.name,
        response=response.response,
        responded_at=response.responded_at,
    )


# ── reactions (FR-507) ──────────────────────────────────────────────────────

@router.post("/student/interactions/{interaction_id}/reactions",
             status_code=status.HTTP_204_NO_CONTENT)
async def send_reaction(
    interaction_id: int,
    body: SendReactionRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """A student sends one of the predefined reactions (FR-507).

    Sending the same reaction the student already has cancels it (tapping the
    active chip again removes the signal).
    """
    if body.reaction not in REACTION_SET:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"reaction must be one of {list(REACTION_SET)}")
    student = await _student_row(db, actor)
    interaction = await _get_open_interaction_for_student(db, student, interaction_id)

    existing = await db.execute(
        select(InteractionReaction).where(
            InteractionReaction.interaction_id == interaction_id,
            InteractionReaction.student_id == student.id,
        )
    )
    reaction = existing.scalar_one_or_none()
    cancelled = bool(reaction and reaction.reaction == body.reaction)
    if cancelled:
        await db.delete(reaction)
    elif reaction:
        reaction.reaction = body.reaction
    else:
        reaction = InteractionReaction(
            interaction_id=interaction_id,
            student_id=student.id,
            reaction=body.reaction,
        )
        db.add(reaction)
    await db.flush()

    async def _announce() -> None:
        counts = await db.execute(
            select(InteractionReaction.reaction, func.count(InteractionReaction.student_id))
            .where(InteractionReaction.interaction_id == interaction_id)
            .group_by(InteractionReaction.reaction)
        )
        await manager.broadcast(interaction.id, {
            "event": "reaction_updated",
            "interaction_id": interaction_id,
            "counts": {r: c for r, c in counts.all()},
            "cancelled": cancelled,
        })

    after_commit(db, _announce)
    return None


@router.get("/lecturer/interactions/{interaction_id}/reactions",
            response_model=list[ReactionCountOut])
async def list_reactions(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Live per-reaction distinct-student counts for the lecturer (FR-507)."""
    await _get_taught_interaction(db, actor, interaction_id)
    counts = await db.execute(
        select(InteractionReaction.reaction, func.count(InteractionReaction.student_id))
        .where(InteractionReaction.interaction_id == interaction_id)
        .group_by(InteractionReaction.reaction)
    )
    return [ReactionCountOut(reaction=r, count=c) for r, c in counts.all()]


# ── I Don't Understand (FR-508) ─────────────────────────────────────────────

@router.post("/student/interactions/{interaction_id}/idu",
             response_model=InteractionIDUOut, status_code=status.HTTP_201_CREATED)
async def send_idu_signal(
    interaction_id: int,
    body: SendIDURequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """A student toggles 'I Don't Understand' (FR-508, S28-style toggle).

    The first tap records the signal; tapping again cancels it.
    """
    student = await _student_row(db, actor)
    interaction = await _get_open_interaction_for_student(db, student, interaction_id)

    existing = await db.execute(
        select(InteractionIDUSignal).where(
            InteractionIDUSignal.interaction_id == interaction_id,
            InteractionIDUSignal.student_id == student.id,
        )
    )
    signal = existing.scalar_one_or_none()
    cancelled = False
    if signal:
        await db.delete(signal)
        cancelled = True
    else:
        signal = InteractionIDUSignal(
            interaction_id=interaction_id,
            student_id=student.id,
        )
        db.add(signal)
        await db.flush()

    distinct = await db.scalar(
        select(func.count(InteractionIDUSignal.student_id))
        .where(InteractionIDUSignal.interaction_id == interaction_id)
    )

    async def _announce() -> None:
        await manager.broadcast(interaction.id, {
            "event": "idu_signal",
            "interaction_id": interaction_id,
            "student_id": student.id,
            "distinct_students": distinct,
            "cancelled": cancelled,
        })

    after_commit(db, _announce)
    return InteractionIDUOut(distinct_students=distinct or 0, has_signal=not cancelled)


@router.get("/lecturer/interactions/{interaction_id}/idu",
            response_model=InteractionIDUOut)
async def get_idu_count(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Number of distinct students who signalled IDU (FR-508)."""
    await _get_taught_interaction(db, actor, interaction_id)
    distinct = await db.scalar(
        select(func.count(InteractionIDUSignal.student_id))
        .where(InteractionIDUSignal.interaction_id == interaction_id)
    )
    return InteractionIDUOut(distinct_students=distinct or 0, has_signal=False)

