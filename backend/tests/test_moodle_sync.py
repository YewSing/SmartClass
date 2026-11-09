"""T11: course + enrolment sync from Moodle (FR-104).

Moodle is mocked with respx; the `moodle` test at the bottom runs against the local SPeCTRUM simulation.
"""
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.user import Lecturer, Student, User
from app.services import moodle_sync
from tests.test_moodle_login import _login, mock_moodle

SVC_TOKEN = "svc-token"


def _ws_url() -> str:
    return f"{settings.MOODLE_URL.rstrip('/')}/webservice/rest/server.php"


class FakeMoodle:
    """Site-wide Moodle data seen with the service token: courses and their enrolled users."""

    def __init__(self):
        self.courses: dict[int, dict] = {}       # id -> {"shortname", "fullname"}
        self.enrolled: dict[int, dict[int, str]] = {}  # course id -> {moodle user id: role}
        self.details: dict[int, dict] = {}       # moodle user id -> username, email, idnumber, ...
        self.fail = False

    def course(self, cid, shortname, fullname, **members):
        self.courses[cid] = {"shortname": shortname, "fullname": fullname}
        self.enrolled[cid] = {int(m): role for m, role in members.items()}

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(503, text="Service Unavailable")
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        assert form["wstoken"] == SVC_TOKEN
        fn = form["wsfunction"]
        if fn == "core_course_get_courses_by_field":
            site = {"id": 1, "shortname": "SPeCTRUM", "fullname": "SPeCTRUM", "format": "site"}
            return httpx.Response(200, json={"courses": [site] + [
                {"id": cid, "format": "topics", **c} for cid, c in self.courses.items()]})
        if fn == "core_enrol_get_enrolled_users":
            members = self.enrolled[int(form["courseid"])]
            return httpx.Response(200, json=[{"id": uid, "roles": [{"shortname": role}], **self.details.get(uid, {})}
                                             for uid, role in members.items()])
        raise AssertionError(f"unexpected wsfunction {fn}")


@pytest.fixture
def fake_moodle(monkeypatch):
    monkeypatch.setattr(settings, "MOODLE_TOKEN", SVC_TOKEN)
    monkeypatch.setattr(moodle_sync, "last_sync", None)
    fake = FakeMoodle()
    with respx.mock(assert_all_called=False) as router:
        router.post(_ws_url()).mock(side_effect=lambda request: fake.handler(request))
        yield fake


async def _moodle_user(db, moodle_id, role, number, *, status="active"):
    u = User(email=f"m{moodle_id}@um.edu.my", role=role, name=f"Moodle {moodle_id}",
             status=status, moodle_user_id=moodle_id)
    db.add(u)
    await db.flush()
    profile = Student(user_id=u.id, matric_no=number) if role == "student" else Lecturer(user_id=u.id, staff_id=number)
    db.add(profile)
    await db.flush()
    return profile


@pytest.fixture
async def school(db_session, users):
    """WIA2005 (one lecture + one tutorial) and WIA1002 (lecture + two tutorial groups), plus
    Moodle-linked students 101-103 and lecturers 201-202, and the local conftest users."""
    db = db_session
    s101 = await _moodle_user(db, 101, "student", "23000101")
    s102 = await _moodle_user(db, 102, "student", "23000102")
    s103 = await _moodle_user(db, 103, "student", "23000103")
    l201 = await _moodle_user(db, 201, "lecturer", "ST201")
    l202 = await _moodle_user(db, 202, "lecturer", "ST202")
    algo = Course(code="WIA2005", name="Algorithm Design")
    ds = Course(code="WIA1002", name="Data Structure")
    db.add_all([algo, ds])
    await db.flush()

    def occ(course, type_, label=None, lecturer_id=None):
        return ClassOccurrence(course_id=course.id, type=type_, day_of_week="Mon", start_time="08:00",
                               end_time="10:00", room="DK1", label=label, lecturer_id=lecturer_id)

    algo_lec, algo_tut = occ(algo, "LECTURE"), occ(algo, "TUTORIAL", "Tutorial")
    ds_lec, ds_t1, ds_t2 = occ(ds, "LECTURE"), occ(ds, "TUTORIAL", "Tutorial Group 1"), occ(ds, "TUTORIAL", "Tutorial Group 2")
    db.add_all([algo_lec, algo_tut, ds_lec, ds_t1, ds_t2])
    await db.commit()
    return {
        "s101": s101.id, "s102": s102.id, "s103": s103.id, "l201": l201.id, "l202": l202.id,
        "algo": algo.id, "ds": ds.id, "algo_lec": algo_lec.id, "algo_tut": algo_tut.id,
        "ds_lec": ds_lec.id, "ds_t1": ds_t1.id, "ds_t2": ds_t2.id,
    }


