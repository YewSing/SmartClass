"""T35: closed sessions sync to Moodle Attendance (FR-311, NFR-20, NFR-22).

Moodle is mocked with respx (FakeAttendanceMoodle); the `moodle` test at the bottom runs end to
end against the local SPeCTRUM simulation (backend/moodle, after setup.sh + seed.sh).
"""
import random
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.services import attendance_moodle_sync as sync
from app.services import session_schedule, session_service
from app.services.kb.moodle_client import MoodleClient

pytestmark = pytest.mark.db

SVC_TOKEN = "svc-token"
MOODLE_COURSE = 77
ATTENDANCE_ID = 5
SERVICE_USER = 2
STATUS_IDS = {"P": 11, "A": 12, "L": 13, "E": 14}   # the plugin's default set (setnumber 0)
CLASS_DAY = date(2026, 11, 16)                      # a Monday, CS101's weekly day


def _ws_url() -> str:
    return f"{settings.MOODLE_URL.rstrip('/')}/webservice/rest/server.php"


class FakeAttendanceMoodle:
    """mod_attendance as seen with the service token: one course with one Attendance activity."""

    def __init__(self):
        self.sessions: dict[int, dict] = {}   # moodle session id -> session record
        self.log: dict[int, dict[int, int]] = {}  # moodle session id -> {moodle user id: status id}
        self.calls: list[tuple[str, dict]] = []
        self.next_id = 900
        self.down = False
        self.fail_update_for: set[int] = set()   # moodle user ids whose update fails
        self.has_activity = True

    def count(self, fn: str) -> int:
        return sum(1 for f, _ in self.calls if f == fn)

    def _session(self, sid: int) -> dict:
        s = self.sessions[sid]
        statuses = [{"id": i, "attendanceid": ATTENDANCE_ID, "acronym": a, "description": a, "grade": 1,
                     "visible": 1, "deleted": 0, "setnumber": 0} for a, i in STATUS_IDS.items()]
        # a deleted status and another set with the same acronyms must be ignored
        statuses += [{"id": 99, "attendanceid": ATTENDANCE_ID, "acronym": "P", "description": "old", "grade": 1,
                      "visible": 1, "deleted": 1, "setnumber": 0},
                     {"id": 98, "attendanceid": ATTENDANCE_ID, "acronym": "P", "description": "set1", "grade": 1,
                      "visible": 1, "deleted": 0, "setnumber": 1}]
        return {**s, "statuses": statuses,
                "attendance_log": [{"studentid": u, "statusid": str(st), "remarks": "", "id": "1"}
                                   for u, st in self.log.get(sid, {}).items()]}

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503, text="Service Unavailable")
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        assert form.pop("wstoken") == SVC_TOKEN
        fn = form.pop("wsfunction")
        form.pop("moodlewsrestformat")
        self.calls.append((fn, form))
        if fn == "core_course_get_courses_by_field":
            assert form["value"] == "CS101"
            return httpx.Response(200, json={"courses": [{"id": MOODLE_COURSE, "shortname": "CS101"}]})
        if fn == "core_course_get_contents":
            assert int(form["courseid"]) == MOODLE_COURSE
            modules = [{"id": 1, "modname": "forum", "instance": 3}]
            if self.has_activity:
                modules.append({"id": 2, "modname": "attendance", "instance": ATTENDANCE_ID})
            return httpx.Response(200, json=[{"id": 1, "name": "General", "modules": modules}])
        if fn == "core_webservice_get_site_info":
            return httpx.Response(200, json={"userid": SERVICE_USER})
        if fn == "mod_attendance_get_sessions":
            assert int(form["attendanceid"]) == ATTENDANCE_ID
            return httpx.Response(200, json=[self._session(sid) for sid in self.sessions])
        if fn == "mod_attendance_get_session":
            sid = int(form["sessionid"])
            if sid not in self.sessions:
                return httpx.Response(200, json={"exception": "dml_missing_record_exception",
                                                 "errorcode": "invalidrecord", "message": "Can't find data record"})
            return httpx.Response(200, json=self._session(sid))
        if fn == "mod_attendance_add_session":
            sid = self.add(int(form["sessiontime"]), form["description"], int(form["duration"]))
            return httpx.Response(200, json={"sessionid": sid})
        if fn == "mod_attendance_update_user_status":
            sid, uid = int(form["sessionid"]), int(form["studentid"])
            if uid in self.fail_update_for:
                return httpx.Response(500, text="boom")
            assert int(form["statusset"]) == 0
            self.log.setdefault(sid, {})[uid] = int(form["statusid"])
            return httpx.Response(200, json="200")
        raise AssertionError(f"unexpected wsfunction {fn}")

    def add(self, sessiontime: int, description: str, duration: int = 3600) -> int:
        self.next_id += 1
        self.sessions[self.next_id] = {"id": self.next_id, "attendanceid": ATTENDANCE_ID, "sessdate": sessiontime,
                                       "duration": duration, "description": description, "statusset": 0,
                                       "studentscanmark": 0}
        return self.next_id


