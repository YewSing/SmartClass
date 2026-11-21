"""Module 5 live classroom interaction, always bound to an AttendanceSession."""
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, after_commit, get_db
from app.core.deps import get_current_user
from app.core.security import decode_token
from app.core.timezone import now_myt
from app.models.interaction import (
    InteractionBallot,
    InteractionEvent,
    InteractionPoll,
    InteractionQuestion,
    InteractionQuickAnswer,
    InteractionQuickPrompt,
)
from app.models.user import Student, User
from app.schemas.interaction import (
    ConfusionCreate,
    PollCreate,
    PollVisibility,
    PollVote,
    QuestionCreate,
    QuestionModerate,
    QuickAnswerCreate,
    QuickPromptCreate,
    ReactionCreate,
)
from app.services import interaction_service as service
from app.services import notify
from app.services.audit_service import write_log
from app.websocket.manager import manager

router = APIRouter(prefix="/interaction/sessions", tags=["interaction"])


async def _access(db, actor, session_id, *, lock=False):
    return await service.authorize(db, actor, session_id, lock=lock)


def _find(items, item_id):
    return next(item for item in items if item["id"] == item_id)


@router.get("/{session_id}")
async def get_state(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return await service.state(db, await _access(db, actor, session_id))


@router.get("/{session_id}/questions")
async def list_questions(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return await service.question_list(db, await _access(db, actor, session_id))


@router.post("/{session_id}/questions", status_code=status.HTTP_201_CREATED)
async def create_question(
    session_id: int,
    body: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    student = service.require_student(access)
    question = InteractionQuestion(
        attendance_session_id=session_id,
        student_id=student.id,
        text=body.text,
        anonymous=body.anonymous,
    )
    db.add(question)
    await db.flush()
    db.add(InteractionEvent(
        attendance_session_id=session_id,
        student_id=student.id,
        kind="question.submitted",
        question_id=question.id,
    ))
    service.queue_event(db, session_id, "interaction.questions_changed")
    return _find(await service.question_list(db, access), question.id)


@router.put("/{session_id}/questions/{question_id}/upvote")
async def upvote_question(
    session_id: int,
    question_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    student = service.require_student(access)
    question = await db.get(InteractionQuestion, question_id)
    if question is None or question.attendance_session_id != session_id or question.hidden:
        raise HTTPException(status_code=404, detail="Question not found")
    exists = await db.scalar(select(InteractionEvent.id).where(
        InteractionEvent.kind == "question.upvoted",
        InteractionEvent.question_id == question_id,
        InteractionEvent.student_id == student.id,
    ))
    if not exists:
        db.add(InteractionEvent(
            attendance_session_id=session_id,
            student_id=student.id,
            kind="question.upvoted",
            question_id=question_id,
        ))
        await db.flush()
        service.queue_event(db, session_id, "interaction.questions_changed")
    return _find(await service.question_list(db, access), question_id)


@router.patch("/{session_id}/questions/{question_id}")
async def moderate_question(
    session_id: int,
    question_id: int,
    body: QuestionModerate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    service.require_lecturer(access)
    question = await db.get(InteractionQuestion, question_id)
    if question is None or question.attendance_session_id != session_id:
        raise HTTPException(status_code=404, detail="Question not found")
    before = {"answered": question.answered, "pinned": question.pinned, "hidden": question.hidden}
    for field in ("answered", "pinned", "hidden"):
        value = getattr(body, field)
        if value is not None:
            setattr(question, field, value)
    after = {"answered": question.answered, "pinned": question.pinned, "hidden": question.hidden}
    if before["hidden"] != after["hidden"]:
        await write_log(db, actor.id, "INTERACTION_QUESTION_HIDDEN", "interaction_question", question.id,
                        {"hidden": before["hidden"]}, {"hidden": after["hidden"]})
    await db.flush()
    service.queue_event(db, session_id, "interaction.questions_changed")
    return _find(await service.question_list(db, access), question_id)


@router.get("/{session_id}/polls")
async def list_polls(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return await service.poll_list(db, await _access(db, actor, session_id))


@router.post("/{session_id}/polls", status_code=status.HTTP_201_CREATED)
async def create_poll(
    session_id: int,
    body: PollCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    service.require_lecturer(access)
    poll = InteractionPoll(attendance_session_id=session_id, **body.model_dump())
    db.add(poll)
    await db.flush()
    service.queue_event(db, session_id, "interaction.polls_changed", roles=("lecturer",))
    return _find(await service.poll_list(db, access), poll.id)


async def _get_poll(db, session_id, poll_id):
    poll = await db.get(InteractionPoll, poll_id)
    if poll is None or poll.attendance_session_id != session_id:
        raise HTTPException(status_code=404, detail="Poll not found")
    return poll


@router.post("/{session_id}/polls/{poll_id}/start")
async def start_poll(
    session_id: int,
    poll_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    service.require_lecturer(access)
    poll = await _get_poll(db, session_id, poll_id)
    if poll.status == "closed":
        raise HTTPException(status_code=409, detail="Poll is closed")
    if poll.status == "draft":
        poll.status = "open"
        poll.started_at = now_myt()
        await db.flush()
        recipients = await service.enrolled_user_ids(db, access.session.occurrence_id)
        payload = {
            "poll_id": poll.id,
            "session_id": session_id,
            "message": poll.prompt,
            "link": f"/interaction/sessions/{session_id}",
        }

        async def _notify() -> None:
            await notify.emit("poll.started", recipients, payload)

        after_commit(db, _notify)
        service.queue_event(db, session_id, "interaction.polls_changed")
    return _find(await service.poll_list(db, access), poll.id)


@router.post("/{session_id}/polls/{poll_id}/close")
async def close_poll(
    session_id: int,
    poll_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    service.require_lecturer(access)
    poll = await _get_poll(db, session_id, poll_id)
    if poll.status == "draft":
        raise HTTPException(status_code=409, detail="Poll has not started")
    if poll.status != "closed":
        poll.status = "closed"
        poll.closed_at = now_myt()
        await db.flush()
        service.queue_event(db, session_id, "interaction.polls_changed")
    return _find(await service.poll_list(db, access), poll.id)


@router.patch("/{session_id}/polls/{poll_id}")
async def set_poll_visibility(
    session_id: int,
    poll_id: int,
    body: PollVisibility,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    service.require_lecturer(access)
    poll = await _get_poll(db, session_id, poll_id)
    poll.show_results = body.show_results
    await db.flush()
    service.queue_event(db, session_id, "interaction.polls_changed")
    return _find(await service.poll_list(db, access), poll.id)


@router.put("/{session_id}/polls/{poll_id}/vote")
async def vote_poll(
    session_id: int,
    poll_id: int,
    body: PollVote,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    student = service.require_student(access)
    poll = await _get_poll(db, session_id, poll_id)
    if poll.status != "open":
        raise HTTPException(status_code=409, detail="Poll is not open")
    choices = sorted(set(body.option_indexes))
    if len(choices) != len(body.option_indexes) or any(i < 0 or i >= len(poll.options) for i in choices):
        raise HTTPException(status_code=422, detail="Invalid poll option")
    if not poll.multiple and len(choices) != 1:
        raise HTTPException(status_code=422, detail="Choose one poll option")
    ballot = await db.scalar(select(InteractionBallot).where(
        InteractionBallot.poll_id == poll.id,
        InteractionBallot.student_id == student.id,
    ))
    changed = ballot is None or ballot.option_indexes != choices
    if ballot is None:
        ballot = InteractionBallot(poll_id=poll.id, student_id=student.id, option_indexes=choices)
        db.add(ballot)
        event_kind = "poll.answered"
    else:
        ballot.option_indexes = choices
        ballot.updated_at = now_myt()
        event_kind = "poll.revised"
    if changed:
        db.add(InteractionEvent(
            attendance_session_id=session_id,
            student_id=student.id,
            kind=event_kind,
            poll_id=poll.id,
        ))
        await db.flush()
        roles = ("lecturer", "student") if poll.show_results else ("lecturer",)
        service.queue_event(db, session_id, "interaction.poll_results_changed", roles=roles)
    return _find(await service.poll_list(db, access), poll.id)


@router.get("/{session_id}/quick-prompts")
async def list_quick_prompts(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return await service.quick_prompt_list(db, await _access(db, actor, session_id))


@router.post("/{session_id}/quick-prompts", status_code=status.HTTP_201_CREATED)
async def create_quick_prompt(
    session_id: int,
    body: QuickPromptCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    service.require_lecturer(access)
    prompt = InteractionQuickPrompt(
        attendance_session_id=session_id,
        prompt=body.prompt,
        max_length=body.max_length or settings.INTERACTION_QUICK_ANSWER_MAX_LENGTH,
    )
    db.add(prompt)
    await db.flush()
    service.queue_event(db, session_id, "interaction.quick_prompts_changed")
    return _find(await service.quick_prompt_list(db, access), prompt.id)


async def _get_quick_prompt(db, session_id, prompt_id):
    prompt = await db.get(InteractionQuickPrompt, prompt_id)
    if prompt is None or prompt.attendance_session_id != session_id:
        raise HTTPException(status_code=404, detail="Quick question not found")
    return prompt


@router.post("/{session_id}/quick-prompts/{prompt_id}/close")
async def close_quick_prompt(
    session_id: int,
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    service.require_lecturer(access)
    prompt = await _get_quick_prompt(db, session_id, prompt_id)
    prompt.status = "closed"
    prompt.closed_at = prompt.closed_at or now_myt()
    await db.flush()
    service.queue_event(db, session_id, "interaction.quick_prompts_changed")
    return _find(await service.quick_prompt_list(db, access), prompt.id)


@router.post("/{session_id}/quick-prompts/{prompt_id}/answers")
async def answer_quick_prompt(
    session_id: int,
    prompt_id: int,
    body: QuickAnswerCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    student = service.require_student(access)
    prompt = await _get_quick_prompt(db, session_id, prompt_id)
    if prompt.status != "open":
        raise HTTPException(status_code=409, detail="Quick question is closed")
    if len(body.text) > prompt.max_length:
        raise HTTPException(status_code=422, detail=f"Answer must be at most {prompt.max_length} characters")
    answer = await db.scalar(select(InteractionQuickAnswer).where(
        InteractionQuickAnswer.quick_prompt_id == prompt.id,
        InteractionQuickAnswer.student_id == student.id,
    ))
    changed = answer is None or answer.text != body.text
    if answer is None:
        answer = InteractionQuickAnswer(quick_prompt_id=prompt.id, student_id=student.id, text=body.text)
        db.add(answer)
        event_kind = "quick_answer.submitted"
    else:
        answer.text = body.text
        answer.updated_at = now_myt()
        event_kind = "quick_answer.revised"
    if changed:
        db.add(InteractionEvent(
            attendance_session_id=session_id,
            student_id=student.id,
            kind=event_kind,
            quick_prompt_id=prompt.id,
        ))
        await db.flush()
        service.queue_event(db, session_id, "interaction.quick_answers_changed", roles=("lecturer",))
    return {"id": answer.id, "quick_prompt_id": prompt.id, "text": answer.text}


@router.get("/{session_id}/quick-prompts/{prompt_id}/answers")
async def quick_answers(
    session_id: int,
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id)
    service.require_lecturer(access)
    await _get_quick_prompt(db, session_id, prompt_id)
    rows = (await db.execute(
        select(InteractionQuickAnswer, User.name)
        .join(Student, Student.id == InteractionQuickAnswer.student_id)
        .join(User, User.id == Student.user_id)
        .where(InteractionQuickAnswer.quick_prompt_id == prompt_id)
        .order_by(InteractionQuickAnswer.created_at)
    )).all()
    return [{"id": answer.id, "student_name": name, "text": answer.text,
             "created_at": answer.created_at} for answer, name in rows]


@router.post("/{session_id}/reactions", status_code=status.HTTP_201_CREATED)
async def react(
    session_id: int,
    body: ReactionCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    student = service.require_student(access)
    await service.enforce_cooldown(
        db, session_id=session_id, student_id=student.id,
        kind="reaction.sent", seconds=settings.INTERACTION_REACTION_COOLDOWN_SECONDS,
    )
    event = InteractionEvent(
        attendance_session_id=session_id,
        student_id=student.id,
        kind="reaction.sent",
        reaction=body.kind,
    )
    db.add(event)
    await db.flush()
    service.queue_event(db, session_id, "interaction.signals_changed", roles=("lecturer",))
    return {"accepted": True, "reaction": body.kind, "occurred_at": event.occurred_at}


@router.post("/{session_id}/confusion", status_code=status.HTTP_201_CREATED)
async def report_confusion(
    session_id: int,
    body: ConfusionCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id, lock=True)
    service.require_open(access)
    student = service.require_student(access)
    await service.enforce_cooldown(
        db, session_id=session_id, student_id=student.id,
        kind="confusion.reported", seconds=settings.INTERACTION_CONFUSION_COOLDOWN_SECONDS,
    )
    crossed, live_count = await service.confusion_crosses_threshold(
        db, session_id=session_id, occurrence_id=access.session.occurrence_id, student_id=student.id
    )
    event = InteractionEvent(
        attendance_session_id=session_id,
        student_id=student.id,
        kind="confusion.reported",
        topic_tag=body.topic_tag,
    )
    db.add(event)
    await db.flush()
    service.queue_event(db, session_id, "interaction.signals_changed", roles=("lecturer",))
    if crossed:
        lecturer_user = await service.lecturer_user_id(db, access.session)
        payload = {
            "session_id": session_id,
            "window_key": f"{session_id}:{event.id}",
            "message": (f"{live_count} student needs clarification" if live_count == 1
                        else f"{live_count} students need clarification"),
            "link": f"/interaction/sessions/{session_id}",
        }

        async def _notify() -> None:
            await notify.emit("confusion.spike", [lecturer_user] if lecturer_user else [], payload)

        after_commit(db, _notify)
    return {"accepted": True, "occurred_at": event.occurred_at}


@router.get("/{session_id}/signals")
async def signals(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id)
    service.require_lecturer(access)
    return await service.signal_summary(db, session_id)


@router.get("/{session_id}/summary")
async def summary(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    access = await _access(db, actor, session_id)
    service.require_lecturer(access)
    if access.session.status == "open":
        raise HTTPException(status_code=409, detail="Summary is available after the class ends")
    questions = await service.question_list(db, access)
    polls = await service.poll_list(db, access)
    signals_data = await service.signal_summary(db, session_id)
    return {
        "attendance_session_id": session_id,
        "questions_asked": len(questions),
        "questions_answered": sum(1 for question in questions if question["answered"]),
        "polls": polls,
        **signals_data,
    }


@router.websocket("/{session_id}/ws")
async def interaction_ws(session_id: int, websocket: WebSocket, token: str = Query(...)):
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        await websocket.close(code=1008)
        return
    if payload.get("type") != "access" or payload.get("role") not in ("lecturer", "student"):
        await websocket.close(code=1008)
        return
    async with AsyncSessionLocal() as db:
        actor = await db.scalar(select(User).where(User.id == user_id, User.status == "active"))
        if actor is None or payload.get("role") != actor.role:
            await websocket.close(code=1008)
            return
        try:
            access = await service.authorize(db, actor, session_id)
        except HTTPException:
            await websocket.close(code=1008)
            return
        role = "lecturer" if access.is_lecturer else "student"

    await manager.connect_interaction(session_id, role, websocket)
    try:
        # Register before the locked bootstrap. A concurrent close either happens first and is
        # reflected here, or waits for this state message then broadcasts the close afterwards.
        async with AsyncSessionLocal() as db:
            actor = await db.scalar(select(User).where(User.id == user_id, User.status == "active"))
            if actor is None:
                await websocket.close(code=1008)
                return
            try:
                fresh = await service.authorize(db, actor, session_id, lock=True)
            except HTTPException:
                await websocket.close(code=1008)
                return
            await websocket.send_json({
                "event": "interaction.state",
                "attendance_session_id": session_id,
                "status": fresh.session.status,
            })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_interaction(session_id, role, websocket)