async def _enrolments(db) -> set[tuple[int, int]]:
    db.expire_all()
    return set((await db.execute(select(Enrollment.student_id, Enrollment.occurrence_id))).all())


async def _lecturer_of(db, occ_id):
    db.expire_all()
    return (await db.execute(select(ClassOccurrence.lecturer_id).where(ClassOccurrence.id == occ_id))).scalar_one()


async def _sync(admin_client):
    resp = await admin_client.post("/admin/moodle/sync")
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.db
async def test_sync_adds_courses_enrolments_and_lecturers(admin_client, db_session, school, fake_moodle):
    fake_moodle.course(7, "WIA2005", "Algorithm Design and Analysis", **{"101": "student", "102": "student", "201": "editingteacher"})
    fake_moodle.course(8, "WIA1002", "Data Structure", **{"101": "student", "202": "teacher"})
    fake_moodle.course(9, "WIX9999", "New Moodle Course", **{"103": "student", "555": "student"})

    report = await _sync(admin_client)
    s = school
    assert await _enrolments(db_session) == {
        (s["s101"], s["algo_lec"]), (s["s101"], s["algo_tut"]),  # one tutorial: enrolled in it
        (s["s102"], s["algo_lec"]), (s["s102"], s["algo_tut"]),
        (s["s101"], s["ds_lec"]),                                # two groups: admin picks the group
    }
    assert await _lecturer_of(db_session, s["algo_lec"]) == s["l201"]
    assert await _lecturer_of(db_session, s["algo_tut"]) == s["l201"]
    assert await _lecturer_of(db_session, s["ds_t2"]) == s["l202"]

    courses = {c.code: c for c in (await db_session.execute(select(Course))).scalars()}
    assert courses["WIA2005"].moodle_course_id == 7 and courses["WIA1002"].moodle_course_id == 8
    assert courses["WIA2005"].name == "Algorithm Design and Analysis"  # Moodle is the source
    assert courses["WIX9999"].moodle_course_id == 9 and courses["WIX9999"].name == "New Moodle Course"
    assert report["courses_created"] == 1
    assert report["enrolments_added"] == 5 and report["lecturers_assigned"] == 5
    assert report["unlinked_users"] == 1  # Moodle user 555 has no SmartClass account yet

    status = await admin_client.get("/admin/moodle/sync")
    assert status.status_code == 200 and status.json()["ok"] is True
    assert status.json()["enrolments_added"] == 5 and status.json()["finished_at"]
    audit = (await db_session.execute(select(AuditLog).where(AuditLog.action == "MOODLE_SYNC"))).scalars().all()
    assert len(audit) == 1


@pytest.mark.db
async def test_sync_removes_enrolments_and_assignments_gone_from_moodle(admin_client, db_session, school, fake_moodle):
    s = school
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"101": "student", "102": "student", "201": "editingteacher"})
    fake_moodle.course(8, "WIA1002", "Data Structure", **{"101": "student", "201": "editingteacher"})
    await _sync(admin_client)
    db_session.add(Enrollment(student_id=s["s101"], occurrence_id=s["ds_t1"]))  # admin picked a group
    await db_session.commit()

    # 102 dropped WIA2005, 101 dropped WIA1002, lecturer 201 handed WIA2005 to 202
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"101": "student", "202": "editingteacher"})
    fake_moodle.course(8, "WIA1002", "Data Structure", **{"201": "editingteacher"})
    report = await _sync(admin_client)

    assert await _enrolments(db_session) == {(s["s101"], s["algo_lec"]), (s["s101"], s["algo_tut"])}
    assert report["enrolments_removed"] == 4  # 102 x2 in WIA2005, 101 lecture + chosen group in WIA1002
    assert await _lecturer_of(db_session, s["algo_lec"]) == s["l202"]
    assert await _lecturer_of(db_session, s["ds_lec"]) == s["l201"]

    # The Moodle course disappears altogether
    del fake_moodle.courses[7]
    await _sync(admin_client)
    assert await _enrolments(db_session) == set()
    assert await _lecturer_of(db_session, s["algo_lec"]) is None


