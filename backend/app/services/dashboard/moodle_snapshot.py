"""Moodle announcements and deadlines on login (FR-203) — S16.

On a successful Moodle login the route calls `refresh_on_login(user_id, profile)` once, after its
own commit. With the user's own transient token (never stored or logged, NFR-05) it reads:

- announcements: discussions of each course's news forum (`mod_forum_get_forums_by_courses`,
  `mod_forum_get_forum_discussions`);
- deadlines: course events from now to `MOODLE_SNAPSHOT_DEADLINE_DAYS` ahead, which include
  assignment due dates (`core_calendar_get_calendar_events`).

The result replaces the user's row in `m2_moodle_snapshot` all at once. Any Moodle failure,
warning, timeout or DB error keeps the previous snapshot and never fails the login. Manual and
scheduled course syncs never call this (FR-203). Read side: `get_snapshot` (S18 dashboard).
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.timezone import MYT
from app.models.moodle_snapshot import MoodleSnapshot
from app.services.kb.moodle_client import MoodleClient

log = logging.getLogger(__name__)

_PER_FORUM = 10          # newest discussions read per news forum
_TITLE_MAX = 255
_TAG = re.compile(r"<[^>]*>")


class SnapshotIncomplete(Exception):
    """Moodle answered, but not with everything (warnings or an unexpected shape)."""


def clock() -> datetime:
    """Current aware UTC time. Tests monkeypatch this (controlled clock)."""
    return datetime.now(timezone.utc)


def _text(value, fallback: str) -> str:
    text = html.unescape(_TAG.sub("", str(value or ""))).strip()
    text = " ".join(text.split())
    return (text or fallback)[:_TITLE_MAX]


def _iso(epoch) -> str | None:
    try:
        seconds = int(epoch)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    return datetime.fromtimestamp(seconds, MYT).isoformat()


def _link_base() -> str:
    return (settings.MOODLE_PUBLIC_URL or settings.MOODLE_URL).rstrip("/")


def _check(body, key: str) -> list:
    if not isinstance(body, dict) or not isinstance(body.get(key), list):
        raise SnapshotIncomplete(f"no {key} list")
    if body.get("warnings"):
        raise SnapshotIncomplete(f"{key}: {len(body['warnings'])} warning(s)")
    return body[key]


async def fetch(client: MoodleClient, courses: list) -> dict:
    """Announcements (newest first) and upcoming deadlines (soonest first) for `courses`
    (moodle_sync.MoodleCourse items: id, shortname, fullname). Raises on any incomplete answer."""
    by_id = {int(c.id): c for c in courses}
    if not by_id:
        return {"announcements": [], "deadlines": []}
    ids = sorted(by_id)
    base = _link_base()

    def course_fields(course_id: int) -> dict:
        c = by_id[course_id]
        return {"course_id": course_id, "course_code": c.shortname, "course_name": c.fullname}

    announcements: list[dict] = []
    forums = await client.call("mod_forum_get_forums_by_courses",
                               **{f"courseids[{i}]": cid for i, cid in enumerate(ids)})
    if not isinstance(forums, list):
        raise SnapshotIncomplete("no forum list")
    for forum in forums:
        course_id = forum.get("course")
        if forum.get("type") != "news" or course_id not in by_id:
            continue
        body = await client.call("mod_forum_get_forum_discussions", forumid=int(forum["id"]),
                                 page=0, perpage=_PER_FORUM)
        for item in _check(body, "discussions"):
            discussion = int(item["discussion"])
            announcements.append({
                **course_fields(course_id),
                "id": discussion,
                "title": _text(item.get("name") or item.get("subject"), "Announcement"),
                "date": _iso(item.get("created") or item.get("timemodified")),
                "link": f"{base}/mod/forum/discuss.php?d={discussion}",
            })

    now = clock()
    start = int(now.timestamp())
    end = int((now + timedelta(days=settings.MOODLE_SNAPSHOT_DEADLINE_DAYS)).timestamp())
    body = await client.call("core_calendar_get_calendar_events", **{
        **{f"events[courseids][{i}]": cid for i, cid in enumerate(ids)},
        "options[userevents]": 0, "options[siteevents]": 0,
        "options[timestart]": start, "options[timeend]": end,
    })
    deadlines: list[dict] = []
    for item in _check(body, "events"):
        course_id = item.get("courseid")
        timestart = int(item.get("timestart") or 0)
        if course_id not in by_id or not item.get("visible", 1) or not start <= timestart <= end:
            continue
        deadlines.append({
            **course_fields(course_id),
            "id": int(item["id"]),
            "title": _text(item.get("name"), "Deadline"),
            "type": item.get("modulename") or item.get("eventtype") or None,
            "date": _iso(timestart),
            "link": f"{base}/calendar/view.php?view=day&course={course_id}&time={timestart}",
        })

    limit = max(0, settings.MOODLE_SNAPSHOT_MAX_ITEMS)
    announcements.sort(key=lambda a: (a["date"] or "", a["id"]), reverse=True)
    deadlines.sort(key=lambda d: (d["date"] or "", d["id"]))
    return {"announcements": announcements[:limit], "deadlines": deadlines[:limit]}


async def _save(user_id: int, data: dict) -> None:
    refreshed_at = clock().astimezone(MYT).replace(tzinfo=None)
    stmt = insert(MoodleSnapshot).values(user_id=user_id, announcements=data["announcements"],
                                         deadlines=data["deadlines"], refreshed_at=refreshed_at)
    stmt = stmt.on_conflict_do_update(
        index_elements=[MoodleSnapshot.user_id],
        set_={"announcements": stmt.excluded.announcements, "deadlines": stmt.excluded.deadlines,
              "refreshed_at": stmt.excluded.refreshed_at},
    )
    async with AsyncSessionLocal() as db:
        await db.execute(stmt)
        await db.commit()


async def _refresh(user_id: int, token: str, courses: list) -> None:
    async with MoodleClient(token=token, timeout=settings.MOODLE_SNAPSHOT_TIMEOUT_SECONDS) as client:
        data = await fetch(client, courses)
    await _save(user_id, data)


async def refresh_on_login(user_id: int, profile) -> bool:
    """Refresh the user's snapshot with `profile.moodle_token`, then drop the token from the
    profile. Never raises; returns whether a new snapshot was saved."""
    token = getattr(profile, "moodle_token", None)
    try:
        profile.moodle_token = None
    except AttributeError:
        pass
    if not token:
        # MoodleClient would fall back to the service token, which can see every course
        return False
    courses = list(getattr(profile, "courses", None) or [])
    try:
        await asyncio.wait_for(_refresh(user_id, token, courses),
                               timeout=settings.MOODLE_SNAPSHOT_TIMEOUT_SECONDS)
        return True
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - login must never fail because of the snapshot
        # Only the class name: messages or URLs could echo request data
        log.warning("Moodle snapshot not refreshed for user %s (%s); previous snapshot kept",
                    user_id, exc.__class__.__name__)
        return False


async def get_snapshot(db: AsyncSession, user_id: int) -> dict | None:
    """The user's saved snapshot, or None before their first successful refresh."""
    row = (await db.execute(select(MoodleSnapshot).where(MoodleSnapshot.user_id == user_id))).scalar_one_or_none()
    if row is None:
        return None
    return {"announcements": list(row.announcements or []), "deadlines": list(row.deadlines or []),
            "refreshed_at": row.refreshed_at}