@pytest.fixture
def fake_moodle(monkeypatch):
    monkeypatch.setattr(settings, "MOODLE_TOKEN", SVC_TOKEN)
    fake = FakeAttendanceMoodle()
    with respx.mock(assert_all_called=False) as router:
        router.post(_ws_url()).mock(side_effect=lambda request: fake.handler(request))
        yield fake


@pytest.fixture
async def linked(classroom, db_session):
    """Give CS101's three students Moodle ids 501..503 (classroom['student_ids'] order)."""
    for i, sid in enumerate(classroom["student_ids"]):
        uid = await db_session.scalar(select(Student.user_id).where(Student.id == sid))
        await db_session.execute(update(User).where(User.id == uid).values(moodle_user_id=501 + i))
    await db_session.commit()
    return {sid: 501 + i for i, sid in enumerate(classroom["student_ids"])}


def at(h: int, m: int = 0, d: date = CLASS_DAY) -> datetime:
    return datetime.combine(d, datetime.min.time()).replace(hour=h, minute=m)


async def _closed_session(db, classroom, statuses, *, start=None, closed=None) -> int:
    """A closed CS101 session queued for sync, with one record per status (student order)."""
    start = start or at(8)
    s = AttendanceSession(occurrence_id=classroom["occurrence_id"], lecturer_id=classroom["lecturer_id"],
                          status="closed", class_date=start.date(), starts_at=start,
                          ends_at=start + timedelta(hours=2), opened_at=start - timedelta(minutes=15),
                          closed_at=closed or start + timedelta(hours=2), source="schedule",
                          moodle_sync_status="pending", moodle_sync_next_at=closed or start + timedelta(hours=2))
    db.add(s)
    await db.flush()
    session_id = s.id
    for student_id, st in zip(classroom["student_ids"], statuses):
        if st is not None:
            db.add(AttendanceRecord(session_id=session_id, student_id=student_id, status=st))
    await db.commit()
    return session_id


async def _session(db, session_id) -> AttendanceSession:
    db.expire_all()
    return await db.get(AttendanceSession, session_id)


async def _records(db, session_id) -> dict[int, AttendanceRecord]:
    db.expire_all()
    rows = (await db.execute(select(AttendanceRecord).where(AttendanceRecord.session_id == session_id))).scalars()
    return {r.student_id: r for r in rows}


async def _run(fake, now):
    async with MoodleClient(token=SVC_TOKEN) as c:
        return await sync.run_due(client=c, now=now)


# ── queueing ──────────────────────────────────────────────────────────────────

