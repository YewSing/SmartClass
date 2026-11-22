"""Classroom interaction session (FR-501, FR-502) — S30.

`GET /interaction/{attendance_session_id}` joins (teaching lecturer or enrolled student, 403
otherwise). The lecturer can close the interaction early and reopen it while the class runs; it
closes by itself when the class session ends. Questions, polls etc. (S31–S33) hang off this.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.core.deps import require_role
from app.core.security import decode_token
from app.models.user import User
from app.schemas.interaction import (
    ConfusionAck,
    ConfusionIn,
    ConfusionOut,
    InteractionSessionOut,
    PollCreate,
    PollListOut,
    PollOut,
    PollUpdate,
    PollVoteIn,
    QuestionCreate,
    QuestionListOut,
    QuestionModerate,
    QuestionOut,
    QuickAnswerIn,
    QuickQuestionCreate,
    QuickQuestionListOut,
    QuickQuestionOut,
    ReactionAck,
    ReactionCountsOut,
    ReactionIn,
)
from app.services.interaction import live, polls, questions, quick, sessions, signals

router = APIRouter(tags=["interaction"])

_WS_ROLES = (sessions.ROLE_LECTURER, sessions.ROLE_STUDENT)


def _out(st: sessions.InteractionState, member: sessions.Member) -> InteractionSessionOut:
    return InteractionSessionOut(
        attendance_session_id=st.attendance_session_id, occurrence_id=st.occurrence_id,
        course_code=st.course_code, course_name=st.course_name, class_status=st.class_status,
        status=st.status, closed_reason=st.closed_reason, opened_at=st.opened_at,
        closed_at=st.closed_at, role=member.role)


@router.get("/interaction/{attendance_session_id}", response_model=InteractionSessionOut)
async def join_interaction(
    attendance_session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "student")),
):
    """Join the class's interaction: its state (open/closed and why) and the caller's role."""
    session, member = await sessions.authorize(db, actor, attendance_session_id)
    return _out(await sessions.join(db, session), member)


async def _ws_user(db: AsyncSession, token: Optional[str]) -> Optional[User]:
    """The active lecturer/student an access token belongs to, or None."""
    payload = decode_token(token) if token else {}
    if payload.get("type") != "access" or payload.get("role") not in _WS_ROLES:
        return None
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    user = await db.get(User, user_id)
    if user is None or user.status != "active" or user.role != payload.get("role"):
        return None
    return user


@router.websocket("/interaction/{attendance_session_id}/ws")
async def interaction_ws(attendance_session_id: int, websocket: WebSocket,
                         token: Optional[str] = Query(None)):
    """Live updates for one class's interaction (FR-516). `?token=<access JWT>`; only the
    teaching lecturer and enrolled students (anyone else, or a bad token: closed with 1008).

    Messages: `connected` (the join state + role) once, then `changed` {topic}, `opened`, `closed`
    {reason} — invalidations only, so the client re-reads through the REST endpoints (see
    `services/interaction/live.py`). When the class isn't running the socket gets `closed` and is
    closed (1000). Client text is ignored."""
    await websocket.accept()
    async with AsyncSessionLocal() as db:
        actor = await _ws_user(db, token)
        member = st = None
        if actor is not None:
            try:
                session, member = await sessions.authorize(db, actor, attendance_session_id)
                st = await sessions.join(db, session)
                await db.commit()
            except HTTPException:
                member = None
    if member is None or st is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    conn = live.hub.add(attendance_session_id, websocket, member.role)
    try:
        hello = _out(st, member).model_dump(mode="json")
        await websocket.send_json({"type": "connected", **hello})
        if st.class_status != "open":
            await websocket.send_json({"type": "closed", "reason": live.closed_reason(st)})
            live.hub.remove(attendance_session_id, conn)
            await websocket.close(code=1000)
            return
        while True:            # the server drives every message
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        live.hub.remove(attendance_session_id, conn)


@router.post("/lecturer/interaction/{attendance_session_id}/open", response_model=InteractionSessionOut)
async def open_interaction(
    attendance_session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Reopen the interaction of a class that is running (409 once the class isn't open)."""
    session, member = await sessions.authorize(db, actor, attendance_session_id)
    if await sessions.open_interaction(db, actor, attendance_session_id):
        live.opened(db, attendance_session_id)
    return _out(await sessions.state(db, session), member)


