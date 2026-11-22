"""Interaction event log writer (FR-517) — S34.

Every student action in M5 calls `record` inside its own transaction, after the action itself has
been written, so the log and the action commit (or roll back) together. Reading is
`app.services.interaction_read` (the M7 interface).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import EVENT_TYPES, InteractionEvent

QUESTION_ASKED = "question_asked"
QUESTION_UPVOTED = "question_upvoted"
POLL_VOTED = "poll_voted"
QUICK_ANSWERED = "quick_answered"
REACTION = "reaction"
CONFUSION = "confusion"


def record(db: AsyncSession, type_: str, attendance_session_id: int, student_id: int | None,
           at: datetime, *, ref_id: int | None = None, anonymous: bool = False) -> None:
    """Add one event to the session's log (flushed with the caller's next flush/commit)."""
    if type_ not in EVENT_TYPES:
        raise ValueError(f"Unknown interaction event type: {type_}")
    db.add(InteractionEvent(attendance_session_id=attendance_session_id, student_id=student_id,
                            type=type_, ref_id=ref_id, anonymous=anonymous, created_at=at))
