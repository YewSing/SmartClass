"""In-app notification feed, read state and live channel (FR-208, FR-209, FR-213) — S11, S12.

Any signed-in active user (student, lecturer, admin) reads and marks only their own
notifications. Someone else's notification answers 404, the same as one that doesn't exist, so
ids can't be probed. `WS /notifications/ws` pushes the user's new notifications and unread count.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, after_commit, get_db
from app.core.deps import get_current_user
from app.core.security import decode_token
from app.models.user import User
from app.schemas.notification import FeedOut, PriorityOut, ReadAllOut, ReadOut, TestSendOut
from app.services.notifications import feed, live, store

router = APIRouter(prefix="/notifications", tags=["notifications"])

_out = feed.out


def _announce_count(db: AsyncSession, user_id: int) -> None:
    """After the commit, tell the user's open screens their new unread count (FR-213)."""
    after_commit(db, lambda: live.publish_unread_count(user_id))


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
    if marked:
        _announce_count(db, actor.id)
    return ReadAllOut(marked=marked, unread_count=await feed.unread_count(db, actor.id))


@router.post("/test", response_model=TestSendOut)
async def send_test(actor: User = Depends(get_current_user)):
    """Send the caller a test notification (S19): it arrives like a real important one (feed, live,
    push, email), so a user can check a device. At most one per minute (the event's window)."""
    ids = await store.deliver("notification.test", [actor.id], {})
    return TestSendOut(sent=bool(ids))


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
    _announce_count(db, actor.id)
    return ReadOut(notification=_out(n), unread_count=await feed.unread_count(db, actor.id))


async def _ws_user(token: Optional[str]) -> Optional[int]:
    """The active user an access token belongs to, or None (bad, expired, refresh, inactive)."""
    payload = decode_token(token) if token else {}
    if payload.get("type") != "access":
        return None
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or user.status != "active" or user.role != payload.get("role"):
        return None
    return user_id


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: Optional[str] = Query(None)):
    """Live notifications for the signed-in user (FR-213). `?token=<access JWT>`.

    Messages: `{type:"connected", unread_count}` once, then `{type:"notification", notification,
    unread_count}` for each new one and `{type:"unread_count", unread_count}` after a read. A bad
    or expired token is accepted and then closed with 1008, so the client sees the reason. Nothing
    is replayed on reconnect: the client re-reads `GET /notifications`."""
    user_id = await _ws_user(token)
    await websocket.accept()
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    async with AsyncSessionLocal() as db:
        count = await feed.unread_count(db, user_id)
    live.hub.add(user_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "unread_count": count})
        while True:            # the server drives every message; client text is ignored
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        live.hub.remove(user_id, websocket)
