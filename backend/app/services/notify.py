"""Notification hook for Module 2 (Dashboard & Notifications, Shino).

Raise an event about a user (`users.id`) here; Module 2 replaces or wraps `emit` to deliver it by
push, in-app or email. M2 persists in-app messages and logs only the event and recipient IDs;
payloads can hold names and matric numbers (NFR-02 / PDPA).

Events raised today:

- `attendance.recorded` -> the student. Payload: `session_id`, `course_code`, `course_name`,
  `status` (`present` | `late`), `detected_at`, `source` (`recognition` | `student_flag`), `message`.

The other Module 2 events from the FR doc (`attendance.flagged`, `face_enrolment.*`, see
`docs/requests-for-shino.md` R1) are not raised yet.

This module imports nothing from `app`: Module 2 wraps it, so it must stay cycle-free.
"""
import logging
from collections.abc import Iterable

log = logging.getLogger(__name__)


async def emit(event: str, user_ids: Iterable[int], payload: dict) -> None:
    """Raise a notification event for `user_ids` (users.id). Module 2 replaces or wraps this to
    deliver push / in-app / email. M2 now persists in-app feed entries. Never raises."""
    try:
        ids = sorted(set(user_ids))
        if not ids:
            return
        log.info("notify %s -> users %s", event, ids)
        from app.services.notification_service import deliver
        await deliver(event, ids, payload)
    except Exception:
        log.warning("notify failed for %s", event)