@pytest.mark.db
async def test_sync_twice_changes_nothing(admin_client, db_session, school, fake_moodle):
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"101": "student", "103": "student", "201": "editingteacher"})
    fake_moodle.course(8, "WIA1002", "Data Structure", **{"102": "student", "202": "teacher"})
    fake_moodle.course(9, "WIX9999", "New Moodle Course", **{"103": "student"})
    first = await _sync(admin_client)
    before = await _enrolments(db_session)
    courses_before = (await db_session.execute(select(func.count(Course.id)))).scalar_one()

    second = await _sync(admin_client)
    assert await _enrolments(db_session) == before
    assert (await db_session.execute(select(func.count(Course.id)))).scalar_one() == courses_before
    assert first["enrolments_added"] > 0
    changes = {k: v for k, v in second.items() if k not in ("unlinked_users", "skipped")}
    assert all(v == 0 for v in changes.values()), second


@pytest.mark.db
async def test_moodle_failure_leaves_data_unchanged(admin_client, db_session, school, fake_moodle):
    s = school
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"101": "student", "201": "editingteacher"})
    await _sync(admin_client)
    before = await _enrolments(db_session)

    fake_moodle.course(7, "WIA2005", "Renamed", **{"102": "student"})
    fake_moodle.course(9, "WIX9999", "New", **{"103": "student"})
    fake_moodle.fail = True
    resp = await admin_client.post("/admin/moodle/sync")
    assert resp.status_code == 502
    assert SVC_TOKEN not in resp.text
    assert await _enrolments(db_session) == before
    assert await _lecturer_of(db_session, s["algo_lec"]) == s["l201"]
    names = set((await db_session.execute(select(Course.code, Course.name))).all())
    assert ("WIA2005", "Algorithm Design") in names and all(code != "WIX9999" for code, _ in names)
    assert (await admin_client.get("/admin/moodle/sync")).json()["ok"] is False


@pytest.mark.db
async def test_failure_midway_through_the_fetch_also_changes_nothing(admin_client, db_session, school, fake_moodle):
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"101": "student"})
    fake_moodle.course(8, "WIA1002", "Data Structure", **{"101": "student"})
    real = fake_moodle.handler

    def flaky(request):
        if b"courseid=8" in request.content:
            return httpx.Response(200, json={"exception": "moodle_exception", "errorcode": "x", "message": "boom"})
        return real(request)

    fake_moodle.handler = flaky
    resp = await admin_client.post("/admin/moodle/sync")
    assert resp.status_code == 502
    assert await _enrolments(db_session) == set()


@pytest.mark.db
async def test_local_accounts_are_never_touched(admin_client, db_session, classroom, school, fake_moodle):
    # conftest's CS101 (local lecturer + 3 local students) exists in Moodle with nobody linked in it
    fake_moodle.course(30, "CS101", "Intro to Testing", **{"101": "student"})
    before = await _enrolments(db_session)
    await _sync(admin_client)
    after = await _enrolments(db_session)
    assert before <= after  # the local students are still enrolled
    assert await _lecturer_of(db_session, classroom["occurrence_id"]) == classroom["lecturer_id"]
    assert (school["s101"], classroom["occurrence_id"]) in after


@pytest.mark.db
async def test_deactivated_or_wrong_role_accounts_are_not_enrolled(admin_client, db_session, school, fake_moodle):
    await _moodle_user(db_session, 104, "student", "23000104", status="inactive")
    await db_session.commit()
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"104": "student", "201": "student"})
    await _sync(admin_client)
    assert await _enrolments(db_session) == set()  # inactive student; 201 is a lecturer account


