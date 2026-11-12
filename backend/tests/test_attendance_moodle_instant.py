"""T38b: events go out only after the change commits, and a closed or overridden session is sent to
Moodle at once in the background with its new sync status broadcast (FR-311, FR-312, NFR-20).

Moodle is the respx fake from the T35 tests. conftest turns the sync off (interval 0); tests here
turn it on with `sync_on`.
"""
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, after_commit, get_db, run_after_commit
from app.models.attendance import AttendanceRecord
from app.models.session import AttendanceSession
from app.services import attendance_moodle_sync as sync
from app.services import attendance_service, session_schedule
from app.websocket.manager import manager
from tests import test_attendance_moodle_sync as t35
from tests.test_attendance_moodle_sync import STATUS_IDS, _closed_session, _run, _session, at

pytestmark = pytest.mark.db

fake_moodle = t35.fake_moodle   # the T35 fixtures
linked = t35.linked


@pytest.fixture
def sync_on(monkeypatch):
    monkeypatch.setattr(settings, "MOODLE_ATTENDANCE_SYNC_INTERVAL_SECONDS", 30)


@pytest.fixture
def events(monkeypatch):
    """Every broadcast as (session id, payload, the session's status in a fresh transaction)."""
    seen: list[tuple[int, dict, str | None]] = []

    async def capture(session_id: int, payload: dict) -> None:
        async with AsyncSessionLocal() as db:   # what a client re-reading right now would see
            status = await db.scalar(select(AttendanceSession.status).where(AttendanceSession.id == session_id))
        seen.append((session_id, payload, status))

    monkeypatch.setattr(manager, "broadcast", capture)
    return seen


def _of(events, name):
    return [(sid, payload, status) for sid, payload, status in events if payload["event"] == name]


