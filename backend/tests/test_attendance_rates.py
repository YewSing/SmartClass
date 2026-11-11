"""T32: attendance rate + history (FR-307–FR-309)."""
from datetime import date, datetime, timedelta

import pytest

from app.core.database import AsyncSessionLocal
from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.session import AttendanceSession
from app.services.attendance_stats import StatusCounts

pytestmark = pytest.mark.db

MON = date(2026, 11, 16)


def day(offset: int) -> date:
    return MON + timedelta(days=offset)


async def make_session(
    occ_id: int,
    lecturer_id: int,
    day: date,
    status: str = "closed",
    records: dict[int, str] | None = None,
    hour: int = 8,
) -> int:
    """One attendance session for `occ_id`, with optional {student_id: status} records."""
    async with AsyncSessionLocal() as db:
        start = datetime(day.year, day.month, day.day, hour, 0)
        end = start + timedelta(hours=2)
        sess = AttendanceSession(
            occurrence_id=occ_id,
            lecturer_id=lecturer_id,
            status=status,
            source="manual",
            class_date=day,
            opened_at=None if status == "scheduled" else start,
            starts_at=start,
            ends_at=end,
            closed_at=end if status == "closed" else None,
        )
        db.add(sess)
        await db.flush()
        for student_id, record_status in (records or {}).items():
            db.add(AttendanceRecord(
                session_id=sess.id,
                student_id=student_id,
                status=record_status,
                detected_at=start if record_status in ("present", "late") else None,
            ))
        await db.commit()
        return sess.id


# ── The formula (FR-308) ─────────────────────────────────────────────────────

def test_rate_formula_counts_late_and_skips_excused():
    counts = StatusCounts(present=2, late=1, excused=1, absent=1)
    assert counts.closed_sessions == 5
    assert counts.counted_sessions == 4
    assert counts.rate == 75.0


def test_rate_is_none_with_no_closed_sessions():
    assert StatusCounts().rate is None


def test_rate_is_none_when_every_session_excused():
    counts = StatusCounts(excused=3)
    assert counts.rate is None
    assert counts.counted_sessions == 0


def test_rate_rounds_to_one_decimal():
    counts = StatusCounts(present=1, absent=2)
    assert counts.rate == 33.3


# ── Student endpoint (FR-309) ────────────────────────────────────────────────

async def test_student_history_rate_and_counts(student_client, classroom):
    sid = classroom["student_ids"][0]
    lec = classroom["lecturer_id"]
    occ = classroom["occurrence_id"]

    await make_session(occ, lec, day(1), records={sid: "present"})
    await make_session(occ, lec, day(2), records={sid: "late"})
    await make_session(occ, lec, day(3), records={sid: "excused"})
    await make_session(occ, lec, day(4), records={sid: "absent"})
    await make_session(occ, lec, day(5))  # no record → absent

    resp = await student_client.get("/student/me/attendance/courses")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    course = body[0]
    assert course["course_code"] == "CS101"
    assert (course["present"], course["late"], course["excused"], course["absent"]) == (1, 1, 1, 2)
    assert course["closed_sessions"] == 5
    assert course["counted_sessions"] == 4
    assert course["rate"] == 50.0

    sessions = course["sessions"]
    assert len(sessions) == 5
    assert [item["date"] for item in sessions] == [day(i).isoformat() for i in (5, 4, 3, 2, 1)]
    assert sessions[0]["status"] == "absent"
    assert sessions[0]["session_status"] == "closed"
    assert all(item["session_status"] == "closed" for item in sessions)


async def test_student_history_zero_closed_sessions(student_client, classroom):
    resp = await student_client.get("/student/me/attendance/courses")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    course = body[0]
    assert course["course_code"] == "CS101"
    assert (course["present"], course["late"], course["excused"], course["absent"]) == (0, 0, 0, 0)
    assert course["closed_sessions"] == 0
    assert course["counted_sessions"] == 0
    assert course["rate"] is None
    assert course["sessions"] == []


async def test_student_history_every_session_excused(student_client, classroom):
    sid = classroom["student_ids"][0]
    lec = classroom["lecturer_id"]
    occ = classroom["occurrence_id"]
    await make_session(occ, lec, day(1), records={sid: "excused"})
    await make_session(occ, lec, day(2), records={sid: "excused"})

    course = (await student_client.get("/student/me/attendance/courses")).json()[0]
    assert course["excused"] == 2
    assert course["closed_sessions"] == 2
    assert course["counted_sessions"] == 0
    assert course["rate"] is None


