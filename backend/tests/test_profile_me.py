"""T20: `GET /auth/me` returns the profile of FR-107 / UC-107 (name, matric/staff number, email,
faculty, courses) and, for students, the face enrolment status (FR-115)."""
import pytest
from sqlalchemy import select

from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.face import FaceEmbedding
from app.models.face_enrolment import FaceEnrolment
from app.models.user import Student

pytestmark = pytest.mark.db


async def _student_id(db_session, users) -> int:
    return (await db_session.execute(
        select(Student.id).where(Student.user_id == users["student"].id))).scalar_one()


async def test_student_profile_has_courses_and_face_status(student_client, classroom, users, db_session):
    # A tutorial of the same course must not list CS101 twice.
    tut = ClassOccurrence(course_id=classroom["course_id"], type="TUTORIAL", day_of_week="Wed",
                          start_time="14:00", end_time="15:00")
    db_session.add(tut)
    await db_session.flush()
    db_session.add(Enrollment(student_id=classroom["student_ids"][0], occurrence_id=tut.id))
    await db_session.commit()

    resp = await student_client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Test Student"
    assert body["email"] == users["student"].email
    assert body["role"] == "student"
    assert body["student"]["matric_no"] == "S0000001"
    assert "faculty" in body["student"]
    assert body["lecturer"] is None
    assert body["courses"] == [{"id": classroom["course_id"], "code": "CS101", "name": "Intro to Testing"}]
    assert body["face_status"] == "not_enrolled"


async def test_student_in_no_course_has_empty_courses(student_client, users):
    body = (await student_client.get("/auth/me")).json()
    assert body["courses"] == []
    assert body["face_status"] == "not_enrolled"


async def test_face_status_follows_enrolment(student_client, users, db_session):
    sid = await _student_id(db_session, users)
    db_session.add(FaceEnrolment(student_id=sid, status="pending_review", check_reasons=["face_mismatch"]))
    await db_session.commit()
    assert (await student_client.get("/auth/me")).json()["face_status"] == "pending_review"

    db_session.add(FaceEmbedding(student_id=sid, embedding=[0.1] * 512))
    await db_session.commit()
    assert (await student_client.get("/auth/me")).json()["face_status"] == "active"


async def test_lecturer_profile_lists_taught_courses_only(lecturer_client, classroom, db_session):
    # A second course taught by the same lecturer, with two classes (listed once).
    lec_id = classroom["lecturer_id"]
    course = Course(code="CS300", name="Advanced Testing")
    db_session.add(course)
    await db_session.flush()
    db_session.add_all([
        ClassOccurrence(course_id=course.id, type="LECTURE", day_of_week="Thu",
                        start_time="08:00", end_time="10:00", lecturer_id=lec_id),
        ClassOccurrence(course_id=course.id, type="TUTORIAL", day_of_week="Fri",
                        start_time="08:00", end_time="09:00", lecturer_id=lec_id),
    ])
    await db_session.commit()

    body = (await lecturer_client.get("/auth/me")).json()
    assert body["role"] == "lecturer"
    assert body["lecturer"]["staff_id"] == "STAFF-T001"
    assert body["lecturer"]["dept"] == "Software Engineering"
    assert body["student"] is None
    assert [c["code"] for c in body["courses"]] == ["CS101", "CS300"]  # not CS202 (another lecturer)
    assert body["face_status"] is None


async def test_admin_profile_has_no_courses_or_face_status(admin_client):
    body = (await admin_client.get("/auth/me")).json()
    assert body["role"] == "admin"
    assert body["courses"] == []
    assert body["face_status"] is None
