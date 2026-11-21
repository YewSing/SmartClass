"""Notification retention (FR-218) — S15.

A daily background job (started in `app/main.py`) deletes notifications older than
`NOTIFICATION_RETENTION_DAYS` (default 90), read or not. `NOTIFICATION_RETENTION_INTERVAL_SECONDS`
<= 0 turns the job off.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.timezone import now_myt
from app.models.notification import Notification

log = logging.getLogger(__name__)


def clock() -> datetime:
    """Current naive MYT time. Tests monkeypatch this (controlled clock)."""
    return now_myt()


async def purge() -> int:
    """Delete notifications created before now - retention days. Returns how many were deleted."""
    days = settings.NOTIFICATION_RETENTION_DAYS
    if days <= 0:          # misconfigured: keep everything rather than delete it all
        log.warning("notification retention: NOTIFICATION_RETENTION_DAYS=%d, nothing deleted", days)
        return 0
    cutoff = clock() - timedelta(days=days)
    async with AsyncSessionLocal() as db:
        result = await db.execute(delete(Notification).where(Notification.created_at < cutoff))
        await db.commit()
    return result.rowcount or 0


async def retention_loop() -> None:
    """Background task started in main.py: purge now, then every interval (daily)."""
    if settings.NOTIFICATION_RETENTION_INTERVAL_SECONDS <= 0:
        return
    while True:
        try:
            deleted = await purge()
            if deleted:
                log.info("notification retention: %d old notifications deleted", deleted)
        except asyncio.CancelledError:
            raise
        except Exception:   # never let the job die on a transient error
            log.exception("notification retention purge failed")
        await _sleep(settings.NOTIFICATION_RETENTION_INTERVAL_SECONDS)


_sleep = asyncio.sleep   # tests replace this (not asyncio.sleep itself)
