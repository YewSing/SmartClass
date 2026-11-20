from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def feed(limit: int = Query(50, ge=1, le=200), before_id: int | None = Query(None, ge=1),
               db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(Notification).where(Notification.user_id == user.id)
    if before_id is not None:
        query = query.where(Notification.id < before_id)
    return (await db.scalars(query.order_by(Notification.id.desc()).limit(limit))).all()


@router.post("/read-all", status_code=204)
async def read_all(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
                     .values(read_at=datetime.now(timezone.utc)))
    return Response(status_code=204)


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def read_one(notification_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    note = await db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id).with_for_update())
    if note is None:
        raise HTTPException(404, "Notification not found")
    if note.read_at is None:
        note.read_at = datetime.now(timezone.utc)
    await db.flush()
    return note
