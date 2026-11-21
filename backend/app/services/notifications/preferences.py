"""Notification preferences (FR-214) — S15.

A user can choose whether **general** notifications are also pushed and emailed. Urgent and
important ones are always pushed (Android) and emailed and can't be turned off. General push and
email are off until the user turns them on (FR-210/FR-211 send only urgent/important by default).

`push.py` and `mailer.py` call `channel_filter` in their queries, so a general notification goes
out on a channel only to recipients who have that channel on.
"""
from __future__ import annotations

from sqlalchemy import exists, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_myt
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference

ALWAYS_ON = ("urgent", "important")     # FR-214: can't be turned off
_COLUMN = {"push": NotificationPreference.push_general, "email": NotificationPreference.email_general}


def channel_filter(channel: str):
    """SQL condition on `Notification`: urgent/important, or general with `channel` turned on."""
    opted_in = exists().where(NotificationPreference.user_id == Notification.user_id,
                              _COLUMN[channel].is_(True))
    return or_(Notification.priority.in_(ALWAYS_ON),
               (Notification.priority == "general") & opted_in)


def to_dict(push_general: bool, email_general: bool) -> dict:
    return {
        "push": {"urgent": True, "important": True, "general": push_general},
        "email": {"urgent": True, "important": True, "general": email_general},
    }


async def get(db: AsyncSession, user_id: int) -> dict:
    row = await db.get(NotificationPreference, user_id)
    return to_dict(bool(row and row.push_general), bool(row and row.email_general))


async def set_general(db: AsyncSession, user_id: int, *, push: bool | None, email: bool | None) -> dict:
    """Save the general push/email choices (None = keep). Caller commits."""
    current = await get(db, user_id)
    push_general = current["push"]["general"] if push is None else push
    email_general = current["email"]["general"] if email is None else email
    table = NotificationPreference.__table__
    stmt = pg_insert(table).values(user_id=user_id, push_general=push_general,
                                   email_general=email_general, updated_at=now_myt())
    stmt = stmt.on_conflict_do_update(
        index_elements=[table.c.user_id],
        set_={"push_general": stmt.excluded.push_general, "email_general": stmt.excluded.email_general,
              "updated_at": stmt.excluded.updated_at},
    )
    await db.execute(stmt)
    return to_dict(push_general, email_general)