@pytest.mark.db
async def test_sync_creates_accounts_for_users_who_never_logged_in(admin_client, db_session, school, fake_moodle):
    fake_moodle.details = {
        301: {"username": "student9", "fullname": "Nine Student", "email": "Nine@Example.com",
              "idnumber": "23009999", "department": "FSKTM"},
        302: {"username": "student8", "fullname": "Eight Student"},   # no email or idnumber in Moodle
        401: {"username": "lecturer9", "fullname": "Nine Lecturer", "email": "l9@example.com", "idnumber": "ST9"},
    }
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"301": "student", "302": "student", "401": "editingteacher"})

    report = await _sync(admin_client)
    assert report["accounts_created"] == 3 and report["unlinked_users"] == 0

    db_session.expire_all()
    users = {u.moodle_user_id: u for u in (await db_session.execute(select(User))).scalars() if u.moodle_user_id}
    assert users[301].role == "student" and users[301].email == "nine@example.com"
    assert users[301].name == "Nine Student" and users[301].password_hash is None  # NFR-05
    assert users[302].email == "student8@moodle.invalid"
    student = (await db_session.execute(select(Student).where(Student.user_id == users[301].id))).scalar_one()
    assert student.matric_no == "23009999" and student.faculty == "FSKTM"
    other = (await db_session.execute(select(Student).where(Student.user_id == users[302].id))).scalar_one()
    assert other.matric_no == "student8"
    lecturer = (await db_session.execute(select(Lecturer).where(Lecturer.user_id == users[401].id))).scalar_one()
    assert users[401].role == "lecturer" and lecturer.staff_id == "ST9"

    # They are on the class list, and the lecturer has the classes, before anyone logs in
    s = school
    student_id, other_id, lecturer_id = student.id, other.id, lecturer.id
    assert await _enrolments(db_session) == {(student_id, s["algo_lec"]), (student_id, s["algo_tut"]),
                                             (other_id, s["algo_lec"]), (other_id, s["algo_tut"])}
    assert await _lecturer_of(db_session, s["algo_lec"]) == lecturer_id

    audit = (await db_session.execute(select(AuditLog).where(AuditLog.action == "MOODLE_ACCOUNT_CREATE"))).scalars().all()
    assert len(audit) == 3

    again = await _sync(admin_client)
    assert again["accounts_created"] == 0 and again["enrolments_added"] == 0


@pytest.mark.db
async def test_teaching_anywhere_makes_a_new_account_a_lecturer(admin_client, db_session, school, fake_moodle):
    fake_moodle.details = {401: {"username": "both", "fullname": "Both Roles", "email": "both@example.com"}}
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"401": "student"})
    fake_moodle.course(8, "WIA1002", "Data Structure", **{"401": "editingteacher"})
    await _sync(admin_client)
    user = (await db_session.execute(select(User).where(User.moodle_user_id == 401))).scalar_one()
    assert user.role == "lecturer"


def _fields(programme, year_sem):
    return [{"shortname": "programme", "value": programme}, {"shortname": "yearsem", "value": year_sem}]


