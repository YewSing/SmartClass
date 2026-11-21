"""Per-user notification feed and read state (FR-208, FR-209) — S11.

Every query here is scoped to one `user_id` (users.id); callers pass the signed-in user's id,
never one from the request. Order is newest first by (created_at, id), paged with an opaque
keyset cursor so new notifications arriving between pages never cause gaps or repeats.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.schemas.notification import NotificationOut
from app.services.notifications import store

PINNED = ("urgent", "important")      # FR-208: shown at the top of the dashboard until read
PRIORITY_LIMIT = 50


class BadCursor(ValueError):
    pass


def out(n: Notification) -> NotificationOut:
    """The API shape of a notification (feed, read endpoints and the live channel)."""
    return NotificationOut(
        id=n.id, event=n.event, priority=n.priority, title=n.title, message=n.message,
        link=n.link, read=n.read_at is not None, read_at=n.read_at, created_at=n.created_at,
    )


def encode_cursor(n: Notification) -> str:
    raw = f"{n.created_at.isoformat()}|{n.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        when, _, nid = raw.partition("|")
        return datetime.fromisoformat(when), int(nid)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise BadCursor("invalid cursor") from exc


async def unread_count(db: AsyncSession, user_id: int) -> int:
    return await db.scalar(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    ) or 0


async def page(db: AsyncSession, user_id: int, limit: int,
               cursor: Optional[str] = None) -> tuple[list[Notification], Optional[str]]:
    """One page of the user's feed, newest first, and the cursor for the next page (or None)."""
    q = select(Notification).where(Notification.user_id == user_id)
    if cursor is not None:
        when, nid = decode_cursor(cursor)
        q = q.where(or_(Notification.created_at < when,
                        and_(Notification.created_at == when, Notification.id < nid)))
    q = q.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
    rows = list((await db.scalars(q)).all())
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, (encode_cursor(rows[-1]) if more and rows else None)


async def pinned(db: AsyncSession, user_id: int) -> list[Notification]:
    """Unread urgent then important notifications, newest first within each (FR-208)."""
    q = (
        select(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None),
               Notification.priority.in_(PINNED))
        .order_by(case((Notification.priority == "urgent", 0), else_=1),
                  Notification.created_at.desc(), Notification.id.desc())
        .limit(PRIORITY_LIMIT)
    )
    return list((await db.scalars(q)).all())


async def mark_read(db: AsyncSession, user_id: int, notification_id: int) -> Optional[Notification]:
    """Mark one of the user's notifications read; None if it isn't theirs (or doesn't exist).
    Idempotent: an already-read notification keeps its first `read_at`."""
    n = await db.scalar(select(Notification).where(
        Notification.id == notification_id, Notification.user_id == user_id))
    if n is None:
        return None
    if n.read_at is None:
        n.read_at = store.clock()
        await db.commit()
        await db.refresh(n)
    return n


async def mark_all_read(db: AsyncSession, user_id: int) -> int:
    """Mark every unread notification of the user read. Returns how many changed."""
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=store.clock())
    )
    await db.commit()
    return result.rowcount or 0
