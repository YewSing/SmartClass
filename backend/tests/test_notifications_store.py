"""S10: notification store and event interface (FR-205, FR-206, FR-207, FR-216)."""
import logging
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, run_after_commit
from app.core.timezone import now_myt
from app.models.attendance import AttendanceRecord
from app.models.notification import Notification
from app.services import attendance_service, notify
from app.services.notifications import registry, store
from app.websocket.manager import manager

FR206_EVENTS = {
    "attendance.recorded", "attendance.flagged", "face_enrolment.result",
    "face_enrolment.pending_review", "quiz.published", "quiz.deadline_reminder", "quiz.graded",
    "game.started", "poll.started", "confusion.spike", "at_risk.alert", "moodle.deadline_reminder",
}

QUIZ = {"quiz_id": 7, "quiz_title": "Week 3 quiz", "course_code": "SH101"}


async def rows(user_id: int | None = None) -> list[Notification]:
    async with AsyncSessionLocal() as db:
        q = select(Notification).order_by(Notification.id)
        if user_id is not None:
            q = q.where(Notification.user_id == user_id)
        return list((await db.scalars(q)).all())


@pytest.fixture
def clock(monkeypatch):
    state = {"now": datetime(2026, 11, 23, 9, 0)}
    monkeypatch.setattr(store, "clock", lambda: state["now"])
    return state


# ── registry (no DB) ─────────────────────────────────────────────────────────────

def test_every_fr206_event_has_a_priority_and_defaults():
    assert FR206_EVENTS <= set(registry.EVENTS)
    for name, spec in registry.EVENTS.items():
        assert spec.priority in ("urgent", "important", "general"), name
        assert spec.fallback_title and spec.fallback_message, name
        assert spec.window > timedelta(0), name
        # Even an empty payload gives a usable notification.
        built = registry.build(name, {})
        assert built.priority == spec.priority and built.title and built.message
        assert built.subject_key


@pytest.mark.parametrize("event,priority", [
    ("attendance.recorded", "general"), ("poll.started", "general"),
    ("quiz.published", "important"), ("face_enrolment.result", "important"),
    ("game.started", "urgent"), ("confusion.spike", "urgent"), ("quiz.deadline_reminder", "urgent"),
])
def test_priority_is_set_by_event_not_caller(event, priority):
    assert registry.build(event, {"priority": "general" if priority != "general" else "urgent"}).priority == priority


def test_templates_fill_link_subject_and_caller_text():
    built = registry.build("quiz.published", QUIZ)
    assert built.title == "New quiz: Week 3 quiz"
    assert built.link == "/quizzes/7"
    assert built.subject_key == "quiz:7"
    custom = registry.build("quiz.published", {**QUIZ, "title": "Custom", "message": "Body", "link": "/quizzes/7/info"})
    assert (custom.title, custom.message, custom.link) == ("Custom", "Body", "/quizzes/7/info")


def test_template_slots_are_plain_and_values_single_line():
    assert registry.render("{a.__class__}", {"a": 1}) is None
    assert registry.render("{a!r}", {"a": 1}) is None
    assert registry.render("x {a}", {"a": {"nested": 1}}) is None
    assert registry.render("x {a}", {"a": "line\nbreak"}) == "x line break"


@pytest.mark.parametrize("link", [
    "https://evil.example/x", "//evil.example/x", "javascript:alert(1)", "/a/../../etc",
    "/a b", "/a\\b", "quizzes/1", "/a/%2e%2e/admin", "/" + "a" * 400, 42,
])
def test_unsafe_links_are_rejected(link):
    with pytest.raises(registry.UnsafeLink):
        registry.build("quiz.published", {**QUIZ, "link": link})


def test_unsafe_link_from_template_field_is_rejected():
    with pytest.raises(registry.UnsafeLink):
        registry.build("quiz.published", {**QUIZ, "quiz_id": "../admin"})


def test_unknown_event_builds_nothing():
    assert registry.build("no.such.event", {}) is None


# ── store / emit (DB) ────────────────────────────────────────────────────────────

@pytest.mark.db
async def test_emit_persists_one_row_per_recipient(shino_class, clock):
    users = shino_class.student_user_ids
    await notify.emit("quiz.published", users, QUIZ)
    saved = await rows()
    assert sorted(r.user_id for r in saved) == sorted(users)
    r = saved[0]
    assert (r.event, r.priority, r.title, r.link, r.subject_key) == (
        "quiz.published", "important", "New quiz: Week 3 quiz", "/quizzes/7", "quiz:7")
    assert r.read_at is None and r.created_at == clock["now"]


