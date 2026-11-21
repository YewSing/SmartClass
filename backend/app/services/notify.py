"""Notification hook for Module 2 (Dashboard & Notifications, Shino).

Raise an event about a user (`users.id`) here. Module 2 stores it as an in-app notification
(`app.services.notifications`, S10); push and email follow in S13/S14. The payload is never
logged and never stored as-is: it holds names and matric numbers (NFR-02 / PDPA).

Call it after your transaction commits (from an `after_commit` callback): it opens its own
database session.

Events raised today:

- `attendance.recorded` -> the student. Payload: `session_id`, `course_code`, `course_name`,
  `status` (`present` | `late`), `detected_at`, `source` (`recognition` | `student_flag`), `message`.

The other Module 2 events from the FR doc (`attendance.flagged`, `face_enrolment.*`, see
`docs/requests-for-shino.md` R1) are not raised yet. The registry of every event, its priority
and payload fields is `app/services/notifications/registry.py` (see `docs/interfaces.md`).

This module imports nothing from `app` at import time: Module 2 is imported lazily inside
`emit`, so it stays cycle-free.
"""
import logging
from collections.abc import Iterable

log = logging.getLogger(__name__)


async def emit(event: str, user_ids: Iterable[int], payload: dict) -> None:
    """Raise a notification event for `user_ids` (users.id). Module 2 stores it (S10). Never
    raises: a notification can't fail the request that raised it."""
    try:
        ids = sorted(set(user_ids))
        if not ids:
            return
        log.info("notify %s -> users %s", event, ids)
        from app.services.notifications import store   # lazy: keeps this module cycle-free

        await store.deliver(event, ids, payload)
    except Exception as exc:
        log.warning("notify failed for %s: %s", event, exc.__class__.__name__)