async def test_closing_through_the_api_queues_a_sync(lecturer_client, classroom, db_session):
    resp = await lecturer_client.post("/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["id"]
    resp = await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")
    assert resp.status_code == 200, resp.text

    s = await _session(db_session, session_id)
    assert s.moodle_sync_status == "pending"
    assert s.moodle_sync_next_at == s.closed_at
    assert s.moodle_sync_attempts == 0
    assert await sync.due_session_ids(db_session, s.closed_at) == [session_id]


async def test_job_close_queues_but_needs_confirmation_does_not(classroom, db_session):
    held = AttendanceSession(occurrence_id=classroom["occurrence_id"], lecturer_id=classroom["lecturer_id"],
                             status="open", class_date=CLASS_DAY, starts_at=at(8), ends_at=at(10),
                             opened_at=at(7, 45), source="schedule")
    db_session.add(held)
    await db_session.flush()
    db_session.add(AttendanceRecord(session_id=held.id, student_id=classroom["student_ids"][0], status="present"))
    empty = AttendanceSession(occurrence_id=classroom["other_occurrence_id"],
                              lecturer_id=classroom["other_lecturer_id"], status="open", class_date=CLASS_DAY,
                              starts_at=at(8), ends_at=at(10), opened_at=at(7, 45), source="manual")
    db_session.add(empty)
    await db_session.flush()
    held_id, empty_id = held.id, empty.id
    await db_session.commit()

    report = await session_schedule.tick(db_session, now=at(10, 1))
    await db_session.commit()
    assert report.closed == [held_id] and report.needs_confirmation == [empty_id]

    assert (await _session(db_session, held_id)).moodle_sync_status == "pending"
    assert (await _session(db_session, empty_id)).moodle_sync_status is None   # nobody marked, nothing sent

    # The lecturer confirms the empty class was held -> it is closed and queued
    s = await _session(db_session, empty_id)
    await session_schedule.confirm(db_session, s, True, at(11), classroom["other_lecturer_id"])
    await db_session.commit()
    s = await _session(db_session, empty_id)
    assert s.status == "closed" and s.moodle_sync_status == "pending"


async def test_sessions_closed_before_t35_are_never_sent(fake_moodle, classroom, linked, db_session):
    session_id = await _closed_session(db_session, classroom, ["present", "absent", "late"])
    await db_session.execute(update(AttendanceSession).values(moodle_sync_status=None, moodle_sync_next_at=None))
    await db_session.commit()
    assert await _run(fake_moodle, at(12)) == {}
    assert fake_moodle.calls == []
    assert (await _session(db_session, session_id)).moodle_sync_status is None


# ── sending ───────────────────────────────────────────────────────────────────

async def test_sync_creates_the_moodle_session_and_maps_all_four_statuses(fake_moodle, classroom, linked,
                                                                         db_session):
    # three students: present, late, excused; then add an absent one through a fourth student below
    session_id = await _closed_session(db_session, classroom, ["present", "late", "excused"])
    extra = User(email="s4@siswa.um.edu.my", role="student", name="S4", status="active", moodle_user_id=504)
    db_session.add(extra)
    await db_session.flush()
    stu4 = Student(user_id=extra.id, matric_no="S0000004")
    db_session.add(stu4)
    await db_session.flush()
    stu4_id = stu4.id
    db_session.add_all([Enrollment(student_id=stu4_id, occurrence_id=classroom["occurrence_id"]),
                        AttendanceRecord(session_id=session_id, student_id=stu4_id, status="absent")])
    await db_session.commit()

    assert await _run(fake_moodle, at(12)) == {session_id: "synced"}

    assert fake_moodle.count("mod_attendance_add_session") == 1
    (msid, msession), = fake_moodle.sessions.items()
    assert msession["description"] == f"SmartClass CS101 session #{session_id}"
    assert msession["sessdate"] == sync.moodle_timestamp(at(8))
    assert msession["sessdate"] % 86400 == 0          # 08:00 MYT is midnight UTC
    assert msession["duration"] == 7200
    s1, s2, s3 = classroom["student_ids"]
    assert fake_moodle.log[msid] == {501: STATUS_IDS["P"], 502: STATUS_IDS["L"], 503: STATUS_IDS["E"],
                                     504: STATUS_IDS["A"]}
    updates = [f for fn, f in fake_moodle.calls if fn == "mod_attendance_update_user_status"]
    assert {int(f["takenbyid"]) for f in updates} == {SERVICE_USER}   # the lecturer has no Moodle account

    s = await _session(db_session, session_id)
    assert (s.moodle_sync_status, s.moodle_session_id, s.moodle_synced_at) == ("synced", msid, at(12))
    assert s.moodle_sync_next_at is None and s.moodle_sync_error is None
    recs = await _records(db_session, session_id)
    assert {sid: r.moodle_status_sent for sid, r in recs.items()} == {
        s1: "present", s2: "late", s3: "excused", stu4_id: "absent"}

    async with db_session.bind.connect() as conn:  # course id was filled in
        assert (await conn.execute(select(Course.moodle_course_id).where(
            Course.id == classroom["course_id"]))).scalar_one() == MOODLE_COURSE


async def test_sync_is_idempotent(fake_moodle, classroom, linked, db_session):
    session_id = await _closed_session(db_session, classroom, ["present", "absent", "late"])
    await _run(fake_moodle, at(12))
    first_calls = len(fake_moodle.calls)

    # Run again with nothing due: no calls at all
    assert await _run(fake_moodle, at(13)) == {}
    assert len(fake_moodle.calls) == first_calls

    # Queue it again with nothing changed: same Moodle session, no status sent again
    await db_session.execute(update(AttendanceSession).where(AttendanceSession.id == session_id)
                             .values(moodle_sync_status="pending", moodle_sync_next_at=at(13)))
    await db_session.commit()
    assert await _run(fake_moodle, at(13)) == {session_id: "synced"}
    assert fake_moodle.count("mod_attendance_add_session") == 1
    assert fake_moodle.count("mod_attendance_update_user_status") == 3
    assert len(fake_moodle.sessions) == 1

    # One status changed: only that student is sent
    rec = (await _records(db_session, session_id))[classroom["student_ids"][1]]
    rec.status = "excused"
    await db_session.execute(update(AttendanceSession).where(AttendanceSession.id == session_id)
                             .values(moodle_sync_status="pending", moodle_sync_next_at=at(14)))
    await db_session.commit()
    await _run(fake_moodle, at(14))
    assert fake_moodle.count("mod_attendance_update_user_status") == 4
    (msid,) = fake_moodle.sessions
    assert fake_moodle.log[msid][502] == STATUS_IDS["E"]


async def test_finds_an_existing_moodle_session_instead_of_adding_a_second(fake_moodle, classroom, linked,
                                                                           db_session):
    session_id = await _closed_session(db_session, classroom, ["present", "present", "present"])
    # A crash after add_session but before the id was committed left this one in Moodle;
    # a session with the same marker but a different time is someone else's.
    marker = f"SmartClass CS101 session #{session_id}"
    fake_moodle.add(sync.moodle_timestamp(at(8)) + 86400 * 7, marker)
    existing = fake_moodle.add(sync.moodle_timestamp(at(8)), marker)

    assert await _run(fake_moodle, at(12)) == {session_id: "synced"}
    assert fake_moodle.count("mod_attendance_add_session") == 0
    assert (await _session(db_session, session_id)).moodle_session_id == existing
    assert set(fake_moodle.log[existing]) == {501, 502, 503}


async def test_recreates_a_moodle_session_deleted_in_moodle(fake_moodle, classroom, linked, db_session):
    session_id = await _closed_session(db_session, classroom, ["present", "late", "absent"])
    await _run(fake_moodle, at(12))
    (old,) = fake_moodle.sessions
    del fake_moodle.sessions[old]
    await db_session.execute(update(AttendanceRecord).values(moodle_status_sent=None))
    await db_session.execute(update(AttendanceSession).where(AttendanceSession.id == session_id)
                             .values(moodle_sync_status="pending", moodle_sync_next_at=at(13)))
    await db_session.commit()

    assert await _run(fake_moodle, at(13)) == {session_id: "synced"}
    (new,) = fake_moodle.sessions
    assert new != old and (await _session(db_session, session_id)).moodle_session_id == new
    assert len(fake_moodle.log[new]) == 3


async def test_lecturer_with_moodle_account_is_taken_by(fake_moodle, classroom, linked, db_session, users):
    await db_session.execute(update(User).where(User.id == users["lecturer"].id).values(moodle_user_id=600))
    await db_session.commit()
    await _closed_session(db_session, classroom, ["present", None, None])
    await _run(fake_moodle, at(12))
    (upd,) = [f for fn, f in fake_moodle.calls if fn == "mod_attendance_update_user_status"]
    assert int(upd["takenbyid"]) == 600
    assert fake_moodle.count("core_webservice_get_site_info") == 0


async def test_students_without_moodle_account_are_skipped_and_noted(fake_moodle, classroom, db_session):
    first = classroom["student_ids"][0]
    uid = await db_session.scalar(select(Student.user_id).where(Student.id == first))
    await db_session.execute(update(User).where(User.id == uid).values(moodle_user_id=501))
    await db_session.commit()
    session_id = await _closed_session(db_session, classroom, ["present", "absent", "late"])

    assert await _run(fake_moodle, at(12)) == {session_id: "synced"}
    (msid,) = fake_moodle.sessions
    assert fake_moodle.log[msid] == {501: STATUS_IDS["P"]}
    s = await _session(db_session, session_id)
    assert s.moodle_sync_error == "2 student(s) have no Moodle account and were not sent"


# ── failures + backoff ────────────────────────────────────────────────────────

async def test_moodle_down_fails_then_retries_with_backoff_until_synced(fake_moodle, classroom, linked,
                                                                        db_session):
    session_id = await _closed_session(db_session, classroom, ["present", "late", "absent"])
    fake_moodle.down = True

    assert await _run(fake_moodle, at(12)) == {session_id: "failed"}
    s = await _session(db_session, session_id)
    assert (s.moodle_sync_status, s.moodle_sync_attempts) == ("failed", 1)
    assert s.moodle_sync_next_at == at(12) + timedelta(seconds=settings.MOODLE_ATTENDANCE_RETRY_BASE_SECONDS)
    assert s.moodle_sync_error == "HTTPStatusError"   # no URL or token in the stored error
    second = s.moodle_sync_next_at
    # attendance stays recorded in SmartClass (NFR-20)
    assert {r.status for r in (await _records(db_session, session_id)).values()} == {"present", "late", "absent"}

    # Not due yet: nothing is tried
    calls = len(fake_moodle.calls)
    assert await _run(fake_moodle, at(12, 0) + timedelta(seconds=59)) == {}
    assert len(fake_moodle.calls) == calls

    # Second failure doubles the wait
    assert await _run(fake_moodle, second) == {session_id: "failed"}
    s = await _session(db_session, session_id)
    assert s.moodle_sync_attempts == 2
    assert s.moodle_sync_next_at == second + timedelta(seconds=2 * settings.MOODLE_ATTENDANCE_RETRY_BASE_SECONDS)

    fake_moodle.down = False
    assert await _run(fake_moodle, s.moodle_sync_next_at) == {session_id: "synced"}
    s = await _session(db_session, session_id)
    assert (s.moodle_sync_status, s.moodle_sync_attempts, s.moodle_sync_error) == ("synced", 0, None)
    (msid,) = fake_moodle.sessions
    assert len(fake_moodle.log[msid]) == 3


def test_retry_delay_doubles_and_is_capped(monkeypatch):
    monkeypatch.setattr(settings, "MOODLE_ATTENDANCE_RETRY_BASE_SECONDS", 60)
    monkeypatch.setattr(settings, "MOODLE_ATTENDANCE_RETRY_MAX_SECONDS", 3600)
    assert [sync.retry_delay(n).total_seconds() for n in (1, 2, 3, 6, 7, 30)] == [60, 120, 240, 1920, 3600, 3600]


async def test_partial_failure_keeps_what_was_sent(fake_moodle, classroom, linked, db_session):
    session_id = await _closed_session(db_session, classroom, ["present", "late", "absent"])
    fake_moodle.fail_update_for = {502}

    assert await _run(fake_moodle, at(12)) == {session_id: "failed"}
    s1, s2, s3 = classroom["student_ids"]
    recs = await _records(db_session, session_id)
    assert recs[s1].moodle_status_sent == "present" and recs[s2].moodle_status_sent is None
    s = await _session(db_session, session_id)
    assert s.moodle_session_id is not None    # the created Moodle session is remembered

    fake_moodle.fail_update_for = set()
    assert await _run(fake_moodle, s.moodle_sync_next_at) == {session_id: "synced"}
    assert fake_moodle.count("mod_attendance_add_session") == 1
    sent = [int(f["studentid"]) for fn, f in fake_moodle.calls if fn == "mod_attendance_update_user_status"]
    assert sent.count(501) == 1      # not sent twice


async def test_course_without_attendance_activity_fails_with_a_clear_reason(fake_moodle, classroom, linked,
                                                                            db_session):
    fake_moodle.has_activity = False
    session_id = await _closed_session(db_session, classroom, ["present", None, None])
    assert await _run(fake_moodle, at(12)) == {session_id: "failed"}
    s = await _session(db_session, session_id)
    assert s.moodle_sync_error == "Moodle course CS101 has no Attendance activity"


async def test_one_failing_session_does_not_block_the_others(fake_moodle, classroom, linked, db_session):
    bad = await _closed_session(db_session, classroom, ["present", "late", "absent"])
    good = await _closed_session(db_session, classroom, ["absent", "present", "present"], start=at(8, d=CLASS_DAY +
                                                                                                timedelta(days=7)))
    await db_session.execute(update(AttendanceSession).where(AttendanceSession.id == good)
                             .values(moodle_sync_next_at=at(12)))
    await db_session.commit()
    fake_moodle.fail_update_for = {501}
    assert await _run(fake_moodle, at(12)) == {bad: "failed", good: "failed"}
    fake_moodle.fail_update_for = set()
    results = await _run(fake_moodle, at(13))
    assert results == {bad: "synced", good: "synced"}


async def test_sync_status_is_limited_to_four_values(classroom, db_session):
    session_id = await _closed_session(db_session, classroom, [None, None, None])
    with pytest.raises(IntegrityError):
        await db_session.execute(update(AttendanceSession).where(AttendanceSession.id == session_id)
                                 .values(moodle_sync_status="done"))
        await db_session.commit()


# ── end to end against the local SPeCTRUM simulation ─────────────────────────

@pytest.mark.moodle
async def test_end_to_end_sync_into_local_moodle(db_session):
    """A closed WIA0000 session with four students lands in Moodle with P/L/E/A; a second run sends nothing."""
    async with MoodleClient() as c:
        course_id = await c.get_course_id("WIA0000")
        assert course_id, "WIA0000 not in Moodle (run seed.sh)"
        enrolled = await c.call("core_enrol_get_enrolled_users", courseid=course_id)
    students = [u for u in enrolled if "student" in {r["shortname"] for r in u.get("roles", [])}][:4]
    assert len(students) == 4, "WIA0000 needs at least 4 students in Moodle"

    lec_user = User(email="t35.lecturer@um.edu.my", role="lecturer", name="T35 Lecturer", status="active")
    db_session.add(lec_user)
    await db_session.flush()
    lec = Lecturer(user_id=lec_user.id, staff_id="T35-STAFF")
    course = Course(code="WIA0000", name="Test course")
    db_session.add_all([lec, course])
    await db_session.flush()
    occ = ClassOccurrence(course_id=course.id, type="LECTURE", lecturer_id=lec.id)
    db_session.add(occ)
    await db_session.flush()
    stu_ids = []
    for i, u in enumerate(students):
        su = User(email=f"t35.s{i}@siswa.um.edu.my", role="student", name=u.get("fullname", "S"), status="active",
                  moodle_user_id=int(u["id"]))
        db_session.add(su)
        await db_session.flush()
        st = Student(user_id=su.id, matric_no=f"T35S{i}")
        db_session.add(st)
        await db_session.flush()
        stu_ids.append(st.id)
    # a unique start time so this test never matches a session left by a dev database
    start = datetime(2026, 1, 5, 8, 0) + timedelta(minutes=random.randrange(100_000))
    s = AttendanceSession(occurrence_id=occ.id, lecturer_id=lec.id, status="closed", class_date=start.date(),
                          starts_at=start, ends_at=start + timedelta(hours=1), opened_at=start,
                          closed_at=start + timedelta(hours=1), source="manual")
    db_session.add(s)
    await db_session.flush()
    session_id = s.id
    for sid, st in zip(stu_ids, ["present", "late", "excused", "absent"]):
        db_session.add(AttendanceRecord(session_id=session_id, student_id=sid, status=st))
    await db_session.commit()

    await session_service.close_session(session_id, db_session, start + timedelta(hours=1))
    await db_session.commit()

    msid = None
    try:
        async with MoodleClient() as c:
            assert await sync.run_due(client=c, now=start + timedelta(hours=2)) == {session_id: "synced"}
            msid = (await _session(db_session, session_id)).moodle_session_id
            got = await c.call("mod_attendance_get_session", sessionid=msid)
            acronyms = {int(st["id"]): st["acronym"] for st in got["statuses"]}
            by_user = {int(e["studentid"]): acronyms[int(e["statusid"])] for e in got["attendance_log"]}
            assert by_user == {int(u["id"]): a for u, a in zip(students, "PLEA")}
            assert got["description"] == f"SmartClass WIA0000 session #{session_id}"

            # queue again: nothing new is sent and no second Moodle session appears
            await db_session.execute(update(AttendanceSession).where(AttendanceSession.id == session_id)
                                     .values(moodle_sync_status="pending",
                                             moodle_sync_next_at=start + timedelta(hours=2)))
            await db_session.commit()
            assert await sync.run_due(client=c, now=start + timedelta(hours=3)) == {session_id: "synced"}
            assert (await _session(db_session, session_id)).moodle_session_id == msid
            again = await c.call("mod_attendance_get_session", sessionid=msid)
            assert again["lasttaken"] == got["lasttaken"]
    finally:
        if msid:
            async with MoodleClient() as c:
                await c.call("mod_attendance_remove_session", sessionid=msid)
