"""
What Moodle can't provide. Moodle (SPeCTRUM) is the source of people, courses and enrolments;
a sync brings those in (POST /admin/moodle/sync, or a login). This adds only:

- the local administrator (FR-103: administrators don't sign in through Moodle)
- the timetable and cameras of the Moodle courses (Moodle has no timetable)
- devlecturer + WIA0000, a test class open all day, every day, so testing doesn't have to wait
  for real class times. Both also exist in Moodle: devlecturer signs in with Moodle on a phone,
  or with the local password below in a browser, which needs no Moodle running

Safe to run again: it only adds what's missing and never deletes anything.

Run from backend/:  python scripts/seed.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.camera import Camera
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.user import Lecturer, Student, User

ADMIN = {"email": "admin@um.edu.my", "password": "Admin@1234", "name": "Admin User"}
DEV_LECTURER = {"email": "devlecturer@um.edu.my", "password": "DevTest@1234", "name": "Dev Test Lecturer",
                "staff_id": "FS99999", "dept": "Testing"}

TEST_COURSE = ("WIA0000", "Dev Test Class")
TEST_ROOM = "TEST LAB"
ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# code -> name (a sync replaces it with Moodle's) and (type, label, day, start, end, room).
# Lecturers come from Moodle: the sync assigns each course's teacher.
TIMETABLE = {
    "WIF3001": ("Software Testing", [
        ("LECTURE", None, "Mon", "08:00", "10:00", "DK 2 FSKTM"),
        ("TUTORIAL", "Tutorial", "Wed", "10:00", "12:00", "MAKMAL MIKRO 1 FSKTM"),
    ]),
    "WIF3004": ("Software Architecture and Design Paradigm", [
        ("LECTURE", None, "Tue", "10:00", "12:00", "DK 5 FSKTM"),
        ("TUTORIAL", "Tutorial", "Thu", "14:00", "16:00", "MAKMAL LANJUTAN FSKTM"),
    ]),
    "WIA2005": ("Algorithm Design and Analysis", [
        ("LECTURE", None, "Wed", "14:00", "16:00", "BILIK KULIAH 1 FSKTM"),
        ("TUTORIAL", "Tutorial", "Fri", "08:00", "10:00", "BILIK KULIAH 2 FSKTM"),
    ]),
}


async def _ensure_user(db: AsyncSession, details: dict, role: str) -> User:
    user = (await db.execute(select(User).where(User.email == details["email"]))).scalar_one_or_none()
    if user is None:
        user = User(email=details["email"], password_hash=hash_password(details["password"]),
                    role=role, name=details["name"], status="active")
        db.add(user)
        await db.flush()
    return user


async def _ensure_course(db: AsyncSession, code: str, name: str) -> Course:
    course = (await db.execute(select(Course).where(Course.code == code))).scalar_one_or_none()
    if course is None:
        course = Course(code=code, name=name)
        db.add(course)
        await db.flush()
    return course


async def _ensure_camera(db: AsyncSession, room: str, device_id: str) -> None:
    await db.execute(insert(Camera).values(label=room, room=room, device_id=device_id)
                     .on_conflict_do_nothing())


async def seed(db: AsyncSession) -> None:
    await _ensure_user(db, ADMIN, "admin")

    # Timetable of the Moodle courses. A course that already has classes is left as it is.
    rooms: list[str] = []
    for code, (name, classes) in TIMETABLE.items():
        course = await _ensure_course(db, code, name)
        has_classes = (await db.execute(
            select(ClassOccurrence.id).where(ClassOccurrence.course_id == course.id).limit(1)
        )).first()
        for type_, label, day, start, end, room in classes:
            rooms.append(room)
            if not has_classes:
                db.add(ClassOccurrence(course_id=course.id, type=type_, label=label, day_of_week=day,
                                       start_time=start, end_time=end, room=room))
    for number, room in enumerate(rooms, start=1):
        await _ensure_camera(db, room, f"CAM-{number:03d}")
    await db.flush()

    # Browser test class: every day, 00:00-23:59
    user = await _ensure_user(db, DEV_LECTURER, "lecturer")
    lecturer = (await db.execute(select(Lecturer).where(Lecturer.user_id == user.id))).scalar_one_or_none()
    if lecturer is None:
        lecturer = Lecturer(user_id=user.id, staff_id=DEV_LECTURER["staff_id"], dept=DEV_LECTURER["dept"])
        db.add(lecturer)
        await db.flush()
    course = await _ensure_course(db, *TEST_COURSE)
    occurrences = (await db.execute(
        select(ClassOccurrence).where(ClassOccurrence.course_id == course.id)
    )).scalars().all()
    if not occurrences:
        occurrences = [ClassOccurrence(course_id=course.id, type="LECTURE", day_of_week=day, start_time="00:00",
                                       end_time="23:59", room=TEST_ROOM, lecturer_id=lecturer.id)
                       for day in ALL_DAYS]
        db.add_all(occurrences)
        await db.flush()
    await _ensure_camera(db, TEST_ROOM, "CAM-TEST")

    # Moodle students join through the sync. Local test accounts (face testing) have no other way in.
    students = (await db.execute(
        select(Student.id).join(User).where(User.moodle_user_id.is_(None))
    )).scalars().all()
    rows = [{"student_id": s, "occurrence_id": o.id} for s in students for o in occurrences]
    if rows:
        await db.execute(insert(Enrollment).values(rows).on_conflict_do_nothing())
    await db.flush()


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await seed(db)
        await db.commit()
    print("Seed complete. Now run a Moodle sync to bring in people and enrolments.")
    print(f"  Admin:    {ADMIN['email']} / {ADMIN['password']}")
    print(f"  DEV test: {DEV_LECTURER['email']} / {DEV_LECTURER['password']}  ({TEST_COURSE[0]}, always open)")
    print("  Everyone else signs in with their Moodle account: see backend/moodle/README.md")


if __name__ == "__main__":
    asyncio.run(main())