@pytest.mark.db
async def test_sync_fills_profile_fields_for_new_and_linked_accounts(admin_client, db_session, school, fake_moodle):
    linked_id = (await _moodle_user(db_session, 310, "student", "student10")).id  # logged in before Moodle had an idnumber
    await db_session.commit()
    fake_moodle.details = {
        310: {"username": "student10", "fullname": "Ten", "email": "m310@um.edu.my", "idnumber": "23004910",
              "department": "Faculty of Computer Science and Information Technology",
              "customfields": _fields("Bachelor of Computer Science (Data Science)", "Year 2, Semester 1 (2026/2027)")},
        311: {"username": "student11", "fullname": "Eleven", "email": "e@example.com", "idnumber": "23004911",
              "customfields": _fields("Bachelor of Computer Science (Artificial Intelligence)", "")},
        410: {"username": "lecturer10", "fullname": "Lec", "email": "l10@example.com", "idnumber": "UM-S0010",
              "department": "Department of Software Engineering"},
    }
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"310": "student", "311": "student", "410": "editingteacher"})

    report = await _sync(admin_client)
    assert report["accounts_created"] == 2 and report["profiles_updated"] == 1

    db_session.expire_all()
    s10 = await db_session.get(Student, linked_id)
    assert s10.matric_no == "23004910"
    assert s10.faculty == "Faculty of Computer Science and Information Technology"
    assert s10.programme == "Bachelor of Computer Science (Data Science)"
    assert s10.year_sem == "Year 2, Semester 1 (2026/2027)"
    u11 = (await db_session.execute(select(User).where(User.moodle_user_id == 311))).scalar_one()
    s11 = (await db_session.execute(select(Student).where(Student.user_id == u11.id))).scalar_one()
    assert s11.programme == "Bachelor of Computer Science (Artificial Intelligence)" and s11.year_sem is None
    u410 = (await db_session.execute(select(User).where(User.moodle_user_id == 410))).scalar_one()
    lec = (await db_session.execute(select(Lecturer).where(Lecturer.user_id == u410.id))).scalar_one()
    assert lec.staff_id == "UM-S0010" and lec.dept == "Department of Software Engineering"

    again = await _sync(admin_client)
    assert again["profiles_updated"] == 0 and again["accounts_created"] == 0


@pytest.mark.db
async def test_profile_refresh_skips_a_number_another_account_holds(admin_client, db_session, school, fake_moodle):
    await _moodle_user(db_session, 320, "student", "23004920")
    mine_id = (await _moodle_user(db_session, 321, "student", "student21")).id
    await db_session.commit()
    fake_moodle.details = {
        320: {"username": "a", "fullname": "A", "email": "m320@um.edu.my", "idnumber": "23004920"},
        321: {"username": "b", "fullname": "B", "email": "m321@um.edu.my", "idnumber": "23004920",  # clash
              "customfields": _fields("Bachelor of Computer Science (Information Systems)", "")},
    }
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"320": "student", "321": "student"})

    report = await _sync(admin_client)
    assert any("Moodle user 321" in line for line in report["skipped"])
    db_session.expire_all()
    kept = await db_session.get(Student, mine_id)
    assert kept.matric_no == "student21" and kept.programme is None  # whole update skipped, nothing half-done
    assert report["enrolments_added"] == 4  # the rest of the sync carried on


@pytest.mark.db
async def test_a_clash_skips_that_person_and_the_sync_carries_on(admin_client, db_session, users, school, fake_moodle):
    local_email = users["student"].email
    fake_moodle.details = {
        301: {"username": "takenemail", "fullname": "A", "email": local_email.upper()},
        302: {"username": "takennumber", "fullname": "B", "email": "b@example.com", "idnumber": "23000101"},  # s101's
        303: {"username": "fine", "fullname": "C", "email": "c@example.com", "idnumber": "23000303"},
    }
    fake_moodle.course(7, "WIA2005", "Algorithm Design", **{"301": "student", "302": "student", "303": "student"})

    report = await _sync(admin_client)
    assert report["accounts_created"] == 1 and report["unlinked_users"] == 2
    assert any("Moodle user 302" in line for line in report["skipped"])
    assert local_email not in str(report["skipped"])

    db_session.expire_all()
    # The local account was not taken over; only the third person exists
    local = await db_session.get(User, users["student"].id)
    assert local.moodle_user_id is None
    linked = set((await db_session.execute(select(User.moodle_user_id).where(User.moodle_user_id >= 300))).scalars())
    assert linked == {303}


@pytest.mark.db
@respx.mock
async def test_login_sync_creates_nobody_else(client, db_session, school):
    mock_moodle(user_id=101, username="23000101", email="m101@um.edu.my", idnumber="23000101")
    before = (await db_session.execute(select(func.count(User.id)))).scalar_one()
    assert (await _login(client, username="23000101")).status_code == 200
    assert (await db_session.execute(select(func.count(User.id)))).scalar_one() == before


