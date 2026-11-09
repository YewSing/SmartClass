"""The seed holds only what Moodle can't provide, and running it again changes nothing."""
import pytest
from sqlalchemy import func, select

from app.core.security import verify_password
from app.models.camera import Camera
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.face import FaceEmbedding
from app.models.knowledge import KbMaterial
from app.models.user import Lecturer, Student, User
from scripts.reset_to_moodle import reset
from scripts.seed import ADMIN, DEV_LECTURER, TEST_COURSE, TIMETABLE, seed

pytestmark = pytest.mark.db


async def _count(db, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def _occurrences(db, code):
    return (await db.execute(
        select(ClassOccurrence).join(Course).where(Course.code == code)
    )).scalars().all()


async def test_only_local_accounts_are_created(db_session):
    await seed(db_session)
    await db_session.commit()
    users = (await db_session.execute(select(User))).scalars().all()
    assert {(u.email, u.role) for u in users} == {(ADMIN["email"], "admin"), (DEV_LECTURER["email"], "lecturer")}
    assert await _count(db_session, Student) == 0   # students come from Moodle
    for details in (ADMIN, DEV_LECTURER):
        user = next(u for u in users if u.email == details["email"])
        assert verify_password(details["password"], user.password_hash)


async def test_moodle_courses_get_a_timetable_with_no_lecturer(db_session):
    await seed(db_session)
    await db_session.commit()
    for code, (_, classes) in TIMETABLE.items():
        occurrences = await _occurrences(db_session, code)
        assert len(occurrences) == len(classes)
        assert all(o.lecturer_id is None for o in occurrences), "the Moodle sync assigns the lecturer"


async def test_test_class_is_open_all_day_every_day_for_devlecturer(db_session):
    await seed(db_session)
    await db_session.commit()
    lecturer = (await db_session.execute(
        select(Lecturer).join(User).where(User.email == DEV_LECTURER["email"])
    )).scalar_one()
    occurrences = await _occurrences(db_session, TEST_COURSE[0])
    assert {o.day_of_week for o in occurrences} == {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
    for o in occurrences:
        assert (o.start_time, o.end_time, o.lecturer_id) == ("00:00", "23:59", lecturer.id)


async def test_every_timetable_room_has_a_camera(db_session):
    await seed(db_session)
    await db_session.commit()
    rooms = set((await db_session.execute(select(ClassOccurrence.room))).scalars())
    cameras = set((await db_session.execute(select(Camera.room))).scalars())
    assert rooms <= cameras


async def test_running_it_again_changes_nothing_and_keeps_later_data(db_session):
    await seed(db_session)
    await db_session.commit()

    # What a sync and an administrator do between two seed runs must survive
    moodle_user = User(email="s1@example.com", role="student", name="S One", moodle_user_id=6)
    local_user = User(email="face@example.com", role="student", name="Face Test")
    db_session.add_all([moodle_user, local_user])
    await db_session.flush()
    moodle_student = Student(user_id=moodle_user.id, matric_no="student1")
    student = Student(user_id=local_user.id, matric_no="23004444")
    db_session.add_all([moodle_student, student])
    wia2005 = (await db_session.execute(select(Course).where(Course.code == "WIA2005"))).scalar_one()
    wia2005.name = "Name from Moodle"
    await db_session.flush()
    student_id, moodle_student_id, course_id = student.id, moodle_student.id, wia2005.id
    await db_session.commit()

    await seed(db_session)
    await db_session.commit()
    first_counts = [await _count(db_session, m) for m in (User, Course, ClassOccurrence, Camera, Enrollment)]
    db_session.expire_all()
    assert (await db_session.get(Course, course_id)).name == "Name from Moodle"
    assert len(await _occurrences(db_session, "WIA2005")) == len(TIMETABLE["WIA2005"][1])

    # The local test account joined the test class once per day; Moodle's students are the sync's job
    enrolled = (await db_session.execute(
        select(Enrollment.student_id, func.count()).group_by(Enrollment.student_id)
    )).all()
    assert dict(enrolled) == {student_id: 7}
    assert moodle_student_id not in dict(enrolled)

    await seed(db_session)
    await db_session.commit()
    assert [await _count(db_session, m) for m in (User, Course, ClassOccurrence, Camera, Enrollment)] == first_counts


async def test_reset_removes_demo_data_but_keeps_faces_ai_materials_and_moodle_accounts(db_session):
    db = db_session
    await seed(db)
    demo = User(email="demo@um.edu.my", role="student", name="Demo", password_hash="x")
    demo_lecturer = User(email="demolec@um.edu.my", role="lecturer", name="Demo Lecturer", password_hash="x")
    face = User(email="face@example.com", role="student", name="Face Test", password_hash="x")
    linked = User(email="s1@example.com", role="student", name="S One", moodle_user_id=6)
    db.add_all([demo, demo_lecturer, face, linked])
    await db.flush()
    demo_student = Student(user_id=demo.id, matric_no="1")
    face_student = Student(user_id=face.id, matric_no="2")
    linked_student = Student(user_id=linked.id, matric_no="3")
    lecturer = Lecturer(user_id=demo_lecturer.id, staff_id="L1")
    old_course = Course(code="WIA1002", name="Old demo")
    db.add_all([demo_student, face_student, linked_student, lecturer, old_course])
    await db.flush()
    db.add(FaceEmbedding(student_id=face_student.id, embedding=[0.0] * 512))
    wif = (await db.execute(select(Course).where(Course.code == "WIF3001"))).scalar_one()
    wif_id, old_id, face_student_id = wif.id, old_course.id, face_student.id
    db.add(KbMaterial(course_id=wif_id, source_key="m1", file_name="notes.pdf", title="Notes"))
    old_occ = ClassOccurrence(course_id=old_id, type="LECTURE", day_of_week="Mon", start_time="08:00",
                              end_time="10:00", lecturer_id=lecturer.id)
    db.add(old_occ)
    await db.flush()
    db.add(Enrollment(student_id=demo_student.id, occurrence_id=old_occ.id))
    await db.commit()

    await reset(db)
    await db.commit()
    db.expire_all()

    emails = set((await db.execute(select(User.email))).scalars())
    assert emails == {ADMIN["email"], DEV_LECTURER["email"], "face@example.com", "s1@example.com"}
    assert set((await db.execute(select(Course.code))).scalars()) == {*TIMETABLE, TEST_COURSE[0]}
    assert await _count(db, FaceEmbedding) == 1
    assert await _count(db, KbMaterial) == 1
    assert (await db.execute(select(KbMaterial.course_id))).scalar_one() == wif_id  # same course row
    # The timetable is back, and the local face account is in the always-open class
    assert len(await _occurrences(db, "WIF3001")) == len(TIMETABLE["WIF3001"][1])
    enrolled = (await db.execute(
        select(func.count()).select_from(Enrollment).where(Enrollment.student_id == face_student_id)
    )).scalar_one()
    assert enrolled == 7
