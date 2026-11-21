"""Notification preferences for the caller (FR-214) — S15.

Only general notifications have a choice: push and email for them can be turned on or off.
Urgent and important ones are always delivered; sending `false` for them answers 422.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationPrefsIn, NotificationPrefsOut
from app.services.notifications import preferences

router = APIRouter(prefix="/me/notification-preferences", tags=["notifications"])


@router.get("", response_model=NotificationPrefsOut)
async def get_preferences(db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    return await preferences.get(db, actor.id)


@router.put("", response_model=NotificationPrefsOut)
async def put_preferences(
    body: NotificationPrefsIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Save the caller's general push/email choice. Omitted fields keep their value."""
    saved = await preferences.set_general(
        db, actor.id,
        push=body.push.general if body.push else None,
        email=body.email.general if body.email else None,
    )
    await db.commit()
    return saved
