"""Event registry for Module 2 notifications (FR-206, FR-207, FR-216) — S10.

Each event type has one priority (set here, never by the caller), a default title and message,
an app-relative link and a *subject*: what the event is about (a session, a quiz, a flag). Two
events with the same type, recipient and subject inside the event's window are one notification.

Templates use `{field}` names from the event payload. A missing field never breaks delivery:
the title/message fall back to the event's static text, a link to `None`, and a subject to a hash
of the rendered text. Values are inserted as short single-line text.
"""
from __future__ import annotations

import hashlib
import re
import string
from dataclasses import dataclass
from datetime import timedelta

TITLE_MAX = 200
MESSAGE_MAX = 1000
LINK_MAX = 300
SUBJECT_MAX = 200
VALUE_MAX = 120


class UnsafeLink(ValueError):
    """The link is not an app-relative path (external URL, scheme, `..`, odd characters)."""


@dataclass(frozen=True)
class EventSpec:
    priority: str                    # urgent | important | general
    title: str                       # template
    message: str                     # template
    fallback_title: str
    fallback_message: str
    link: str | None                 # app-relative template, e.g. /quizzes/{quiz_id}
    subject: str                     # template, e.g. quiz:{quiz_id}
    window: timedelta = timedelta(hours=24)


def _spec(priority, title, message, fallback_title, fallback_message, link, subject,
          window=timedelta(hours=24)) -> EventSpec:
    return EventSpec(priority, title, message, fallback_title, fallback_message, link, subject, window)


# FR-206 events (plus FR-217 lecturer announcements). Messages never carry marks or performance.
EVENTS: dict[str, EventSpec] = {
    "attendance.recorded": _spec(
        "general", "Attendance recorded: {course_code}",
        "Your attendance for {course_code} was recorded as {status}.",
        "Attendance recorded", "Your attendance was recorded.",
        "/attendance/sessions/{session_id}", "session:{session_id}"),
    "attendance.flagged": _spec(
        "important", "Attendance flag to review: {course_code}",
        "A student in {course_code} says they are present but was not recognised.",
        "Attendance flag to review", "A student says they are present but was not recognised.",
        "/attendance/sessions/{session_id}", "flag:{flag_id}"),
    "face_enrolment.pending_review": _spec(
        "important", "Face enrolment to review",
        "A student's face enrolment needs your review.",
        "Face enrolment to review", "A student's face enrolment needs your review.",
        "/face-verification", "enrolment:{enrolment_id}"),
    "face_enrolment.result": _spec(
        "important", "Face enrolment {status}",
        "Your face enrolment was {status}.",
        "Face enrolment result", "Your face enrolment has been reviewed.",
        "/profile/face", "enrolment:{enrolment_id}:{status}"),
    "quiz.published": _spec(
        "important", "New quiz: {quiz_title}",
        "A new quiz is available in {course_code}.",
        "New quiz", "A new quiz is available.",
        "/quizzes/{quiz_id}", "quiz:{quiz_id}"),
    "quiz.deadline_reminder": _spec(
        "urgent", "Quiz closing soon: {quiz_title}",
        "{quiz_title} closes in {remaining}.",
        "Quiz closing soon", "A quiz you have not submitted closes soon.",
        "/quizzes/{quiz_id}", "quiz:{quiz_id}:{reminder}", timedelta(days=3)),
    "quiz.graded": _spec(
        "important", "Quiz results released: {quiz_title}",
        "Your results for {quiz_title} are ready.",
        "Quiz results released", "Your quiz results are ready.",
        "/quizzes/{quiz_id}/result", "quiz:{quiz_id}"),
    "game.started": _spec(
        "urgent", "Live quiz starting: {quiz_title}",
        "A live quiz has started in {course_code}. Join now.",
        "Live quiz starting", "A live quiz has started. Join now.",
        "/games/{game_id}", "game:{game_id}", timedelta(hours=6)),
    "poll.started": _spec(
        "general", "New poll in {course_code}",
        "Your lecturer started a poll.",
        "New poll", "Your lecturer started a poll.",
        "/interaction/{attendance_session_id}", "poll:{poll_id}", timedelta(hours=6)),
    "confusion.spike": _spec(
        "urgent", "Students are confused: {course_code}",
        "Many students pressed \"I don't understand\" in the last few minutes.",
        "Students are confused", "Many students pressed \"I don't understand\" in the last few minutes.",
        "/interaction/{attendance_session_id}", "spike:{attendance_session_id}:{spike_id}",
        timedelta(hours=6)),
    "at_risk.alert": _spec(
        "important", "Student at risk in {course_code}",
        "A student in {course_code} matches an at-risk rule.",
        "Student at risk", "A student matches an at-risk rule.",
        "/analytics/courses/{course_id}", "alert:{alert_id}", timedelta(days=30)),
    "moodle.deadline_reminder": _spec(
        "important", "Deadline soon: {title}",
        "{title} ({course_code}) is due in {remaining}.",
        "Deadline soon", "A Moodle deadline is coming up.",
        "/home", "moodle:{moodle_event_id}:{reminder}", timedelta(days=3)),
    "announcement.posted": _spec(
        "important", "{title}", "{message}",
        "Announcement", "Your lecturer posted an announcement.",
        "/announcements/{announcement_id}", "announcement:{announcement_id}"),
    # S19: "Send a test notification" in the apps' preferences (checks push/email on a device).
    # Important so it is pushed and emailed like a real one; one per minute per user.
    "notification.test": _spec(
        "important", "Test notification", "Notifications are working on this account.",
        "Test notification", "Notifications are working on this account.",
        None, "test", timedelta(minutes=1)),
}

