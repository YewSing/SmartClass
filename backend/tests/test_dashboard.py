"""S18: student and lecturer dashboard reads (FR-201, FR-202)."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import update

from app.core.database import AsyncSessionLocal
from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence
from app.models.moodle_snapshot import MoodleSnapshot
from app.models.notification import Notification
from app.models.session import AttendanceSession
from app.services import session_schedule, session_service
from app.services.dashboard import reads
from tests.shino_helpers import ShinoClass, build_shino_class

pytestmark = pytest.mark.db

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


async def record(session_id: int, student_id: int, status: str) -> None:
    async with AsyncSessionLocal() as db:
        db.add(AttendanceRecord(session_id=session_id, student_id=student_id, status=status,
                                detected_at=session_schedule.clock()))
        await db.commit()


async def close(session_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await session_service.close_session(session_id, db)
        await db.commit()


async def past_closed_session(c: ShinoClass, days_ago: int, statuses: list[str]) -> int:
    """A closed session `days_ago` days back with one record per enrolled student (same order)."""
    when = session_schedule.clock() - timedelta(days=days_ago)
    async with AsyncSessionLocal() as db:
        sess = AttendanceSession(occurrence_id=c.occurrence_id, lecturer_id=c.lecturer_id,
                                 class_date=when.date(), starts_at=when, ends_at=when + timedelta(hours=2),
                                 opened_at=when, closed_at=when + timedelta(hours=2),
                                 status="closed", source="manual")
        db.add(sess)
        await db.flush()
        db.add_all([AttendanceRecord(session_id=sess.id, student_id=sid, status=st)
                    for sid, st in zip(c.student_ids, statuses)])
        await db.commit()
        return sess.id


async def notify(user_id: int, priority: str, title: str, read: bool = False) -> int:
    async with AsyncSessionLocal() as db:
        n = Notification(user_id=user_id, event="announcement.posted", priority=priority, title=title,
                         message=f"msg {title}", link="/notifications", subject_key=f"t:{title}:{user_id}",
                         created_at=datetime(2026, 11, 22, 9, 0),
                         read_at=datetime(2026, 11, 22, 10, 0) if read else None)
        db.add(n)
        await db.commit()
        return n.id


async def get(c: ShinoClass, user_id: int, role: str, path: str):
    async with c.client(user_id, role) as client:
        return await client.get(path)


def today_slot_day() -> str:
    return DAYS[session_schedule.clock().weekday()]


# ── student (FR-201) ───────────────────────────────────────────────────────────

async def test_student_today_class_shows_own_status_while_open(shino_class):
    c = shino_class
    await record(c.session_id, c.student_ids[0], "present")
    await record(c.session_id, c.student_ids[1], "late")

    r = await get(c, c.student_user_ids[0], "student", "/student/me/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == session_schedule.clock().date().isoformat()
    [cls] = body["today_classes"]
    assert cls["occurrence_id"] == c.occurrence_id and cls["course_code"] == "SH101"
    assert cls["session_id"] == c.session_id and cls["session_status"] == "open"
    assert cls["attendance_status"] == "present"
    assert cls["room"] == "SH-R1" and cls["start_time"] is not None

    late = (await get(c, c.student_user_ids[1], "student", "/student/me/dashboard")).json()
    assert late["today_classes"][0]["attendance_status"] == "late"
    unseen = (await get(c, c.student_user_ids[2], "student", "/student/me/dashboard")).json()
    assert unseen["today_classes"][0]["attendance_status"] == "not_recorded"


async def test_student_status_after_close_and_rates_per_course(shino_class):
    c = shino_class
    await past_closed_session(c, 7, ["present", "absent", "excused", "late"])
    await record(c.session_id, c.student_ids[0], "late")
    await close(c.session_id)

    me = (await get(c, c.student_user_ids[0], "student", "/student/me/dashboard")).json()
    assert me["today_classes"][0]["session_status"] == "closed"
    assert me["today_classes"][0]["attendance_status"] == "late"
    [rate] = me["attendance_rates"]
    assert rate["course_code"] == "SH101" and rate["course_name"] == "Shino Test Course"
    assert (rate["present"], rate["late"], rate["absent"], rate["closed_sessions"]) == (1, 1, 0, 2)
    assert rate["rate"] == 100.0

    second = (await get(c, c.student_user_ids[1], "student", "/student/me/dashboard")).json()
    assert second["today_classes"][0]["attendance_status"] == "absent"     # close marked them absent
    assert second["attendance_rates"][0]["rate"] == 0.0
    excused = (await get(c, c.student_user_ids[2], "student", "/student/me/dashboard")).json()
    assert excused["attendance_rates"][0]["rate"] == 0.0                   # 0/(2-1): excused left out


async def test_student_rate_is_null_without_closed_sessions(shino_class):
    c = shino_class
    body = (await get(c, c.student_user_ids[0], "student", "/student/me/dashboard")).json()
    [rate] = body["attendance_rates"]
    assert rate["rate"] is None and rate["closed_sessions"] == 0


async def test_outsider_sees_no_classes_rates_or_others_notifications(shino_class):
    c = shino_class
    await notify(c.student_user_ids[0], "urgent", "for-enrolled")
    body = (await get(c, c.outsider_user_id, "student", "/student/me/dashboard")).json()
    assert body["today_classes"] == [] and body["attendance_rates"] == []
    assert body["priority_notifications"] == [] and body["unread_count"] == 0


async def test_student_moodle_snapshot_with_refreshed_at_and_isolation(shino_class):
    c = shino_class
    empty = (await get(c, c.student_user_ids[0], "student", "/student/me/dashboard")).json()
    assert empty["moodle"] == {"announcements": [], "deadlines": [], "refreshed_at": None}

    ann = {"course_id": 5, "course_code": "SH101", "course_name": "Shino Test Course", "id": 11,
           "title": "Welcome", "date": "2026-11-20T09:00:00+08:00",
           "link": "http://moodle/mod/forum/discuss.php?d=11"}
    dl = {"course_id": 5, "course_code": "SH101", "course_name": "Shino Test Course", "id": 21,
          "title": "Assignment 1", "type": "assign", "date": "2026-11-30T23:59:00+08:00",
          "link": "http://moodle/calendar/view.php?view=day&course=5&time=1"}
    async with AsyncSessionLocal() as db:
        db.add(MoodleSnapshot(user_id=c.student_user_ids[0], announcements=[ann], deadlines=[dl],
                              refreshed_at=datetime(2026, 11, 22, 8, 30)))
        await db.commit()

    body = (await get(c, c.student_user_ids[0], "student", "/student/me/dashboard")).json()
    assert body["moodle"]["announcements"] == [ann]
    assert body["moodle"]["deadlines"] == [dl]
    assert body["moodle"]["refreshed_at"].startswith("2026-11-22T08:30")
    other = (await get(c, c.student_user_ids[1], "student", "/student/me/dashboard")).json()
    assert other["moodle"]["announcements"] == [] and other["moodle"]["refreshed_at"] is None


async def test_student_priority_notifications_unread_urgent_first_only_mine(shino_class):
    c = shino_class
    me = c.student_user_ids[0]
    await notify(me, "important", "imp")
    await notify(me, "urgent", "urg")
    await notify(me, "general", "gen")
    await notify(me, "urgent", "old-read", read=True)
    await notify(c.student_user_ids[1], "urgent", "not-mine")

    body = (await get(c, me, "student", "/student/me/dashboard")).json()
    assert [n["title"] for n in body["priority_notifications"]] == ["urg", "imp"]
    assert body["unread_count"] == 3          # every unread, general included
    assert body["live_activity"] is None      # M5/M6 field present until S80


async def test_student_weekly_slot_today_without_session(monkeypatch):
    c = await build_shino_class(open_session=False)
    async with AsyncSessionLocal() as db:
        await db.execute(update(ClassOccurrence).where(ClassOccurrence.id == c.occurrence_id)
                         .values(day_of_week=today_slot_day()))
        await db.commit()
    body = (await get(c, c.student_user_ids[0], "student", "/student/me/dashboard")).json()
    [cls] = body["today_classes"]
    assert (cls["start_time"], cls["end_time"]) == ("08:00", "10:00")
    assert cls["session_id"] is None and cls["session_status"] is None
    assert cls["attendance_status"] is None


async def test_needs_confirmation_session_has_no_status_yet(shino_class):
    c = shino_class
    async with AsyncSessionLocal() as db:
        await db.execute(update(AttendanceSession).where(AttendanceSession.id == c.session_id)
                         .values(status="needs_confirmation"))
        await db.commit()
    body = (await get(c, c.student_user_ids[0], "student", "/student/me/dashboard")).json()
    [cls] = body["today_classes"]
    assert cls["session_status"] == "needs_confirmation" and cls["attendance_status"] is None


async def test_other_days_session_is_not_today(shino_class, monkeypatch):
    c = shino_class
    later = session_schedule.clock() + timedelta(days=3)
    if DAYS[later.weekday()] == "Mon":      # SH101's weekly slot; pick a day without it
        later += timedelta(days=1)
    monkeypatch.setattr(reads, "clock", lambda: later)
    body = (await get(c, c.student_user_ids[0], "student", "/student/me/dashboard")).json()
    assert body["date"] == later.date().isoformat()
    assert body["today_classes"] == []


# ── lecturer (FR-202) ──────────────────────────────────────────────────────────

async def test_lecturer_dashboard_current_open_session_counts(shino_class):
    c = shino_class
    await record(c.session_id, c.student_ids[0], "present")
    await record(c.session_id, c.student_ids[1], "late")
    await record(c.session_id, c.student_ids[2], "absent")

    r = await get(c, c.lecturer_user_id, "lecturer", "/lecturer/dashboard")
    assert r.status_code == 200
    body = r.json()
    [cls] = body["today_classes"]
    assert cls["occurrence_id"] == c.occurrence_id and cls["session_status"] == "open"
    assert "attendance_status" not in cls
    ov = body["attendance_overview"]
    assert ov["session_id"] == c.session_id and ov["session_status"] == "open"
    assert ov["course_code"] == "SH101"
    assert (ov["enrolled"], ov["present"], ov["late"], ov["excused"], ov["absent"], ov["not_recorded"]) \
        == (4, 1, 1, 0, 1, 1)
    assert ov["rate"] is None
    assert body["participation"] is None and body["quizzes"] is None and body["at_risk_alerts"] is None


async def test_lecturer_latest_closed_session_counts(shino_class):
    c = shino_class
    await past_closed_session(c, 14, ["absent", "absent", "absent", "absent"])
    await record(c.session_id, c.student_ids[0], "present")
    await record(c.session_id, c.student_ids[1], "late")
    await record(c.session_id, c.student_ids[2], "excused")
    await close(c.session_id)

    ov = (await get(c, c.lecturer_user_id, "lecturer", "/lecturer/dashboard")).json()["attendance_overview"]
    assert ov["session_id"] == c.session_id and ov["session_status"] == "closed"
    assert (ov["enrolled"], ov["present"], ov["late"], ov["excused"], ov["absent"], ov["not_recorded"]) \
        == (4, 1, 1, 1, 1, 0)
    assert ov["rate"] == round(2 / 3 * 100, 1)


async def test_lecturer_overview_prefers_open_over_newer_closed(shino_class):
    c = shino_class
    async with AsyncSessionLocal() as db:   # the open session started a while ago
        await db.execute(update(AttendanceSession).where(AttendanceSession.id == c.session_id).values(
            starts_at=session_schedule.clock() - timedelta(hours=1)))
        await db.commit()
    await past_closed_session(c, 0, ["present"] * 4)
    ov = (await get(c, c.lecturer_user_id, "lecturer", "/lecturer/dashboard")).json()["attendance_overview"]
    assert ov["session_id"] == c.session_id and ov["session_status"] == "open"


async def test_other_lecturer_sees_nothing_of_the_class(shino_class):
    c = shino_class
    await notify(c.lecturer_user_id, "urgent", "for-teacher")
    body = (await get(c, c.other_lecturer_user_id, "lecturer", "/lecturer/dashboard")).json()
    assert all(cls["occurrence_id"] != c.occurrence_id for cls in body["today_classes"])
    assert body["attendance_overview"] is None
    assert body["priority_notifications"] == []


async def test_lecturer_priority_notifications(shino_class):
    c = shino_class
    await notify(c.lecturer_user_id, "urgent", "u1")
    await notify(c.lecturer_user_id, "general", "g1")
    body = (await get(c, c.lecturer_user_id, "lecturer", "/lecturer/dashboard")).json()
    assert [n["title"] for n in body["priority_notifications"]] == ["u1"]
    assert body["unread_count"] == 2


async def test_lecturer_without_sessions_has_no_overview():
    c = await build_shino_class(open_session=False)
    body = (await get(c, c.lecturer_user_id, "lecturer", "/lecturer/dashboard")).json()
    assert body["attendance_overview"] is None


# ── access ─────────────────────────────────────────────────────────────────────

async def test_roles_and_auth(shino_class):
    c = shino_class
    assert (await get(c, c.student_user_ids[0], "student", "/lecturer/dashboard")).status_code == 403
    assert (await get(c, c.lecturer_user_id, "lecturer", "/student/me/dashboard")).status_code == 403
    async with c.client() as anon:
        # no token: HTTPBearer refuses before the role check (401 or 403, as in S11's feed tests)
        assert (await anon.get("/student/me/dashboard")).status_code in (401, 403)
        assert (await anon.get("/lecturer/dashboard")).status_code in (401, 403)
