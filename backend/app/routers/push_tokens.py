"""Device push tokens for the phone apps (FR-210, FR-212) — S13.

The apps register their Expo push token after sign-in and remove it on logout. One row per
device: the token is unique, so registering a token that another account used on the same phone
moves it to the caller. A user can only remove their own token (anyone else's answers 404).
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import case, delete, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.timezone import now_myt
from app.models.push_token import PushToken
from app.models.user import User
from app.schemas.notification import PushTokenIn, PushTokenOut

router = APIRouter(prefix="/me/push-tokens", tags=["notifications"])


@router.post("", response_model=PushTokenOut)
async def register_push_token(
    body: PushTokenIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Register (or refresh) this device's Expo push token for the caller. 201 when new, else 200."""
    now = now_myt()
    table = PushToken.__table__
    stmt = pg_insert(table).values(user_id=actor.id, token=body.token, platform=body.platform,
                                   created_at=now, last_seen_at=now)
    # One atomic upsert, so two first registrations of the same token can't race. On a token
    # another account used on this phone, the device follows the sign-in (created_at restarts).
    stmt = stmt.on_conflict_do_update(
        index_elements=[table.c.token],
        set_={
            "user_id": stmt.excluded.user_id,
            "platform": stmt.excluded.platform,
            "last_seen_at": stmt.excluded.last_seen_at,
            "created_at": case((table.c.user_id == stmt.excluded.user_id, table.c.created_at),
                               else_=stmt.excluded.created_at),
        },
    ).returning(table.c.token, table.c.platform, table.c.created_at, table.c.last_seen_at,
                literal_column("(xmax = 0)").label("inserted"))
    row = (await db.execute(stmt)).one()
    await db.commit()
    if row.inserted:
        response.status_code = status.HTTP_201_CREATED
    return PushTokenOut(token=row.token, platform=row.platform, created_at=row.created_at,
                        last_seen_at=row.last_seen_at)


@router.delete("/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_push_token(
    token: str,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Remove one of the caller's push tokens (logout). Someone else's or an unknown token: 404."""
    result = await db.execute(
        delete(PushToken).where(PushToken.token == token, PushToken.user_id == actor.id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Push token not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
