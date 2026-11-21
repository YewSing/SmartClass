"""Live in-app notifications over a websocket (FR-213, NFR-44) — S12.

Every open `WS /notifications/ws` connection of a user is registered here. `publish` is called by
`store.deliver` after its commit and sends each new notification, with the recipient's new unread
count, to that recipient's connections only. Nothing is queued for closed connections: a client
that reconnects re-reads `GET /notifications` and gets the current count in its `connected`
message, never a replay.

The hub lives in the API process (one uvicorn worker, as for M3's channels).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

from fastapi import WebSocket
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.notification import Notification
from app.services.notifications import feed

log = logging.getLogger(__name__)


class NotificationHub:
    """users.id -> that user's open notification sockets."""

    def __init__(self) -> None:
        self._sockets: dict[int, set[WebSocket]] = {}

    def add(self, user_id: int, ws: WebSocket) -> None:
        self._sockets.setdefault(user_id, set()).add(ws)

    def remove(self, user_id: int, ws: WebSocket) -> None:
        sockets = self._sockets.get(user_id)
        if sockets is not None:
            sockets.discard(ws)
            if not sockets:
                self._sockets.pop(user_id, None)

    def is_connected(self, user_id: int) -> bool:
        return bool(self._sockets.get(user_id))

    async def send(self, user_id: int, message: dict) -> None:
        """Send to every open socket of `user_id`; a socket that fails is dropped."""
        for ws in list(self._sockets.get(user_id, ())):
            try:
                await ws.send_json(message)
            except Exception:
                self.remove(user_id, ws)


hub = NotificationHub()


async def publish(notification_ids: Iterable[int]) -> None:
    """Send committed notifications to their recipients' open sockets. Never raises."""
    ids = sorted(set(notification_ids))
    if not ids:
        return
    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.scalars(
                select(Notification).where(Notification.id.in_(ids)).order_by(Notification.id)
            )).all()
            by_user: dict[int, list[Notification]] = {}
            for n in rows:
                if hub.is_connected(n.user_id):
                    by_user.setdefault(n.user_id, []).append(n)
            for user_id, items in by_user.items():
                count = await feed.unread_count(db, user_id)
                for n in items:
                    await hub.send(user_id, {
                        "type": "notification",
                        "notification": feed.out(n).model_dump(mode="json"),
                        "unread_count": count,
                    })
    except Exception as exc:   # live delivery must never fail the event that was stored
        log.warning("live notification publish failed: %s", exc.__class__.__name__)


async def publish_unread_count(user_id: int) -> None:
    """Tell the user's other screens the unread count changed (read / read-all). Never raises."""
    if not hub.is_connected(user_id):
        return
    try:
        async with AsyncSessionLocal() as db:
            count = await feed.unread_count(db, user_id)
        await hub.send(user_id, {"type": "unread_count", "unread_count": count})
    except Exception as exc:
        log.warning("live unread-count publish failed: %s", exc.__class__.__name__)