async def _start(lecturer_client, classroom) -> int:
    resp = await lecturer_client.post("/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── after commit ──────────────────────────────────────────────────────────────

async def test_session_closed_is_broadcast_after_the_close_commits(lecturer_client, classroom, events):
    session_id = await _start(lecturer_client, classroom)
    resp = await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")
    assert resp.status_code == 200, resp.text

    [(sid, payload, status_seen)] = _of(events, "session_closed")
    assert sid == session_id
    assert status_seen == "closed"   # committed before the event went out
    assert payload["status"] == "closed" and payload["final"] is True
    assert payload["moodle_sync_status"] == "pending"
    assert _of(events, "moodle_sync") == []   # the sync is off: nothing is sent or announced


async def test_override_is_broadcast_after_it_commits(lecturer_client, classroom, events):
    session_id = await _start(lecturer_client, classroom)
    student_id = classroom["student_ids"][0]
    resp = await lecturer_client.put(f"/lecturer/sessions/{session_id}/attendance/override",
                                     json={"student_id": student_id, "status": "excused"})
    assert resp.status_code == 200, resp.text

    [(sid, payload, _)] = _of(events, "attendance_override")
    assert sid == session_id and payload["student"]["status"] == "excused"
    assert "moodle_sync_status" not in payload   # an open session is not in Moodle yet
    async with AsyncSessionLocal() as db:   # the record the event announces is committed
        assert await db.scalar(select(AttendanceRecord.status).where(
            AttendanceRecord.session_id == session_id, AttendanceRecord.student_id == student_id)) == "excused"


async def test_recognition_update_waits_for_the_commit(classroom, db_session, events, monkeypatch):
    monkeypatch.setattr(attendance_service, "check_low_attendance_alert", _no_alert)
    session = AttendanceSession(occurrence_id=classroom["occurrence_id"], lecturer_id=classroom["lecturer_id"],
                                status="open", source="manual")
    db_session.add(session)
    await db_session.flush()
    record, was_new = await attendance_service.mark_present(session.id, classroom["student_ids"][0], db_session)
    assert was_new
    await attendance_service.broadcast_attendance_update(session.id, record, "S1", "S0000001", db_session)
    assert events == []   # nothing announced before the commit

    await db_session.commit()
    await run_after_commit(db_session)
    [(sid, payload, _)] = events
    assert sid == session.id and payload["event"] == "attendance_update"
    assert payload["counts"]["present"] == 1


async def _no_alert(*_args, **_kwargs):
    return None


async def test_a_rolled_back_request_announces_nothing():
    called = []

    async def callback():
        called.append(True)

    gen = get_db()
    db = await gen.__anext__()
    after_commit(db, callback)
    with pytest.raises(RuntimeError):
        await gen.athrow(RuntimeError("handler failed"))
    assert called == []


async def test_one_failing_callback_does_not_stop_the_others():
    called = []

    async def boom():
        raise ValueError("x")

    async def ok():
        called.append(True)

    async with AsyncSessionLocal() as db:
        after_commit(db, boom)
        after_commit(db, ok)
        await run_after_commit(db)
    assert called == [True]


# ── instant sync ──────────────────────────────────────────────────────────────

async def test_ending_a_class_sends_it_to_moodle_at_once_and_announces_synced(
        sync_on, fake_moodle, classroom, linked, lecturer_client, db_session, events):
    session_id = await _start(lecturer_client, classroom)
    resp = await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")
    assert resp.status_code == 200, resp.text
    assert resp.json()["moodle_sync_status"] == "pending"
    await sync.wait_for_background_syncs()

    s = await _session(db_session, session_id)
    assert s.moodle_sync_status == "synced" and s.moodle_synced_at is not None
    (msid,) = fake_moodle.sessions
    assert set(fake_moodle.log[msid].values()) == {STATUS_IDS["A"]}   # nobody was marked: all absent

    assert [p["event"] for _, p, _ in events] == ["session_closed", "moodle_sync"]
    [(sid, payload, _)] = _of(events, "moodle_sync")
    assert sid == session_id
    assert payload["moodle_sync_status"] == "synced"
    assert payload["moodle_synced_at"] == s.moodle_synced_at.isoformat()


async def test_moodle_down_announces_failed_and_keeps_the_retry(
        sync_on, fake_moodle, classroom, linked, lecturer_client, db_session, events):
    fake_moodle.down = True
    session_id = await _start(lecturer_client, classroom)
    assert (await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")).status_code == 200
    await sync.wait_for_background_syncs()

    s = await _session(db_session, session_id)
    assert s.moodle_sync_status == "failed" and s.moodle_sync_attempts == 1
    assert s.moodle_sync_next_at is not None   # the loop retries with backoff (NFR-20)
    [(_, payload, _)] = _of(events, "moodle_sync")
    assert payload["moodle_sync_status"] == "failed" and payload["moodle_sync_error"]

    fake_moodle.down = False   # Moodle is back: the loop's retry also announces the outcome
    assert await _run(fake_moodle, s.moodle_sync_next_at) == {session_id: "synced"}
    assert _of(events, "moodle_sync")[-1][1]["moodle_sync_status"] == "synced"


async def test_override_after_close_resends_at_once(sync_on, fake_moodle, classroom, linked, lecturer_client,
                                                     db_session, events):
    session_id = await _closed_session(db_session, classroom, ["present", "late", "absent"])
    assert await _run(fake_moodle, at(12)) == {session_id: "synced"}
    (msid,) = fake_moodle.sessions
    student_id = classroom["student_ids"][2]
    events.clear()

    resp = await lecturer_client.put(f"/lecturer/sessions/{session_id}/attendance/override",
                                     json={"student_id": student_id, "status": "excused", "reason": "MC"})
    assert resp.status_code == 200, resp.text
    await sync.wait_for_background_syncs()

    assert (await _session(db_session, session_id)).moodle_sync_status == "synced"
    assert fake_moodle.log[msid][linked[student_id]] == STATUS_IDS["E"]
    override, moodle = events
    assert override[1]["event"] == "attendance_override" and override[1]["moodle_sync_status"] == "pending"
    assert moodle[1] == {**moodle[1], "event": "moodle_sync", "moodle_sync_status": "synced"}


async def test_confirm_held_sends_at_once(sync_on, fake_moodle, classroom, linked, lecturer_client, db_session,
                                          events, monkeypatch):
    s = AttendanceSession(occurrence_id=classroom["occurrence_id"], lecturer_id=classroom["lecturer_id"],
                          status="needs_confirmation", class_date=at(8).date(), starts_at=at(8), ends_at=at(10),
                          opened_at=at(7, 45), closed_at=at(10), source="schedule")
    db_session.add(s)
    await db_session.commit()
    monkeypatch.setattr(session_schedule, "clock", lambda: at(11))

    resp = await lecturer_client.post(f"/lecturer/sessions/{s.id}/confirm", json={"held": True})
    assert resp.status_code == 200, resp.text
    await sync.wait_for_background_syncs()
    assert (await _session(db_session, s.id)).moodle_sync_status == "synced"


async def test_the_job_closing_a_class_sends_it_after_its_commit(sync_on, fake_moodle, classroom, linked,
                                                                 db_session):
    s = AttendanceSession(occurrence_id=classroom["occurrence_id"], lecturer_id=classroom["lecturer_id"],
                          status="open", class_date=at(8).date(), starts_at=at(8), ends_at=at(10),
                          opened_at=at(7, 45), source="schedule", lecturer_action_at=at(8))
    db_session.add(s)
    await db_session.commit()

    async with AsyncSessionLocal() as db:
        report = await session_schedule.tick(db, now=at(10, 1))
        assert sync._background == set()   # nothing starts before the commit
        await db.commit()
        await run_after_commit(db)
    assert report.closed == [s.id]
    await sync.wait_for_background_syncs()
    assert (await _session(db_session, s.id)).moodle_sync_status == "synced"


async def test_no_token_or_interval_zero_starts_nothing(fake_moodle, classroom, linked, lecturer_client, db_session,
                                                        monkeypatch):
    session_id = await _start(lecturer_client, classroom)   # conftest: interval 0
    assert (await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")).status_code == 200
    assert sync._background == set()
    assert fake_moodle.calls == []

    monkeypatch.setattr(settings, "MOODLE_ATTENDANCE_SYNC_INTERVAL_SECONDS", 30)
    monkeypatch.setattr(settings, "MOODLE_TOKEN", "")
    assert sync.start_background_sync(session_id) is None
    assert (await _session(db_session, session_id)).moodle_sync_status == "pending"


async def test_background_sync_skips_a_session_already_sent(sync_on, fake_moodle, classroom, linked, db_session,
                                                            events):
    session_id = await _closed_session(db_session, classroom, ["present", "late", "absent"])
    assert await _run(fake_moodle, at(12)) == {session_id: "synced"}
    calls = len(fake_moodle.calls)
    assert await sync.sync_in_background(session_id) is None
    assert len(fake_moodle.calls) == calls


# ── end to end against the local SPeCTRUM simulation ─────────────────────────

@pytest.mark.moodle
async def test_ending_a_class_shows_synced_from_local_moodle_within_seconds(db_session, users, lecturer_client,
                                                                          events, sync_on):
    """T38b's "Done when": End class on a WIA0000 class -> the session is in the local Moodle and a
    `moodle_sync: synced` event follows within a few seconds, with no Retry."""
    import asyncio
    import time

    from app.models.class_ import ClassOccurrence, Course, Enrollment
    from app.models.user import Lecturer, Student, User
    from app.services.kb.moodle_client import MoodleClient

    async with MoodleClient() as c:
        course_id = await c.get_course_id("WIA0000")
        assert course_id, "WIA0000 not in Moodle (run seed.sh)"
        enrolled = await c.call("core_enrol_get_enrolled_users", courseid=course_id)
    students = [u for u in enrolled if "student" in {r["shortname"] for r in u.get("roles", [])}][:2]
    assert len(students) == 2, "WIA0000 needs at least 2 students in Moodle"

    lec_id = await db_session.scalar(select(Lecturer.id).where(Lecturer.user_id == users["lecturer"].id))
    course = Course(code="WIA0000", name="Test course")
    db_session.add(course)
    await db_session.flush()
    occ = ClassOccurrence(course_id=course.id, type="LECTURE", lecturer_id=lec_id)
    db_session.add(occ)
    await db_session.flush()
    for i, u in enumerate(students):
        su = User(email=f"t38b.s{i}@siswa.um.edu.my", role="student", name=u.get("fullname", "S"), status="active",
                  moodle_user_id=int(u["id"]))
        db_session.add(su)
        await db_session.flush()
        st = Student(user_id=su.id, matric_no=f"T38BS{i}")
        db_session.add(st)
        await db_session.flush()
        db_session.add(Enrollment(student_id=st.id, occurrence_id=occ.id))
    occ_id = occ.id
    await db_session.commit()

    resp = await lecturer_client.post("/lecturer/sessions", json={"occurrence_id": occ_id})
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["id"]
    msid = None
    try:
        started = time.monotonic()
        resp = await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")
        assert resp.status_code == 200, resp.text
        assert resp.json()["moodle_sync_status"] == "pending"
        await asyncio.wait_for(sync.wait_for_background_syncs(), 10)
        elapsed = time.monotonic() - started

        [(_, payload, _)] = _of(events, "moodle_sync")
        assert payload["moodle_sync_status"] == "synced", payload
        assert elapsed < 5, f"took {elapsed:.1f} s"
        s = await _session(db_session, session_id)
        msid = s.moodle_session_id
        async with MoodleClient() as c:
            got = await c.call("mod_attendance_get_session", sessionid=msid)
        assert got["description"] == f"SmartClass WIA0000 session #{session_id}"
        acronyms = {int(st["id"]): st["acronym"] for st in got["statuses"]}
        assert {acronyms[int(e["statusid"])] for e in got["attendance_log"]} == {"A"}
    finally:
        if msid:
            async with MoodleClient() as c:
                await c.call("mod_attendance_remove_session", sessionid=msid)
