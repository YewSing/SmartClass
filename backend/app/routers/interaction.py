"""Classroom interaction session (FR-501, FR-502) — S30.

`GET /interaction/{attendance_session_id}` joins (teaching lecturer or enrolled student, 403
otherwise). The lecturer can close the interaction early and reopen it while the class runs; it
closes by itself when the class session ends. Questions, polls etc. (S31–S33) hang off this.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User
from app.schemas.interaction import (
    InteractionSessionOut,
    QuestionCreate,
    QuestionListOut,
    QuestionModerate,
    QuestionOut,
)
from app.services.interaction import questions, sessions

router = APIRouter(tags=["interaction"])


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


@router.post("/lecturer/interaction/{attendance_session_id}/open", response_model=InteractionSessionOut)
async def open_interaction(
    attendance_session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Reopen the interaction of a class that is running (409 once the class isn't open)."""
    session, member = await sessions.authorize(db, actor, attendance_session_id)
    await sessions.open_interaction(db, actor, attendance_session_id)
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