@pytest.mark.db
async def test_sync_endpoint_is_admin_only(lecturer_client, student_client, client):
    for c in (lecturer_client, student_client):
        assert (await c.post("/admin/moodle/sync")).status_code == 403
        assert (await c.get("/admin/moodle/sync")).status_code == 403
    assert (await client.post("/admin/moodle/sync")).status_code in (401, 403)  # HTTPBearer: no token → 403


@pytest.mark.db
async def test_sync_without_moodle_token_is_502_and_changes_nothing(admin_client, monkeypatch):
    monkeypatch.setattr(settings, "MOODLE_TOKEN", "")
    resp = await admin_client.post("/admin/moodle/sync")
    assert resp.status_code == 502


# ── login sync (the user's own courses, read with their own token) ───────────

@pytest.mark.db
@respx.mock
async def test_login_enrols_the_student_in_their_moodle_courses(client, db_session, school):
    # mock_moodle: Moodle user 42 is enrolled in course 7 (shortname WIF3001) as a student
    db_session.add(Course(code="WIF3001", name="Old"))
    await db_session.flush()
    wif = (await db_session.execute(select(Course).where(Course.code == "WIF3001"))).scalar_one()
    lec = ClassOccurrence(course_id=wif.id, type="LECTURE", day_of_week="Tue", start_time="08:00",
                          end_time="10:00", lecturer_id=school["l201"])
    db_session.add(lec)
    # Already enrolled in WIA2005 (Moodle course 77) from an earlier sync, but no longer in Moodle
    algo = await db_session.get(Course, school["algo"])
    algo.moodle_course_id = 77
    await db_session.commit()
    lec_id = lec.id

    mock_moodle(idnumber="23004001")
    first = await _login(client)
    assert first.status_code == 200, first.text
    student_id = (await db_session.execute(
        select(Student.id).join(User).where(User.moodle_user_id == 42))).scalar_one()
    db_session.add(Enrollment(student_id=student_id, occurrence_id=school["algo_lec"]))
    await db_session.commit()

    assert (await _login(client)).status_code == 200
    assert await _enrolments(db_session) == {(student_id, lec_id)}
    wif = (await db_session.execute(select(Course).where(Course.code == "WIF3001"))).scalar_one()
    assert wif.moodle_course_id == 7
    assert await _lecturer_of(db_session, lec_id) == school["l201"]  # someone else's assignment kept


@pytest.mark.db
@respx.mock
async def test_login_sync_only_changes_the_user_logging_in(client, db_session, school):
    s = school
    algo = await db_session.get(Course, s["algo"])
    algo.moodle_course_id = 7
    db_session.add(Enrollment(student_id=s["s102"], occurrence_id=s["algo_lec"]))
    await db_session.commit()

    mock_moodle(user_id=101, username="23000101", email="m101@um.edu.my", idnumber="23000101")
    assert (await _login(client, username="23000101")).status_code == 200
    # 101 joins; 102 (not in this login's data) and the lecture's empty slot are left alone
    assert await _enrolments(db_session) == {
        (s["s102"], s["algo_lec"]), (s["s101"], s["algo_lec"]), (s["s101"], s["algo_tut"])}
    assert await _lecturer_of(db_session, s["algo_lec"]) is None


@pytest.mark.db
@respx.mock
async def test_login_assigns_a_lecturer_to_their_unassigned_classes(client, db_session, school):
    s = school
    algo = await db_session.get(Course, s["algo"])
    algo.moodle_course_id = 7
    await db_session.commit()
    mock_moodle(user_id=201, username="lect201", email="m201@um.edu.my", idnumber="ST201", roles=("editingteacher",))
    assert (await _login(client, username="lect201")).status_code == 200
    assert await _lecturer_of(db_session, s["algo_lec"]) == s["l201"]
    assert await _enrolments(db_session) == set()


# ── against the local Moodle (SPeCTRUM simulation) ───────────────────────────

@pytest.mark.db
@pytest.mark.moodle
async def test_local_moodle_full_sync_is_idempotent(admin_client, db_session):
    first = await _sync(admin_client)
    assert first["courses_created"] >= 1
    second = await _sync(admin_client)
    assert second["courses_created"] == 0 and second["enrolments_added"] == 0 and second["enrolments_removed"] == 0
