"""Notification hook for Module 2 (Dashboard & Notifications, Shino).

Raise an event about a user (`users.id`) here; Module 2 delivers it by push, in-app or
email. The in-app row is written now (FR-205/FR-206, S10); the delivery worker (S11) reads
the unset flags. Never logs the payload: it holds names and matric numbers (NFR-02 / PDPA).

Events raised today:

- `attendance.recorded` -> the student. Payload: `session_id`, `course_code`, `course_name`,
  `status` (`present` | `late`), `detected_at`, `source` (`recognition` | `student_flag`), `message`.
- `quiz.published` -> the course lecturer, priority `important` (FR-211).

The other Module 2 events from the FR doc (`attendance.flagged`, `face_enrolment.*`, see
`docs/requests-for-shino.md` R1) are not raised yet.

Imports from `app` stay lazy inside `emit` so Module 1's import-time cycle rule holds.
"""
import logging
from collections.abc import Iterable

log = logging.getLogger(__name__)

PRIORITIES = ("urgent", "important", "general")


async def emit(event: str, user_ids: Iterable[int], payload: dict | None,
               priority: str = "general") -> list[int]:
    """Store a notification for each of `user_ids` (users.id) and return their ids.

    Callers without a priority default to `general` (feed-only). Delivery flags start unset
    for the S11 worker. A storage failure returns `[]` instead of breaking the action that
    raised the event; an unknown priority is a programming error and raises `ValueError`."""
    if priority not in PRIORITIES:
        raise ValueError(f"unknown notification priority: {priority}")
    try:
        ids = sorted(set(user_ids))
        if not ids:
            return []
        from app.core.database import AsyncSessionLocal
        from app.models.notify import Notification

        async with AsyncSessionLocal() as db:
            rows = [
                Notification(user_id=uid, event=event, priority=priority, payload=payload)
                for uid in ids
            ]
            db.add_all(rows)
            await db.commit()
            created = [row.id for row in rows]
        log.info("notify %s (%s) -> users %s", event, priority, ids)
        return created
    except Exception:
        log.warning("notify failed for %s", event)
        return []

