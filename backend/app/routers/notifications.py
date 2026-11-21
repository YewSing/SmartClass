"""In-app notification feed and read state (FR-208, FR-209) — S11.

Any signed-in active user (student, lecturer, admin) reads and marks only their own
notifications. Someone else's notification answers 404, the same as one that doesn't exist, so
ids can't be probed.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import FeedOut, NotificationOut, PriorityOut, ReadAllOut, ReadOut
from app.services.notifications import feed

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id, event=n.event, priority=n.priority, title=n.title, message=n.message,
        link=n.link, read=n.read_at is not None, read_at=n.read_at, created_at=n.created_at,
    )


@router.get("", response_model=FeedOut)
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """The caller's feed, newest first, with read state and the total unread count (FR-209)."""
    try:
        rows, next_cursor = await feed.page(db, actor.id, limit, cursor)
    except feed.BadCursor:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid cursor")
    return FeedOut(items=[_out(n) for n in rows], next_cursor=next_cursor,
                   unread_count=await feed.unread_count(db, actor.id))


@router.get("/priority", response_model=PriorityOut)
async def priority_notifications(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Unread urgent and important notifications for the top of the dashboard (FR-208)."""
    rows = await feed.pinned(db, actor.id)
    return PriorityOut(items=[_out(n) for n in rows], unread_count=await feed.unread_count(db, actor.id))


@router.post("/read-all", response_model=ReadAllOut)
async def read_all(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Mark all of the caller's notifications read (FR-209)."""
    marked = await feed.mark_all_read(db, actor.id)
    return ReadAllOut(marked=marked, unread_count=await feed.unread_count(db, actor.id))


@router.post("/{notification_id}/read", response_model=ReadOut)
async def read_one(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Mark one of the caller's notifications read (FR-209). Idempotent."""
    n = await feed.mark_read(db, actor.id, notification_id)
    if n is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return ReadOut(notification=_out(n), unread_count=await feed.unread_count(db, actor.id))