async def test_only_closed_sessions_count(student_client, classroom):
    sid = classroom["student_ids"][0]
    lec = classroom["lecturer_id"]
    occ = classroom["occurrence_id"]

    await make_session(occ, lec, day(1), status="closed", records={sid: "present"})
    await make_session(occ, lec, day(2), status="open")
    await make_session(occ, lec, day(3), status="needs_confirmation")
    await make_session(occ, lec, day(4), status="cancelled")
    await make_session(occ, lec, day(5), status="scheduled")

    course = (await student_client.get("/student/me/attendance/courses")).json()[0]
    assert course["present"] == 1
    assert course["closed_sessions"] == 1
    assert course["rate"] == 100.0

    sessions = course["sessions"]
    assert len(sessions) == 2
    assert sessions[0]["session_status"] == "open"
    assert sessions[0]["status"] == "not_recorded"
    assert sessions[1]["session_status"] == "closed"
    assert sessions[1]["status"] == "present"


async def test_open_session_record_shown_not_counted(student_client, classroom):
    sid = classroom["student_ids"][0]
    await make_session(classroom["occurrence_id"], classroom["lecturer_id"], day(1),
                       status="open", records={sid: "late"})

    course = (await student_client.get("/student/me/attendance/courses")).json()[0]
    assert (course["present"], course["late"], course["excused"], course["absent"]) == (0, 0, 0, 0)
    assert course["closed_sessions"] == 0
    assert course["rate"] is None
    assert len(course["sessions"]) == 1
    assert course["sessions"][0]["status"] == "late"
    assert course["sessions"][0]["session_status"] == "open"


async def test_student_history_only_own_courses_and_records(student_client, classroom):
    sid = classroom["student_ids"][0]
    other_sid = classroom["student_ids"][1]
    lec = classroom["lecturer_id"]
    occ = classroom["occurrence_id"]

    await make_session(occ, lec, day(1), records={sid: "present", other_sid: "absent"})
    # CS202 belongs to another lecturer and this student is not enrolled in it.
    await make_session(classroom["other_occurrence_id"], classroom["other_lecturer_id"], day(1),
                       records={sid: "absent"})

    body = (await student_client.get("/student/me/attendance/courses")).json()
    assert [course["course_code"] for course in body] == ["CS101"]
    course = body[0]
    assert course["closed_sessions"] == 1
    assert course["present"] == 1
    assert course["absent"] == 0
    assert course["rate"] == 100.0


async def test_student_history_groups_course_across_classes(student_client, classroom, users):
    sid = classroom["student_ids"][0]
    lec = classroom["lecturer_id"]

    async with AsyncSessionLocal() as db:
        tutorial = ClassOccurrence(
            course_id=classroom["course_id"], type="TUTORIAL", day_of_week="Wed",
            start_time="10:00", end_time="11:00", room="DK3", lecturer_id=lec,
            label="Tutorial Group 1",
        )
        db.add(tutorial)
        await db.flush()
        db.add(Enrollment(student_id=sid, occurrence_id=tutorial.id))
        await db.commit()
        tutorial_id = tutorial.id

    await make_session(classroom["occurrence_id"], lec, day(1), records={sid: "present"})
    await make_session(tutorial_id, lec, day(2), records={sid: "absent"})

    body = (await student_client.get("/student/me/attendance/courses")).json()
    assert len(body) == 1
    course = body[0]
    assert course["course_code"] == "CS101"
    assert course["closed_sessions"] == 2
    assert course["rate"] == 50.0
    assert {item["class_type"] for item in course["sessions"]} == {"LECTURE", "TUTORIAL"}


async def test_student_endpoint_forbids_staff(lecturer_client, admin_client):
    resp = await lecturer_client.get("/student/me/attendance/courses")
    assert resp.status_code == 403, resp.text
    resp = await admin_client.get("/student/me/attendance/courses")
    assert resp.status_code == 403, resp.text


# ── Lecturer endpoint ────────────────────────────────────────────────────────

