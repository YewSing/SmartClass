"""T36: re-sync after override, Moodle mismatch check, conflict choice, retry now (FR-312, FR-320).

Moodle is the respx fake from the T35 tests (`fake.log[moodle session id][moodle user id] = status id`).
"""
import json
import random
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.core.config import settings
from app.models.attendance import AttendanceRecord
from app.models.audit import AuditLog
from app.models.class_ import ClassOccurrence, Course
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.services import attendance_moodle_sync as sync
from app.services.kb.moodle_client import MoodleClient
from tests import test_attendance_moodle_sync as t35
from tests.test_attendance_moodle_sync import STATUS_IDS, _closed_session, _records, _run, _session, at

pytestmark = pytest.mark.db

fake_moodle = t35.fake_moodle   # the T35 fixtures
linked = t35.linked


async def _synced(db, classroom, fake, statuses=("present", "late", "absent")) -> tuple[int, int]:
    """A CS101 session synced at 12:00. Returns (session id, Moodle session id)."""
    session_id = await _closed_session(db, classroom, list(statuses))
    assert await _run(fake, at(12)) == {session_id: "synced"}
    (msid,) = fake.sessions
    return session_id, msid


async def _audits(db, action: str) -> list[AuditLog]:
    db.expire_all()
    return list((await db.execute(select(AuditLog).where(AuditLog.action == action)
                                  .order_by(AuditLog.id))).scalars())


@pytest.fixture
def fixed_clock(monkeypatch):
    """Endpoints that call sync.clock() see 13:00 on the class day."""
    monkeypatch.setattr(sync, "clock", lambda: at(13))


# ── re-sync after an override (FR-312) ──────────────────────────────────────

async def test_override_of_a_synced_session_requeues_and_sends_only_that_student(
        fake_moodle, classroom, linked, db_session, lecturer_client):
    session_id, msid = await _synced(db_session, classroom, fake_moodle)
    s1, s2, s3 = classroom["student_ids"]
    rec = (await _records(db_session, session_id))[s3]

    resp = await lecturer_client.put(f"/attendance/{rec.id}/override",
                                     json={"status": "excused", "reason": "MC"})
    assert resp.status_code == 200, resp.text
    s = await _session(db_session, session_id)
    assert s.moodle_sync_status == "pending" and s.moodle_sync_next_at is not None

    sent_before = fake_moodle.count("mod_attendance_update_user_status")
    assert await _run(fake_moodle, s.moodle_sync_next_at) == {session_id: "synced"}
    assert fake_moodle.count("mod_attendance_update_user_status") == sent_before + 1
    assert fake_moodle.log[msid][503] == STATUS_IDS["E"]
    assert (await _records(db_session, session_id))[s3].moodle_status_sent == "excused"


async def test_session_override_endpoint_requeues_a_new_record(fake_moodle, classroom, linked, db_session,
                                                               lecturer_client):
    session_id, msid = await _synced(db_session, classroom, fake_moodle, ("present", "late", None))
    s3 = classroom["student_ids"][2]
    resp = await lecturer_client.put(f"/lecturer/sessions/{session_id}/attendance/override",
                                     json={"student_id": s3, "status": "absent"})
    assert resp.status_code == 200, resp.text
    s = await _session(db_session, session_id)
    assert s.moodle_sync_status == "pending"
    assert await _run(fake_moodle, s.moodle_sync_next_at) == {session_id: "synced"}
    assert fake_moodle.log[msid] == {501: STATUS_IDS["P"], 502: STATUS_IDS["L"], 503: STATUS_IDS["A"]}