@router.post("/lecturer/interaction/{attendance_session_id}/close", response_model=InteractionSessionOut)
async def close_interaction(
    attendance_session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Close the interaction early; the class itself keeps running."""
    session, member = await sessions.authorize(db, actor, attendance_session_id)
    await sessions.close_interaction(db, actor, attendance_session_id)
    return _out(await sessions.state(db, session), member)


# ── live questions (S31, FR-503–FR-506) ─────────────────────────────────────────

@router.get("/interaction/{attendance_session_id}/questions", response_model=QuestionListOut)
async def list_questions(
    attendance_session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "student")),
):
    """Questions pinned first, then by upvotes, then oldest first. Students never get hidden ones."""
    session, member = await sessions.authorize(db, actor, attendance_session_id)
    st = await sessions.state(db, session)
    return QuestionListOut(attendance_session_id=attendance_session_id, status=st.status,
                           questions=await questions.list_questions(db, member, attendance_session_id))


@router.post("/interaction/{attendance_session_id}/questions", response_model=QuestionOut,
             status_code=status.HTTP_201_CREATED)
async def ask_question(
    attendance_session_id: int,
    body: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "student")),
):
    """A student asks a live question, optionally anonymously (409 once the interaction closed)."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await questions.ask(db, member, attendance_session_id, body.text, body.anonymous)


@router.post("/interaction/{attendance_session_id}/questions/{question_id}/upvote", response_model=QuestionOut)
async def upvote_question(
    attendance_session_id: int,
    question_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "student")),
):
    """Upvote once; a repeat changes nothing. Not your own question (409)."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await questions.upvote(db, member, attendance_session_id, question_id)


@router.patch("/lecturer/interaction/{attendance_session_id}/questions/{question_id}",
              response_model=QuestionOut)
async def moderate_question(
    attendance_session_id: int,
    question_id: int,
    body: QuestionModerate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Mark answered, pin or hide (hide/unhide audited)."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await questions.moderate(db, actor, member, attendance_session_id, question_id, body)


# ── live polls (S32, FR-507–FR-509) ─────────────────────────────────────────────

@router.get("/interaction/{attendance_session_id}/polls", response_model=PollListOut)
async def list_polls(
    attendance_session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "student")),
):
    """Newest first. The lecturer also gets drafts and always the counts; students get the counts
    only when the lecturer shows results."""
    session, member = await sessions.authorize(db, actor, attendance_session_id)
    st = await sessions.state(db, session)
    return PollListOut(attendance_session_id=attendance_session_id, status=st.status,
                       polls=await polls.list_polls(db, member, attendance_session_id,
                                                    interaction_open=st.is_open))


@router.post("/lecturer/interaction/{attendance_session_id}/polls", response_model=PollOut,
             status_code=status.HTTP_201_CREATED)
async def create_poll(
    attendance_session_id: int,
    body: PollCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Create a draft poll (2–6 options, single or multiple choice)."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await polls.create(db, actor, member, attendance_session_id, body)


@router.post("/lecturer/interaction/{attendance_session_id}/polls/{poll_id}/start", response_model=PollOut)
async def start_poll(
    attendance_session_id: int,
    poll_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Open the poll for votes; students get a `poll.started` notification."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await polls.start(db, member, attendance_session_id, poll_id)


@router.post("/lecturer/interaction/{attendance_session_id}/polls/{poll_id}/close", response_model=PollOut)
async def close_poll(
    attendance_session_id: int,
    poll_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Stop the voting (idempotent)."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await polls.close(db, member, attendance_session_id, poll_id)


@router.patch("/lecturer/interaction/{attendance_session_id}/polls/{poll_id}", response_model=PollOut)
async def update_poll(
    attendance_session_id: int,
    poll_id: int,
    body: PollUpdate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Show or hide the results to students."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await polls.set_show_results(db, member, attendance_session_id, poll_id, body.show_results)


@router.post("/interaction/{attendance_session_id}/polls/{poll_id}/vote", response_model=PollOut)
async def vote_poll(
    attendance_session_id: int,
    poll_id: int,
    body: PollVoteIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "student")),
):
    """A student's vote; it replaces their earlier vote until the poll closes."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await polls.vote(db, member, attendance_session_id, poll_id, body.option_ids)


