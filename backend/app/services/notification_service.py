"""M2 recipient feed. The public producer signature stays in notify.py."""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import AsyncSessionLocal
from app.models.notification import Notification
from app.models.user import User

EVENTS = {
    "attendance.recorded": ("general", "Attendance recorded"),
    "attendance.flagged": ("important", "Attendance needs review"),
    "face_enrolment.pending_review": ("important", "Face enrolment needs review"),
    "face_enrolment.result": ("important", "Face enrolment result"),
    "quiz.published": ("important", "New quiz available"),
    "quiz.deadline_reminder": ("important", "Quiz closes soon"),
    "quiz.graded": ("general", "Quiz result available"),
    "game.started": ("important", "Live game started"),
    "poll.started": ("important", "Live poll started"),
    "confusion.spike": ("urgent", "Class needs clarification"),
    "at_risk.alert": ("important", "Student needs support"),
    "moodle.deadline_reminder": ("important", "Course deadline approaching"),
}


def event_content(event, payload, now=None):
    priority, title = EVENTS[event]
    title = payload.get("title", title)
    if not isinstance(title, str) or not title.strip() or len(title) > 255:
        raise ValueError("Notification title must contain 1-255 characters")
    # Explicit subject/version keys let producers distinguish recurring events.
    # Legacy T44 uses one immutable attendance event per session and recipient.
    subject = {k: payload[k] for k in ("session_id", "enrolment_id", "quiz_id", "poll_id", "event_id", "dedupe_key", "status") if k in payload}
    if event in ("quiz.deadline_reminder", "moodle.deadline_reminder", "confusion.spike", "at_risk.alert"):
        # Producers can supply an exact occurrence/window key; legacy events use
        # bounded windows so a later legitimate event is not suppressed forever.
        window = 120 if event == "confusion.spike" else 3600
        subject["occurrence"] = payload.get("window_key") or payload.get("event_id") or payload.get("dedupe_key") or int((now or datetime.now(timezone.utc)).timestamp()) // window
    if not subject:
        subject = {"payload": payload, "day": (now or datetime.now(timezone.utc)).date().isoformat()}
    key = hashlib.sha256(json.dumps([event, subject], sort_keys=True, default=str).encode()).hexdigest()
    message = str(payload.get("message") or payload.get("reason") or title)
    link = payload.get("link")
    if link is None:
        if event.startswith("attendance.") and payload.get("session_id") is not None:
            link = f"/attendance/sessions/{payload['session_id']}"
        elif event.startswith("face_enrolment."):
            link = "/face-enrolment" if event.endswith("result") else "/face-verification"
        elif event.startswith(("quiz.", "game.")) and payload.get("quiz_id") is not None:
            link = f"/quizzes/{payload['quiz_id']}"
    # Links are app-relative destinations; clients must resolve them through their route map.
    if link is not None and (not isinstance(link, str) or not link.startswith("/") or link.startswith("//")):
        raise ValueError("Notification link must be an app-relative path")
    return dict(event_type=event, event_key=key, priority=priority, title=title, message=message, link=link)


async def deliver(event, user_ids, payload):
    content = event_content(event, payload)
    async with AsyncSessionLocal() as db:
        ids = (await db.scalars(select(User.id).where(User.id.in_(set(user_ids)), User.status == "active"))).all()
        for user_id in ids:
            await db.execute(insert(Notification).values(user_id=user_id, **content)
                             .on_conflict_do_nothing(constraint="uq_notification_recipient_event"))
        await db.commit()