async def test_override_of_an_open_session_queues_nothing(classroom, db_session, lecturer_client):
    resp = await lecturer_client.post("/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]})
    session_id = resp.json()["id"]
    resp = await lecturer_client.put(f"/lecturer/sessions/{session_id}/attendance/override",
                                     json={"student_id": classroom["student_ids"][0], "status": "present"})
    assert resp.status_code == 200, resp.text
    assert (await _session(db_session, session_id)).moodle_sync_status is None


async def test_override_of_a_failed_session_retries_now_without_waiting_for_backoff(
        fake_moodle, classroom, linked, db_session):
    session_id = await _closed_session(db_session, classroom, ["present", "late", "absent"])
    fake_moodle.down = True
    await _run(fake_moodle, at(12))
    s = await _session(db_session, session_id)
    assert s.moodle_sync_attempts == 1
    sync.queue_resync(s, at(12, 1))
    await db_session.commit()
    s = await _session(db_session, session_id)
    assert (s.moodle_sync_status, s.moodle_sync_attempts, s.moodle_sync_next_at) == ("pending", 0, at(12, 1))


# ── changed in Moodle: never overwritten, session becomes `conflict` (FR-320) ──

async def test_a_status_changed_in_moodle_is_not_overwritten_by_a_resync(fake_moodle, classroom, linked,
                                                                         db_session, lecturer_client):
    session_id, msid = await _synced(db_session, classroom, fake_moodle)
    s1, s2, s3 = classroom["student_ids"]
    fake_moodle.log[msid][501] = STATUS_IDS["E"]      # someone set student 1 to Excused in Moodle

    # The lecturer overrides students 1 and 3 in SmartClass
    recs = await _records(db_session, session_id)
    for sid, st in ((s1, "late"), (s3, "present")):
        resp = await lecturer_client.put(f"/attendance/{recs[sid].id}/override", json={"status": st})
        assert resp.status_code == 200, resp.text
    s = await _session(db_session, session_id)
    assert await _run(fake_moodle, s.moodle_sync_next_at) == {session_id: "conflict"}

    assert fake_moodle.log[msid][501] == STATUS_IDS["E"]   # Moodle's change kept
    assert fake_moodle.log[msid][503] == STATUS_IDS["P"]   # the other override still went through
    recs = await _records(db_session, session_id)
    assert (recs[s1].status, recs[s1].moodle_status_found, recs[s1].moodle_status_sent) == (
        "late", "excused", "present")
    assert recs[s3].moodle_status_found is None
    s1_record = recs[s1].id
    s = await _session(db_session, session_id)
    assert s.moodle_sync_status == "conflict" and s.moodle_sync_next_at is None
    assert "1 student(s) were changed in Moodle" in s.moodle_sync_error

    # Both values are in the session API
    resp = await lecturer_client.get("/lecturer/sessions")
    out = next(x for x in resp.json() if x["id"] == session_id)
    assert out["moodle_sync_status"] == "conflict"
    (conflict,) = out["moodle_conflicts"]
    assert conflict == {"record_id": s1_record, "student_id": s1, "matric_no": conflict["matric_no"],
                        "name": conflict["name"], "smartclass_status": "late", "moodle_status": "excused",
                        "keep_smartclass": False}


async def test_a_moodle_mark_removed_or_unknown_is_a_conflict(fake_moodle, classroom, linked, db_session):
    session_id, msid = await _synced(db_session, classroom, fake_moodle)
    s1, s2, s3 = classroom["student_ids"]
    del fake_moodle.log[msid][501]                     # mark removed in Moodle
    fake_moodle.log[msid][502] = 77                    # a status SmartClass doesn't have
    await db_session.execute(update(AttendanceSession).where(AttendanceSession.id == session_id)
                             .values(moodle_sync_status="pending", moodle_sync_next_at=at(13)))
    await db_session.commit()
    assert await _run(fake_moodle, at(13)) == {session_id: "conflict"}
    recs = await _records(db_session, session_id)
    assert (recs[s1].moodle_status_found, recs[s2].moodle_status_found) == ("none", "other")
    assert 501 not in fake_moodle.log[msid] and fake_moodle.log[msid][502] == 77


async def test_moodle_already_holding_smartclass_value_is_not_a_conflict(fake_moodle, classroom, linked,
                                                                         db_session):
    session_id, msid = await _synced(db_session, classroom, fake_moodle)
    s1 = classroom["student_ids"][0]
    fake_moodle.log[msid][501] = STATUS_IDS["E"]       # changed in Moodle to what SmartClass now says too
    rec = (await _records(db_session, session_id))[s1]
    rec.status = "excused"
    sync.queue_resync(await db_session.get(AttendanceSession, session_id), at(13))
    await db_session.commit()
    sent = fake_moodle.count("mod_attendance_update_user_status")
    assert await _run(fake_moodle, at(13)) == {session_id: "synced"}
    assert fake_moodle.count("mod_attendance_update_user_status") == sent
    assert (await _records(db_session, session_id))[s1].moodle_status_sent == "excused"


async def test_relinked_moodle_session_does_not_report_old_marks_as_conflicts(fake_moodle, classroom, linked,
                                                                              db_session):
    """The Moodle session was deleted; the new one is empty, so everything is sent again."""
    session_id, old = await _synced(db_session, classroom, fake_moodle)
    del fake_moodle.sessions[old]
    sync.queue_resync(await db_session.get(AttendanceSession, session_id), at(13))
    await db_session.commit()
    assert await _run(fake_moodle, at(13)) == {session_id: "synced"}
    (new,) = fake_moodle.sessions
    assert new != old and fake_moodle.log[new] == {501: STATUS_IDS["P"], 502: STATUS_IDS["L"],
                                                   503: STATUS_IDS["A"]}


# ── scheduled check of synced sessions ──────────────────────────────────────

async def test_scheduled_check_reads_synced_sessions_and_finds_a_change(fake_moodle, classroom, linked,
                                                                        db_session):
    session_id, msid = await _synced(db_session, classroom, fake_moodle)
    interval = timedelta(seconds=settings.MOODLE_ATTENDANCE_CHECK_INTERVAL_SECONDS)
    calls = len(fake_moodle.calls)
    assert await _run(fake_moodle, at(12) + interval - timedelta(seconds=1)) == {}   # not due yet
    assert len(fake_moodle.calls) == calls

    # Nothing changed: the check sends nothing and the session stays synced
    assert await _run(fake_moodle, at(12) + interval) == {session_id: "synced"}
    assert fake_moodle.count("mod_attendance_update_user_status") == 3
    s = await _session(db_session, session_id)
    assert s.moodle_checked_at == at(12) + interval

    fake_moodle.log[msid][502] = STATUS_IDS["A"]       # changed in Moodle
    assert await _run(fake_moodle, at(12) + 2 * interval) == {session_id: "conflict"}
    assert fake_moodle.log[msid][502] == STATUS_IDS["A"]
    assert (await _records(db_session, session_id))[classroom["student_ids"][1]].moodle_status_found == "absent"

    # Moodle changed back to what was sent: the next check clears the conflict on its own
    fake_moodle.log[msid][502] = STATUS_IDS["L"]
    assert await _run(fake_moodle, at(12) + 3 * interval) == {session_id: "synced"}
    assert (await _records(db_session, session_id))[classroom["student_ids"][1]].moodle_status_found is None


async def test_scheduled_check_skips_old_sessions(fake_moodle, classroom, linked, db_session):
    session_id, _ = await _synced(db_session, classroom, fake_moodle)
    later = at(10) + timedelta(days=settings.MOODLE_ATTENDANCE_CHECK_DAYS, seconds=1)
    assert await _run(fake_moodle, later) == {}


async def test_a_failed_scheduled_check_keeps_the_status(fake_moodle, classroom, linked, db_session):
    session_id, _ = await _synced(db_session, classroom, fake_moodle)
    when = at(12) + timedelta(seconds=settings.MOODLE_ATTENDANCE_CHECK_INTERVAL_SECONDS)
    fake_moodle.down = True
    assert await _run(fake_moodle, when) == {session_id: "synced"}
    s = await _session(db_session, session_id)
    assert (s.moodle_sync_status, s.moodle_sync_attempts, s.moodle_sync_error) == ("synced", 0, None)
    assert s.moodle_checked_at == when
    assert await _run(fake_moodle, when + timedelta(minutes=1)) == {}   # not retried every loop


# ── the lecturer's choice ───────────────────────────────────────────────────

async def _conflict(db, classroom, fake, moodle_status_id) -> tuple[int, int, int]:
    """Synced session where student 1 was changed in Moodle. Returns (session, Moodle session, record)."""
    session_id, msid = await _synced(db, classroom, fake)
    fake.log[msid][501] = moodle_status_id
    await db.execute(update(AttendanceSession).where(AttendanceSession.id == session_id)
                     .values(moodle_sync_status="pending", moodle_sync_next_at=at(12, 30)))
    await db.commit()
    assert await _run(fake, at(12, 30)) == {session_id: "conflict"}
    rec = (await _records(db, session_id))[classroom["student_ids"][0]]
    return session_id, msid, rec.id


async def test_keep_smartclass_value_overwrites_moodle_on_next_sync(fake_moodle, classroom, linked, db_session,
                                                                    lecturer_client, fixed_clock):
    session_id, msid, record_id = await _conflict(db_session, classroom, fake_moodle, STATUS_IDS["E"])
    resp = await lecturer_client.post(f"/lecturer/sessions/{session_id}/moodle-conflicts/{record_id}",
                                      json={"keep": "smartclass"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["moodle_sync_status"] == "pending"
    assert body["moodle_conflicts"][0]["keep_smartclass"] is True

    (audit,) = await _audits(db_session, "MOODLE_CONFLICT_RESOLVED")
    assert json.loads(audit.old_val) == {"smartclass": "present", "moodle": "excused"}
    assert json.loads(audit.new_val) == {"keep": "smartclass", "status": "present"}

    assert await _run(fake_moodle, at(13)) == {session_id: "synced"}
    assert fake_moodle.log[msid][501] == STATUS_IDS["P"]
    rec = await db_session.get(AttendanceRecord, record_id)
    assert (rec.moodle_status_found, rec.moodle_overwrite_ok, rec.moodle_status_sent) == (None, False, "present")


async def test_keep_smartclass_but_moodle_changed_again_is_a_new_conflict(fake_moodle, classroom, linked,
                                                                          db_session, lecturer_client,
                                                                          fixed_clock):
    session_id, msid, record_id = await _conflict(db_session, classroom, fake_moodle, STATUS_IDS["E"])
    await lecturer_client.post(f"/lecturer/sessions/{session_id}/moodle-conflicts/{record_id}",
                               json={"keep": "smartclass"})
    fake_moodle.log[msid][501] = STATUS_IDS["L"]       # changed again before the re-sync
    assert await _run(fake_moodle, at(13)) == {session_id: "conflict"}
    assert fake_moodle.log[msid][501] == STATUS_IDS["L"]
    db_session.expire_all()
    rec = await db_session.get(AttendanceRecord, record_id)
    assert (rec.moodle_status_found, rec.moodle_overwrite_ok) == ("late", False)


async def test_take_moodle_value_updates_smartclass_and_is_audited(fake_moodle, classroom, linked, db_session,
                                                                   lecturer_client, fixed_clock, users):
    session_id, msid, record_id = await _conflict(db_session, classroom, fake_moodle, STATUS_IDS["E"])
    resp = await lecturer_client.post(f"/lecturer/sessions/{session_id}/moodle-conflicts/{record_id}",
                                      json={"keep": "moodle"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["moodle_conflicts"] == []

    db_session.expire_all()
    rec = await db_session.get(AttendanceRecord, record_id)
    assert (rec.status, rec.moodle_status_sent, rec.moodle_status_found) == ("excused", "excused", None)
    assert (rec.override_by, rec.override_at) == (users["lecturer"].id, at(13))
    (audit,) = await _audits(db_session, "MOODLE_CONFLICT_RESOLVED")
    assert audit.actor_id == users["lecturer"].id
    assert json.loads(audit.new_val) == {"keep": "moodle", "status": "excused"}

    sent = fake_moodle.count("mod_attendance_update_user_status")
    assert await _run(fake_moodle, at(13)) == {session_id: "synced"}
    assert fake_moodle.count("mod_attendance_update_user_status") == sent   # Moodle already has it


async def test_take_moodle_value_is_refused_when_moodle_has_no_usable_status(fake_moodle, classroom, linked,
                                                                             db_session, lecturer_client):
    session_id, msid, record_id = await _conflict(db_session, classroom, fake_moodle, 77)
    resp = await lecturer_client.post(f"/lecturer/sessions/{session_id}/moodle-conflicts/{record_id}",
                                      json={"keep": "moodle"})
    assert resp.status_code == 409
    resp = await lecturer_client.post(f"/lecturer/sessions/{session_id}/moodle-conflicts/{record_id}",
                                      json={"keep": "smartclass"})
    assert resp.status_code == 200


async def test_resolve_checks_the_record(fake_moodle, classroom, linked, db_session, lecturer_client,
                                         other_lecturer_client):
    session_id, msid, record_id = await _conflict(db_session, classroom, fake_moodle, STATUS_IDS["E"])
    other = (await _records(db_session, session_id))[classroom["student_ids"][1]]
    url = f"/lecturer/sessions/{session_id}/moodle-conflicts"
    assert (await lecturer_client.post(f"{url}/{other.id}", json={"keep": "smartclass"})).status_code == 409
    assert (await lecturer_client.post(f"{url}/999999", json={"keep": "smartclass"})).status_code == 404
    assert (await lecturer_client.post(f"{url}/{record_id}", json={"keep": "both"})).status_code == 422
    assert (await other_lecturer_client.post(f"{url}/{record_id}", json={"keep": "moodle"})).status_code == 403


# ── retry now ───────────────────────────────────────────────────────────────

async def test_retry_now_sends_a_failed_session_at_once(fake_moodle, classroom, linked, db_session,
                                                        lecturer_client, fixed_clock):
    session_id = await _closed_session(db_session, classroom, ["present", "late", "absent"])
    fake_moodle.down = True
    await _run(fake_moodle, at(12))
    assert (await _session(db_session, session_id)).moodle_sync_status == "failed"

    fake_moodle.down = False
    resp = await lecturer_client.post(f"/lecturer/sessions/{session_id}/moodle-sync")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["moodle_sync_status"], body["moodle_synced_at"], body["moodle_sync_error"]) == (
        "synced", at(13).isoformat(), None)
    (msid,) = fake_moodle.sessions
    assert len(fake_moodle.log[msid]) == 3
    assert (await _session(db_session, session_id)).moodle_sync_status == "synced"   # committed


async def test_retry_now_reports_a_failure(fake_moodle, classroom, linked, db_session, lecturer_client,
                                           fixed_clock):
    session_id = await _closed_session(db_session, classroom, ["present", "late", "absent"])
    fake_moodle.down = True
    resp = await lecturer_client.post(f"/lecturer/sessions/{session_id}/moodle-sync")
    assert resp.status_code == 200
    assert (resp.json()["moodle_sync_status"], resp.json()["moodle_sync_error"]) == ("failed", "HTTPStatusError")


async def test_retry_now_refuses_open_sessions_other_lecturers_and_missing_config(
        classroom, db_session, lecturer_client, other_lecturer_client, monkeypatch):
    resp = await lecturer_client.post("/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]})
    open_id = resp.json()["id"]
    assert (await lecturer_client.post(f"/lecturer/sessions/{open_id}/moodle-sync")).status_code == 409
    assert (await other_lecturer_client.post(f"/lecturer/sessions/{open_id}/moodle-sync")).status_code == 403

    closed_id = await _closed_session(db_session, classroom, ["present", None, None])
    monkeypatch.setattr(settings, "MOODLE_TOKEN", "")
    assert (await lecturer_client.post(f"/lecturer/sessions/{closed_id}/moodle-sync")).status_code == 503


@pytest.mark.moodle
async def test_end_to_end_conflict_in_local_moodle(db_session):
    """A status changed in the local Moodle is found by the scheduled check and not overwritten;
    keeping SmartClass's value then puts it back in Moodle."""
    async with MoodleClient() as c:
        course_id = await c.get_course_id("WIA0000")
        assert course_id, "WIA0000 not in Moodle (run seed.sh)"
        enrolled = await c.call("core_enrol_get_enrolled_users", courseid=course_id)
    students = [u for u in enrolled if "student" in {r["shortname"] for r in u.get("roles", [])}][:2]
    assert len(students) == 2, "WIA0000 needs at least 2 students in Moodle"

    lec_user = User(email="t36.lecturer@um.edu.my", role="lecturer", name="T36 Lecturer", status="active")
    db_session.add(lec_user)
    await db_session.flush()
    lec_user_id = lec_user.id
    lec = Lecturer(user_id=lec_user_id, staff_id="T36-STAFF")
    course = Course(code="WIA0000", name="Test course")
    db_session.add_all([lec, course])
    await db_session.flush()
    occ = ClassOccurrence(course_id=course.id, type="LECTURE", lecturer_id=lec.id)
    db_session.add(occ)
    await db_session.flush()
    start = datetime(2026, 1, 5, 8, 0) + timedelta(minutes=random.randrange(100_000))
    s = AttendanceSession(occurrence_id=occ.id, lecturer_id=lec.id, status="closed", class_date=start.date(),
                          starts_at=start, ends_at=start + timedelta(hours=1), opened_at=start,
                          closed_at=start + timedelta(hours=1), source="manual", moodle_sync_status="pending",
                          moodle_sync_next_at=start + timedelta(hours=1))
    db_session.add(s)
    await db_session.flush()
    session_id = s.id
    record_ids = []
    for i, u in enumerate(students):
        su = User(email=f"t36.s{i}@siswa.um.edu.my", role="student", name=u.get("fullname", "S"),
                  status="active", moodle_user_id=int(u["id"]))
        db_session.add(su)
        await db_session.flush()
        st = Student(user_id=su.id, matric_no=f"T36S{i}")
        db_session.add(st)
        await db_session.flush()
        rec = AttendanceRecord(session_id=session_id, student_id=st.id, status="present")
        db_session.add(rec)
        await db_session.flush()
        record_ids.append(rec.id)
    await db_session.commit()

    msid = None
    t = start + timedelta(hours=2)
    try:
        async with MoodleClient() as c:
            assert await sync.run_due(client=c, now=t) == {session_id: "synced"}
            msid = (await _session(db_session, session_id)).moodle_session_id
            got = await c.call("mod_attendance_get_session", sessionid=msid)
            by_acronym = {st["acronym"]: int(st["id"]) for st in got["statuses"]
                          if int(st["setnumber"]) == int(got["statusset"]) and not int(st["deleted"])}
            info = await c.call("core_webservice_get_site_info")
            # Someone marks the first student Excused directly in Moodle
            await c.call("mod_attendance_update_user_status", sessionid=msid, studentid=int(students[0]["id"]),
                         takenbyid=int(info["userid"]), statusid=by_acronym["E"], statusset=got["statusset"])

            t += timedelta(seconds=settings.MOODLE_ATTENDANCE_CHECK_INTERVAL_SECONDS)
            assert await sync.run_due(client=c, now=t) == {session_id: "conflict"}
            sess = await _session(db_session, session_id)
            rec = await db_session.get(AttendanceRecord, record_ids[0])
            assert (rec.status, rec.moodle_status_found) == ("present", "excused")
            await sync.resolve_conflict(db_session, sess, rec, "smartclass", lec_user_id, t)
            await db_session.commit()
            assert await sync.run_due(client=c, now=t) == {session_id: "synced"}
            got = await c.call("mod_attendance_get_session", sessionid=msid)
            by_user = {int(e["studentid"]): int(e["statusid"]) for e in got["attendance_log"]}
            assert by_user[int(students[0]["id"])] == by_acronym["P"]
    finally:
        if msid:
            async with MoodleClient() as c:
                await c.call("mod_attendance_remove_session", sessionid=msid)


async def test_session_api_shows_sync_status(fake_moodle, classroom, linked, db_session, lecturer_client):
    session_id, _ = await _synced(db_session, classroom, fake_moodle)
    resp = await lecturer_client.get("/lecturer/sessions")
    out = next(x for x in resp.json() if x["id"] == session_id)
    assert (out["moodle_sync_status"], out["moodle_synced_at"], out["moodle_conflicts"]) == (
        "synced", at(12).isoformat(), [])
    assert "moodle_sync_next_at" in out and "moodle_sync_error" in out
