"""Classroom interaction session (FR-501, FR-502) — S30.

`GET /interaction/{attendance_session_id}` joins (teaching lecturer or enrolled student, 403
otherwise). The lecturer can close the interaction early and reopen it while the class runs; it
closes by itself when the class session ends. Questions, polls etc. (S31–S33) hang off this.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User
from app.schemas.interaction import InteractionSessionOut
from app.services.interaction import sessions

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
