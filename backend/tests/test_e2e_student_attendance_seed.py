"""T39: the student attendance E2E seed gives the flow a real 66.7% course to check."""
import pytest
from sqlalchemy import func, select

from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.session import AttendanceSession
from app.models.user import Lecturer
from scripts.e2e_student_attendance import COURSE_CODE, clean, seed

pytestmark = pytest.mark.db

URL = "/student/me/attendance/courses"
DATES = ["2026-10-26", "2026-10-19", "2026-10-12", "2026-10-05"]


async def _count(db, model, *where):
    db.expire_all()
    return await db.scalar(select(func.count()).select_from(model).where(*where))


async def _course_from_api(client) -> dict | None:
    body = (await client.get(URL)).json()
    return next((c for c in body if c["course_code"] == COURSE_CODE), None)


async def test_seeded_course_gives_the_rate_the_flow_checks(student_client, classroom, users, db_session):
    student_id = classroom["student_ids"][0]
    lecturer_id = await db_session.scalar(
        select(Lecturer.id).where(Lecturer.user_id == users["lecturer"].id)
    )
    await seed(db_session, student_id, lecturer_id)

    course = await _course_from_api(student_client)
    assert course is not None
    assert course["rate"] == 66.7
    assert (course["present"], course["late"], course["excused"], course["absent"]) == (1, 1, 1, 1)
    assert course["closed_sessions"] == 4
    assert course["counted_sessions"] == 3

    sessions = course["sessions"]
    assert [s["status"] for s in sessions] == ["absent", "excused", "late", "present"]
    assert [s["date"] for s in sessions] == DATES
    assert next(s for s in sessions if s["status"] == "excused")["date"] == "2026-10-19"
    assert all(s["session_status"] == "closed" for s in sessions)


async def test_seeding_again_keeps_one_course_and_clean_removes_everything(
    student_client, classroom, users, db_session
):
    student_id = classroom["student_ids"][0]
    lecturer_id = await db_session.scalar(
        select(Lecturer.id).where(Lecturer.user_id == users["lecturer"].id)
    )
    await seed(db_session, student_id, lecturer_id)
    await seed(db_session, student_id, lecturer_id)

    assert await _count(db_session, Course, Course.code == COURSE_CODE) == 1
    course_id = await db_session.scalar(select(Course.id).where(Course.code == COURSE_CODE))
    occ_id = await db_session.scalar(
        select(ClassOccurrence.id).where(ClassOccurrence.course_id == course_id)
    )
    session_ids = (await db_session.execute(
        select(AttendanceSession.id).where(AttendanceSession.occurrence_id == occ_id)
    )).scalars().all()
    assert len(session_ids) == 4

    await clean(db_session)

    assert await _count(db_session, Course, Course.id == course_id) == 0
    assert await _count(db_session, ClassOccurrence, ClassOccurrence.id == occ_id) == 0
    assert await _count(db_session, Enrollment, Enrollment.occurrence_id == occ_id) == 0
    assert await _count(db_session, AttendanceSession, AttendanceSession.id.in_(session_ids)) == 0
    assert await _count(
        db_session, AttendanceRecord, AttendanceRecord.session_id.in_(session_ids)
    ) == 0
    assert await _course_from_api(student_client) is None

    await clean(db_session)  # an empty database is fine


async def test_seeded_sessions_are_never_queued_for_moodle(classroom, users, db_session):
    student_id = classroom["student_ids"][0]
    lecturer_id = await db_session.scalar(
        select(Lecturer.id).where(Lecturer.user_id == users["lecturer"].id)
    )
    await seed(db_session, student_id, lecturer_id)

    db_session.expire_all()
    occ_id = await db_session.scalar(
        select(ClassOccurrence.id)
        .join(Course, Course.id == ClassOccurrence.course_id)
        .where(Course.code == COURSE_CODE)
    )
    statuses = (await db_session.execute(
        select(AttendanceSession.moodle_sync_status).where(AttendanceSession.occurrence_id == occ_id)
    )).scalars().all()
    assert len(statuses) == 4
    assert all(status is None for status in statuses)
