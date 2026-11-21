"""Lecturer announcements (FR-217, UC: New announcement) — S17.

`create` stores the announcement and, after the request's commit, notifies the class's active
enrolled students through `notify.emit("announcement.posted", ...)` (priority *important*, set by
the registry). With `post_to_moodle` the row is queued (`moodle_status = "pending"`): one try
starts in the background right after the commit, and `announcement_moodle_loop` retries due rows
after RETRY_BASE * 2^(attempts-1) seconds (capped) until ANNOUNCEMENT_MOODLE_MAX_ATTEMPTS tries
have failed (`failed`). The queue lives in the table, so it survives a restart.

The post uses the SmartClass service token (the lecturer's Moodle token is never stored, NFR-05),
so Moodle shows the service account as the author; the message names the lecturer. Each post
carries a marker; a retry first looks for it in the forum, so a post whose reply was lost is not
posted twice. Errors keep only a Moodle error code or exception class (no tokens, no URLs).
"""
from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, after_commit
from app.core.timezone import now_myt
from app.models.announcement import Announcement
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.user import Student, User
from app.services import notify
from app.services.audit_service import write_log
from app.services.kb.moodle_client import MoodleClient, MoodleError

log = logging.getLogger(__name__)

EVENT = "announcement.posted"
_DISCUSSIONS_CHECKED = 50        # newest forum discussions searched for a lost post's marker

_run_lock = asyncio.Lock()       # one Moodle post at a time (never the same row twice)
_tasks: set[asyncio.Task] = set()


class PostError(Exception):
    """A Moodle post problem worth showing the lecturer (a short code, no secrets)."""


def clock() -> datetime:
    """Current naive MYT time. Tests monkeypatch this (controlled clock)."""
    return now_myt()


def retry_delay(attempts: int) -> timedelta:
    """Wait before try number `attempts + 1`, after `attempts` failed tries (attempts >= 1)."""
    seconds = settings.ANNOUNCEMENT_MOODLE_RETRY_BASE_SECONDS * 2 ** max(0, attempts - 1)
    return timedelta(seconds=min(seconds, settings.ANNOUNCEMENT_MOODLE_RETRY_MAX_SECONDS))


def marker(announcement_id: int) -> str:
    return f"(SmartClass announcement #{announcement_id})"


def moodle_link(discussion_id: int | None) -> str | None:
    if discussion_id is None:
        return None
    base = (settings.MOODLE_PUBLIC_URL or settings.MOODLE_URL).rstrip("/")
    return f"{base}/mod/forum/discuss.php?d={discussion_id}"


async def recipients(db: AsyncSession, occurrence_id: int) -> list[int]:
    """users.id of the active students enrolled in the class."""
    rows = await db.execute(
        select(User.id)
        .join(Student, Student.user_id == User.id)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.occurrence_id == occurrence_id, User.status == "active",
               User.role == "student")
        .order_by(User.id)
    )
    return list(rows.scalars())


async def create(db: AsyncSession, actor: User, occurrence: ClassOccurrence, title: str,
                 message: str, post_to_moodle: bool) -> Announcement:
    """Store the announcement (the caller has checked the actor teaches the class). The
    notifications and the first Moodle try run after the caller's commit."""
    course = await db.get(Course, occurrence.course_id)
    student_ids = await recipients(db, occurrence.id)
    row = Announcement(
        occurrence_id=occurrence.id, course_id=occurrence.course_id, author_user_id=actor.id,
        title=title, message=message, recipient_count=len(student_ids),
        moodle_status="pending" if post_to_moodle else "not_requested", moodle_attempts=0,
        moodle_next_at=clock() if post_to_moodle else None,
    )
    db.add(row)
    await db.flush()
    await write_log(db, actor.id, "ANNOUNCEMENT_SEND", "class_occurrence", occurrence.id,
                    new_val={"announcement_id": row.id, "recipients": len(student_ids),
                             "post_to_moodle": post_to_moodle})
    payload = {"announcement_id": row.id, "title": title, "message": message,
               "course_code": course.code if course else None}
    announcement_id = row.id

    async def _after() -> None:
        await notify.emit(EVENT, student_ids, payload)
        if post_to_moodle:
            schedule(announcement_id)

    after_commit(db, _after)
    return row


# ── Moodle post ─────────────────────────────────────────────────────────────────

def _body(row: Announcement, author: str | None) -> str:
    text = html.escape(row.message).replace("\r\n", "\n").replace("\n", "<br>")
    by = f"Posted by {html.escape(author)} via SmartClass" if author else "Posted via SmartClass"
    return f"<p>{text}</p><p><small>{by} {marker(row.id)}</small></p>"


def _error_text(exc: Exception) -> str:
    # Moodle errors are "<function>: <errorcode> - <message>"; httpx errors can carry the URL with
    # the token, so only their class name is kept (NFR-08)
    if isinstance(exc, (PostError, MoodleError)):
        return str(exc)[:255]
    return exc.__class__.__name__


async def _news_forum(client: MoodleClient, course: Course) -> int:
    course_id = course.moodle_course_id or await client.get_course_id(course.code)
    if course_id is None:
        raise PostError(f"Course {course.code} is not in Moodle")
    forums = await client.call("mod_forum_get_forums_by_courses", **{"courseids[0]": int(course_id)})
    if not isinstance(forums, list):
        raise PostError("Moodle returned no forum list")
    for forum in forums:
        if forum.get("type") == "news" and int(forum.get("course") or 0) == int(course_id):
            return int(forum["id"])
    raise PostError(f"Moodle course {course.code} has no announcements forum")