async def test_lecturer_class_rates(lecturer_client, classroom):
    a, b, c = classroom["student_ids"]
    lec = classroom["lecturer_id"]
    occ = classroom["occurrence_id"]

    await make_session(occ, lec, day(1), records={a: "present", b: "excused"})
    await make_session(occ, lec, day(2), records={a: "late", b: "excused"})
    await make_session(occ, lec, day(3), records={a: "absent", b: "present"})
    await make_session(occ, lec, day(4), status="open", records={a: "present", b: "present", c: "present"})

    resp = await lecturer_client.get(f"/lecturer/classes/{occ}/attendance/rates")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["course_code"] == "CS101"
    assert body["closed_sessions"] == 3
    assert [s["student_id"] for s in body["students"]] == [a, b, c]

    by_id = {s["student_id"]: s for s in body["students"]}
    assert (by_id[a]["present"], by_id[a]["late"], by_id[a]["excused"], by_id[a]["absent"]) == (1, 1, 0, 1)
    assert by_id[a]["closed_sessions"] == 3
    assert by_id[a]["rate"] == 66.7
    assert (by_id[b]["present"], by_id[b]["late"], by_id[b]["excused"], by_id[b]["absent"]) == (1, 0, 2, 0)
    assert by_id[b]["counted_sessions"] == 1
    assert by_id[b]["rate"] == 100.0
    assert (by_id[c]["present"], by_id[c]["late"], by_id[c]["excused"], by_id[c]["absent"]) == (0, 0, 0, 3)
    assert by_id[c]["rate"] == 0.0


async def test_lecturer_class_rates_zero_closed_sessions(lecturer_client, classroom):
    occ = classroom["occurrence_id"]
    resp = await lecturer_client.get(f"/lecturer/classes/{occ}/attendance/rates")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["closed_sessions"] == 0
    assert len(body["students"]) == 3
    for student in body["students"]:
        assert student["rate"] is None
        assert student["closed_sessions"] == 0
        assert (student["present"], student["late"], student["excused"], student["absent"]) == (0, 0, 0, 0)


async def test_lecturer_class_rates_every_session_excused(lecturer_client, classroom):
    a = classroom["student_ids"][0]
    lec = classroom["lecturer_id"]
    occ = classroom["occurrence_id"]
    await make_session(occ, lec, day(1), records={a: "excused"})
    await make_session(occ, lec, day(2), records={a: "excused"})

    body = (await lecturer_client.get(f"/lecturer/classes/{occ}/attendance/rates")).json()
    by_id = {s["student_id"]: s for s in body["students"]}
    assert by_id[a]["excused"] == 2
    assert by_id[a]["rate"] is None
    for other in classroom["student_ids"][1:]:
        assert by_id[other]["absent"] == 2
        assert by_id[other]["rate"] == 0.0


async def test_lecturer_rates_access(
    lecturer_client, other_lecturer_client, admin_client, student_client, classroom
):
    occ = classroom["occurrence_id"]
    resp = await other_lecturer_client.get(f"/lecturer/classes/{occ}/attendance/rates")
    assert resp.status_code == 403, resp.text

    resp = await lecturer_client.get(f"/lecturer/classes/{classroom['other_occurrence_id']}/attendance/rates")
    assert resp.status_code == 403, resp.text

    resp = await admin_client.get(f"/lecturer/classes/{occ}/attendance/rates")
    assert resp.status_code == 403, resp.text

    resp = await student_client.get(f"/lecturer/classes/{occ}/attendance/rates")
    assert resp.status_code == 403, resp.text

    resp = await lecturer_client.get("/lecturer/classes/999999/attendance/rates")
    assert resp.status_code == 404, resp.text


async def test_confirmed_held_session_counts(lecturer_client, student_client, classroom):
    sid = classroom["student_ids"][0]
    lec = classroom["lecturer_id"]
    occ = classroom["occurrence_id"]
    session_id = await make_session(occ, lec, day(1), status="needs_confirmation", records={sid: "present"})

    resp = await lecturer_client.post(f"/lecturer/sessions/{session_id}/confirm", json={"held": True})
    assert resp.status_code == 200, resp.text

    course = (await student_client.get("/student/me/attendance/courses")).json()[0]
    assert course["closed_sessions"] == 1
    assert course["present"] == 1
    assert course["rate"] == 100.0