# ── quick questions (S33, FR-510) ───────────────────────────────────────────────

@router.get("/interaction/{attendance_session_id}/quick-questions", response_model=QuickQuestionListOut)
async def list_quick_questions(
    attendance_session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "student")),
):
    """Newest first. The lecturer gets every answer (no names); a student only their own."""
    session, member = await sessions.authorize(db, actor, attendance_session_id)
    st = await sessions.state(db, session)
    return QuickQuestionListOut(
        attendance_session_id=attendance_session_id, status=st.status,
        quick_questions=await quick.list_quick(db, member, attendance_session_id, interaction_open=st.is_open))


@router.post("/lecturer/interaction/{attendance_session_id}/quick-questions",
             response_model=QuickQuestionOut, status_code=status.HTTP_201_CREATED)
async def ask_quick_question(
    attendance_session_id: int,
    body: QuickQuestionCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Ask a quick question; it takes answers at once, up to `max_chars` characters each."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await quick.ask(db, actor, member, attendance_session_id, body)


@router.post("/lecturer/interaction/{attendance_session_id}/quick-questions/{quick_question_id}/close",
             response_model=QuickQuestionOut)
async def close_quick_question(
    attendance_session_id: int,
    quick_question_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Stop taking answers (idempotent)."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await quick.close(db, member, attendance_session_id, quick_question_id)


@router.post("/interaction/{attendance_session_id}/quick-questions/{quick_question_id}/answer",
             response_model=QuickQuestionOut)
async def answer_quick_question(
    attendance_session_id: int,
    quick_question_id: int,
    body: QuickAnswerIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "student")),
):
    """A student's short answer; it replaces their earlier one while the question is open."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await quick.answer(db, member, attendance_session_id, quick_question_id, body.text)


# ── reactions and "I don't understand" (S33, FR-511, FR-512, FR-514, FR-515) ─────

@router.post("/interaction/{attendance_session_id}/reactions", response_model=ReactionAck,
             status_code=status.HTTP_201_CREATED)
async def send_reaction(
    attendance_session_id: int,
    body: ReactionIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "student")),
):
    """A student's quick reaction (429 with Retry-After during the cooldown)."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await signals.react(db, member, attendance_session_id, body.kind)


@router.get("/lecturer/interaction/{attendance_session_id}/reactions", response_model=ReactionCountsOut)
async def reaction_counts(
    attendance_session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Running counts per reaction kind."""
    session, member = await sessions.authorize(db, actor, attendance_session_id)
    st = await sessions.state(db, session)
    return await signals.reaction_counts(db, member, attendance_session_id, st.status)


@router.post("/interaction/{attendance_session_id}/confusion", response_model=ConfusionAck,
             status_code=status.HTTP_201_CREATED)
async def press_confusion(
    attendance_session_id: int,
    body: ConfusionIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "student")),
):
    """"I don't understand", optionally with a topic (429 with Retry-After during the cooldown)."""
    _, member = await sessions.authorize(db, actor, attendance_session_id)
    return await signals.press(db, member, attendance_session_id, body.topic)


@router.get("/lecturer/interaction/{attendance_session_id}/confusion", response_model=ConfusionOut)
async def confusion_view(
    attendance_session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Count, recent count, timeline and topics; never who pressed."""
    session, member = await sessions.authorize(db, actor, attendance_session_id)
    st = await sessions.state(db, session)
    return await signals.confusion_view(db, member, session, st.status)