@pytest.mark.db
async def test_duplicates_dropped_within_window_and_allowed_after(shino_class, clock):
    uid = shino_class.student_user_ids[0]
    await notify.emit("quiz.published", [uid], QUIZ)
    clock["now"] += timedelta(hours=23)
    await notify.emit("quiz.published", [uid], QUIZ)                       # same subject, in window
    assert len(await rows(uid)) == 1
    await notify.emit("quiz.published", [uid], {**QUIZ, "quiz_id": 8})     # other subject
    assert len(await rows(uid)) == 2
    clock["now"] += timedelta(hours=2)                                     # 25 h after the first
    await notify.emit("quiz.published", [uid], QUIZ)
    assert len(await rows(uid)) == 3


@pytest.mark.db
async def test_dedup_is_per_recipient(shino_class, clock):
    a, b = shino_class.student_user_ids[:2]
    await notify.emit("quiz.published", [a], QUIZ)
    await notify.emit("quiz.published", [a, b], QUIZ)
    assert [r.user_id for r in await rows()] == [a, b]


@pytest.mark.db
async def test_dedup_without_subject_fields_uses_the_text(shino_class, clock):
    uid = shino_class.student_user_ids[0]
    await notify.emit("quiz.published", [uid], {"title": "A"})
    await notify.emit("quiz.published", [uid], {"title": "A"})
    await notify.emit("quiz.published", [uid], {"title": "B"})
    assert [r.title for r in await rows(uid)] == ["A", "B"]


@pytest.mark.db
async def test_unknown_event_is_logged_not_raised(shino_class, caplog):
    with caplog.at_level(logging.WARNING):
        await notify.emit("no.such.event", shino_class.student_user_ids, {"x": 1})
    assert await rows() == []
    assert "unknown notification event no.such.event" in caplog.text


@pytest.mark.db
async def test_unsafe_link_stores_nothing_and_never_raises(shino_class, caplog):
    with caplog.at_level(logging.WARNING):
        await notify.emit("quiz.published", shino_class.student_user_ids,
                          {**QUIZ, "link": "https://evil.example/phish"})
    assert await rows() == []
    assert "UnsafeLink" in caplog.text and "evil" not in caplog.text


@pytest.mark.db
async def test_unknown_recipients_skipped(shino_class, clock):
    uid = shino_class.student_user_ids[0]
    await notify.emit("quiz.published", [uid, 999_999], QUIZ)
    assert [r.user_id for r in await rows()] == [uid]


@pytest.mark.db
async def test_payload_never_stored_raw(shino_class, clock, caplog):
    uid = shino_class.lecturer_user_id
    payload = {"enrolment_id": 3, "student_name": "Secret Name", "matric_no": "SH123456",
               "courses": ["SH101"]}
    with caplog.at_level(logging.DEBUG):
        await notify.emit("face_enrolment.pending_review", [uid], payload)
        # A templated event with caller text: only the referenced fields and caller text land.
        await notify.emit("quiz.published", [uid], {**QUIZ, "message": "Open now",
                                                    "student_name": "Secret Name",
                                                    "matric_no": "SH123456"})
    saved = await rows(uid)
    assert len(saved) == 2
    for r in saved:
        stored = " ".join(str(getattr(r, c.key)) for c in Notification.__table__.columns)
        assert "Secret Name" not in stored and "SH123456" not in stored
        assert "'enrolment_id'" not in stored and "{" not in stored
    assert saved[1].message == "Open now" and saved[1].title == "New quiz: Week 3 quiz"
    assert "Secret Name" not in caplog.text and "SH123456" not in caplog.text


@pytest.mark.db
async def test_attendance_recorded_from_m3_lands(shino_class, monkeypatch):
    """M3's own broadcast path (unchanged) raises `attendance.recorded`; it is stored."""
    async def quiet(*args, **kwargs):
        return None
    monkeypatch.setattr(manager, "broadcast", quiet)
    monkeypatch.setattr(manager, "send_to_user", quiet)

    async with AsyncSessionLocal() as db:
        record = AttendanceRecord(session_id=shino_class.session_id,
                                  student_id=shino_class.student_ids[0],
                                  status="present", detected_at=now_myt())
        db.add(record)
        await db.flush()
        await attendance_service.broadcast_attendance_update(
            shino_class.session_id, record, "Shino Student 1", "SH000001", db)
        await db.commit()
        await run_after_commit(db)

    (r,) = await rows(shino_class.student_user_ids[0])
    assert (r.event, r.priority) == ("attendance.recorded", "general")
    assert r.link == f"/attendance/sessions/{shino_class.session_id}"
    assert r.subject_key == f"session:{shino_class.session_id}"
    assert "SH101" in r.message and "SH000001" not in r.message
