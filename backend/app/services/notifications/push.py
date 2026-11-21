"""Expo push for urgent and important notifications (FR-210, FR-212) — S13.

`store.deliver` calls `schedule(ids)` after its commit. The send runs in a background task, so a
slow or unreachable Expo never delays or fails the request that raised the event. Only urgent and
important notifications are pushed (general ones stay in-app), and only to tokens whose platform
is in `PUSH_PLATFORMS` (Android by default: on iOS they arrive in-app and by email, FR-210).

Messages go to `EXPO_PUSH_URL` in batches of at most 100 (Expo's limit). A `DeviceNotRegistered`
ticket deletes that token. Network or HTTP failures are logged (no token, no secret) and dropped.
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Iterable

import httpx
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.notification import Notification
from app.models.push_token import PushToken

log = logging.getLogger(__name__)

PUSHED_PRIORITIES = ("urgent", "important")
BATCH_SIZE = 100
TOKEN_RE = re.compile(r"^Expo(nent)?PushToken\[[A-Za-z0-9_\-]{10,160}\]$")

_tasks: set[asyncio.Task] = set()


def valid_token(token: str) -> bool:
    return bool(TOKEN_RE.fullmatch(token or ""))


def _platforms() -> list[str]:
    return [p.strip() for p in settings.PUSH_PLATFORMS.split(",") if p.strip()]


def schedule(notification_ids: Iterable[int]) -> None:
    """Start pushing these committed notifications in the background. Never raises."""
    ids = sorted(set(notification_ids))
    if not ids or not settings.PUSH_ENABLED:
        return
    try:
        task = asyncio.get_running_loop().create_task(send(ids))
    except RuntimeError:          # no running loop (sync caller): nothing to push from
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    """Wait for every scheduled push (tests, shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def _messages(ids: list[int]) -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Notification, PushToken.token)
            .join(PushToken, PushToken.user_id == Notification.user_id)
            .where(Notification.id.in_(ids),
                   Notification.priority.in_(PUSHED_PRIORITIES),
                   PushToken.platform.in_(_platforms()))
            .order_by(Notification.id, PushToken.id)
        )).all()
    return [
        {
            "to": token,
            "title": n.title,
            "body": n.message,
            "data": {"notification_id": n.id, "event": n.event, "priority": n.priority, "link": n.link},
            "sound": "default",
            "priority": "high",
            "channelId": "default",
        }
        for n, token in rows
    ]


async def _post(client: httpx.AsyncClient, batch: list[dict]) -> list[str]:
    """Send one batch. Returns the tokens Expo says are no longer registered."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if settings.EXPO_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {settings.EXPO_ACCESS_TOKEN}"
    try:
        r = await client.post(settings.EXPO_PUSH_URL, json=batch, headers=headers)
    except httpx.HTTPError as exc:
        log.warning("expo push: %d messages not sent (%s)", len(batch), exc.__class__.__name__)
        return []
    if r.status_code != 200:
        log.warning("expo push: %d messages not sent (HTTP %d)", len(batch), r.status_code)
        return []
    try:
        tickets = r.json().get("data") or []
    except (ValueError, AttributeError):
        log.warning("expo push: unreadable response for %d messages", len(batch))
        return []
    gone: list[str] = []
    failed = 0
    for msg, ticket in zip(batch, tickets):
        if not isinstance(ticket, dict) or ticket.get("status") == "ok":
            continue
        error = (ticket.get("details") or {}).get("error")
        if error == "DeviceNotRegistered":
            gone.append(msg["to"])
        else:
            failed += 1
    if failed:
        log.warning("expo push: %d messages rejected", failed)
    return gone


async def send(notification_ids: Iterable[int]) -> int:
    """Push the urgent/important ones of these notifications to their recipients' devices.
    Returns the number of messages sent to Expo. Never raises."""
    ids = sorted(set(notification_ids))
    try:
        messages = await _messages(ids) if ids else []
        if not messages:
            return 0
        gone: list[str] = []
        async with httpx.AsyncClient(timeout=settings.EXPO_PUSH_TIMEOUT_SECONDS) as client:
            for start in range(0, len(messages), BATCH_SIZE):
                gone += await _post(client, messages[start:start + BATCH_SIZE])
        if gone:
            async with AsyncSessionLocal() as db:
                await db.execute(delete(PushToken).where(PushToken.token.in_(gone)))
                await db.commit()
            log.info("expo push: %d unregistered device tokens removed", len(gone))
        return len(messages)
    except Exception as exc:     # push must never fail the event that was stored
        log.warning("expo push failed: %s", exc.__class__.__name__)
        return 0
