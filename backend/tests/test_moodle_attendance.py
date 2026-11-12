"""T34: mod_attendance in the local SPeCTRUM simulation (needs backend/moodle up + setup.sh + seed.sh)."""
import time

import pytest

from app.services.kb.moodle_client import MoodleClient, MoodleError
from app.services.moodle_auth import get_user_token

COURSES = ["WIF3001", "WIF3004", "WIA2005", "WIA0000"]


async def _attendance_id(client: MoodleClient, shortname: str) -> int:
    course_id = await client.get_course_id(shortname)
    assert course_id, f"{shortname} not in Moodle (run seed.sh)"
    sections = await client.call("core_course_get_contents", courseid=course_id)
    ids = [m["instance"] for s in sections for m in s.get("modules", []) if m.get("modname") == "attendance"]
    assert len(ids) == 1, f"{shortname} should have exactly one Attendance activity, found {ids}"
    return ids[0]


@pytest.mark.moodle
@pytest.mark.parametrize("shortname", COURSES)
async def test_every_seeded_course_has_one_attendance_activity(shortname):
    async with MoodleClient() as c:
        await _attendance_id(c, shortname)


@pytest.mark.moodle
async def test_get_sessions_works_with_service_token():
    async with MoodleClient() as c:
        body = await c.call("mod_attendance_get_sessions", attendanceid=await _attendance_id(c, "WIA0000"))
    assert isinstance(body, list)


@pytest.mark.moodle
async def test_service_can_add_and_remove_a_session_with_four_statuses():
    async with MoodleClient() as c:
        aid = await _attendance_id(c, "WIA0000")
        add = await c.call("mod_attendance_add_session", attendanceid=aid, description="T34 test",
                           sessiontime=int(time.time()), duration=3600, addcalendarevent=0)
        sid = add["sessionid"]
        try:
            sess = await c.call("mod_attendance_get_session", sessionid=sid)
            assert sess["studentscanmark"] == 0
            assert {s["acronym"] for s in sess["statuses"]} >= {"P", "L", "E", "A"}
            sessions = await c.call("mod_attendance_get_sessions", attendanceid=aid)
            assert sid in [s["id"] for s in sessions]
        finally:
            await c.call("mod_attendance_remove_session", sessionid=sid)


@pytest.mark.moodle
async def test_student_token_cannot_read_attendance_sessions():
    async with MoodleClient() as c:
        aid = await _attendance_id(c, "WIA0000")
    tok = await get_user_token("student1", "Student123!")
    async with MoodleClient(token=tok) as s:
        with pytest.raises(MoodleError):
            await s.call("mod_attendance_get_sessions", attendanceid=aid)