_FORMATTER = string.Formatter()
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
_SAFE_LINK = re.compile(r"/[A-Za-z0-9\-._~/?=&]*")   # no %: encoded ../ can't sneak in


def _clean(value: object) -> str | None:
    """Short single-line text for a template slot, or None if the value can't go in one."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    text = _CONTROL.sub(" ", str(value)).strip()
    return text[:VALUE_MAX] if text else None


def render(template: str | None, payload: dict) -> str | None:
    """Fill `{field}` slots from `payload`; None when the template needs a field it lacks.
    Only plain `{name}` slots are allowed (no attribute/index access, no format specs)."""
    if template is None:
        return None
    out: list[str] = []
    for literal, field, spec, conv in _FORMATTER.parse(template):
        out.append(literal)
        if field is None:
            continue
        if spec or conv or not field.isidentifier():
            return None
        value = _clean(payload.get(field))
        if value is None:
            return None
        out.append(value)
    return "".join(out)


def check_link(link: str | None) -> str | None:
    """Return `link` if it is a safe app-relative path, else raise `UnsafeLink`."""
    if link is None:
        return None
    if (not isinstance(link, str) or len(link) > LINK_MAX or link.startswith("//")
            or ".." in link or not _SAFE_LINK.fullmatch(link)):
        raise UnsafeLink("notification links must be app-relative paths")
    return link


@dataclass(frozen=True)
class Rendered:
    event: str
    priority: str
    title: str
    message: str
    link: str | None
    subject_key: str
    window: timedelta


def _override(payload: dict, key: str, limit: int) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] if value else None


def build(event: str, payload: dict) -> Rendered | None:
    """The notification for `event`, or None for an unknown event. Raises `UnsafeLink`.

    FR-205: the caller may pass `title`, `message` and `link` in the payload; the priority always
    comes from the event type (FR-207)."""
    spec = EVENTS.get(event)
    if spec is None:
        return None
    payload = payload if isinstance(payload, dict) else {}
    title = (render(spec.title, payload) or spec.fallback_title)[:TITLE_MAX]
    message = (render(spec.message, payload) or spec.fallback_message)[:MESSAGE_MAX]
    # A caller's own title/message keep their full length and line breaks (template slots are
    # cut to VALUE_MAX single-line text, too short for an announcement body, FR-217).
    title = _override(payload, "title", TITLE_MAX) or title
    message = _override(payload, "message", MESSAGE_MAX) or message
    if "link" in payload and payload["link"] is not None:
        link = check_link(payload["link"])
    else:
        link = check_link(render(spec.link, payload))
    subject = render(spec.subject, payload)
    if subject is None:   # no subject fields: the same text counts as the same notification
        digest = hashlib.sha256(f"{title}\n{message}\n{link}".encode()).hexdigest()[:24]
        subject = f"content:{digest}"
    return Rendered(event, spec.priority, title, message, link, subject[:SUBJECT_MAX], spec.window)