async def _already_posted(client: MoodleClient, forum_id: int, announcement_id: int) -> int | None:
    body = await client.call("mod_forum_get_forum_discussions", forumid=forum_id, page=0,
                             perpage=_DISCUSSIONS_CHECKED)
    if not isinstance(body, dict) or not isinstance(body.get("discussions"), list):
        raise PostError("Moodle returned no discussion list")
    mark = marker(announcement_id)
    for item in body["discussions"]:
        if mark in str(item.get("message") or ""):
            return int(item["discussion"])
    return None


async def _post(client: MoodleClient, row: Announcement, course: Course, author: str | None) -> int:
    forum_id = await _news_forum(client, course)
    if row.moodle_attempts > 0:   # an earlier try may have posted before its answer was lost
        found = await _already_posted(client, forum_id, row.id)
        if found is not None:
            return found
    result = await client.call("mod_forum_add_discussion", forumid=forum_id, subject=row.title,
                               message=_body(row, author))
    if not isinstance(result, dict) or not result.get("discussionid"):
        raise PostError("Moodle did not create the discussion")
    return int(result["discussionid"])


async def post_to_moodle(announcement_id: int, now: datetime | None = None) -> str | None:
    """Try to post one pending announcement whose next try is due. Returns its Moodle status
    afterwards (None when the row is gone). Never raises."""
    try:
        async with _run_lock:
            async with AsyncSessionLocal() as db:
                row = await db.get(Announcement, announcement_id, with_for_update=True)
                if row is None:
                    return None
                now = now or clock()
                if row.moodle_status != "pending" or (row.moodle_next_at and row.moodle_next_at > now):
                    return row.moodle_status
                course = await db.get(Course, row.course_id)
                author = (await db.scalar(select(User.name).where(User.id == row.author_user_id))
                          if row.author_user_id else None)
                try:
                    async with MoodleClient(timeout=settings.ANNOUNCEMENT_MOODLE_TIMEOUT_SECONDS) as client:
                        discussion_id = await _post(client, row, course, author)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 - every failure is recorded and retried
                    row.moodle_attempts += 1
                    row.moodle_last_attempt_at = now
                    row.moodle_error = _error_text(exc)
                    if (row.moodle_attempts >= max(1, settings.ANNOUNCEMENT_MOODLE_MAX_ATTEMPTS)
                            or not retries_enabled()):
                        row.moodle_status, row.moodle_next_at = "failed", None
                    else:
                        row.moodle_next_at = now + retry_delay(row.moodle_attempts)
                    log.warning("Moodle post of announcement %s failed (try %s, %s): %s",
                                announcement_id, row.moodle_attempts, row.moodle_status,
                                exc.__class__.__name__)
                else:
                    row.moodle_attempts += 1
                    row.moodle_last_attempt_at = now
                    row.moodle_status, row.moodle_next_at, row.moodle_error = "posted", None, None
                    row.moodle_discussion_id, row.moodle_posted_at = discussion_id, now
                status = row.moodle_status
                await db.commit()
                return status
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - a DB problem leaves the row pending for the loop
        log.warning("Moodle post of announcement %s not tried: %s", announcement_id,
                    exc.__class__.__name__)
        return None


def schedule(announcement_id: int) -> None:
    """Start the first Moodle try in the background. Never raises."""
    try:
        task = asyncio.get_running_loop().create_task(post_to_moodle(announcement_id))
    except RuntimeError:          # no running loop: the retry loop picks it up
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    """Wait for every scheduled Moodle try (tests, shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def run_due(now: datetime | None = None) -> dict[int, str | None]:
    """Try every pending announcement whose next try has come. Returns id -> status."""
    now = now or clock()
    async with AsyncSessionLocal() as db:
        ids = list((await db.execute(
            select(Announcement.id)
            .where(Announcement.moodle_status == "pending",
                   Announcement.moodle_next_at.is_not(None), Announcement.moodle_next_at <= now)
            .order_by(Announcement.moodle_next_at, Announcement.id)
        )).scalars())
    return {i: await post_to_moodle(i, now) for i in ids}


def retries_enabled() -> bool:
    """The retry loop runs only with a Moodle token and a positive interval; without it a failed
    first try is final (so a post never sits in `pending` for ever)."""
    return bool(settings.MOODLE_TOKEN) and settings.ANNOUNCEMENT_MOODLE_INTERVAL_SECONDS > 0


async def announcement_moodle_loop() -> None:
    """Background retry loop started in main.py; off unless `retries_enabled()`."""
    if not retries_enabled():
        return
    while True:
        try:
            results = await run_due()
            if results:
                log.info("Moodle announcement posts: %s", results)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Moodle announcement loop failed: %s", exc.__class__.__name__)
        await asyncio.sleep(settings.ANNOUNCEMENT_MOODLE_INTERVAL_SECONDS)


# ── read side ───────────────────────────────────────────────────────────────────

async def list_for_class(db: AsyncSession, occurrence_id: int) -> list[Announcement]:
    rows = await db.execute(
        select(Announcement).where(Announcement.occurrence_id == occurrence_id)
        .order_by(Announcement.created_at.desc(), Announcement.id.desc())
    )
    return list(rows.scalars())
