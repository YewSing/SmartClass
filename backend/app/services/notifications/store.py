"""Persist notification events (FR-205, FR-209, FR-216) — S10.

`deliver` is what `app.services.notify.emit` calls. It opens its own database session (events are
raised after the caller's commit), stores one row per recipient and drops duplicates: the same
event, recipient and subject inside the event's window (FR-216). After the commit the new rows go
out live to the recipients' open screens (`live.publish`, FR-213).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.timezone import now_myt
from app.models.notification import Notification
from app.models.user import User
from app.services.notifications import registry

log = logging.getLogger(__name__)


def clock() -> datetime:
    """Current naive MYT time. Tests monkeypatch this (controlled clock)."""
    return now_myt()


async def deliver(event: str, user_ids: Iterable[int], payload: dict) -> list[int]:
    """Store `event` for each of `user_ids` (users.id). Returns the new notification ids.

    Unknown events are logged and dropped. Raises `registry.UnsafeLink` for a non app-relative
    link (nothing is stored). Recipients that don't exist and duplicates are skipped."""
    rendered = registry.build(event, payload)
    if rendered is None:
        log.warning("unknown notification event %s dropped", event)
        return []
    ids = sorted({int(u) for u in user_ids})
    if not ids:
        return []

    now = clock()
    async with AsyncSessionLocal() as db:
        # Serialise deliveries of the same (event, subject) so two concurrent emits can't both
        # pass the duplicate check.
        await db.execute(select(func.pg_advisory_xact_lock(
            func.hashtext(f"m2:{rendered.event}:{rendered.subject_key}"))))
        existing = set((await db.scalars(select(User.id).where(User.id.in_(ids)))).all())
        recent = set((await db.scalars(
            select(Notification.user_id).where(
                Notification.user_id.in_(ids),
                Notification.event == rendered.event,
                Notification.subject_key == rendered.subject_key,
                Notification.created_at > now - rendered.window,
            )
        )).all())
        rows = [
            Notification(
                user_id=uid, event=rendered.event, priority=rendered.priority,
                title=rendered.title, message=rendered.message, link=rendered.link,
                subject_key=rendered.subject_key, created_at=now,
            )
            for uid in ids if uid in existing and uid not in recent
        ]
        if len(rows) < len(ids):
            log.info("notify %s: %d duplicate/unknown recipients skipped", event, len(ids) - len(rows))
        db.add_all(rows)
        await db.commit()
        new_ids = [row.id for row in rows]

    # Only after the commit: a client that re-reads its feed on the event must see the row (FR-213).
    from app.services.notifications import live   # lazy: live imports feed, which imports store

    await live.publish(new_ids)
    return new_ids
