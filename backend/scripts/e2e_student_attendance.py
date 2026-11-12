"""
Test data for the student attendance E2E flow (T39): a local course E2E039 with four closed
sessions, one per status, for one student.

    python scripts/e2e_student_attendance.py seed  --student student4@example.com
    python scripts/e2e_student_attendance.py clean

`seed` gives the student a course they are enrolled in with four finished classes: present,
late, excused and absent (newest first), so the app shows a 66.7% rate and all four counts.
`clean` removes everything it created (records, sessions, enrolments, the class and the course).
The course has no Moodle id and its sessions are never queued for the Moodle sync, so neither
sync touches it. The student must exist in SmartClass already (a Moodle sync or login creates them).

Run from backend/ against the dev database (DATABASE_URL in .env).
"""
import argparse
import asyncio
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User

COURSE_CODE = "E2E039"
COURSE_NAME = "E2E Attendance Test"
STATUSES = ["present", "late", "excused", "absent"]
DATES = [date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19), date(2026, 10, 26)]


async def clean(db: AsyncSession) -> None:
    course = (await db.execute(select(Course).where(Course.code == COURSE_CODE))).scalar_one_or_none()
    if course is None:
        return
    occ_ids = (await db.execute(
        select(ClassOccurrence.id).where(ClassOccurrence.course_id == course.id)
    )).scalars().all()
    if occ_ids:
        session_ids = (await db.execute(
            select(AttendanceSession.id).where(AttendanceSession.occurrence_id.in_(occ_ids))
        )).scalars().all()
        if session_ids:
            await db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id.in_(session_ids)))
            await db.execute(delete(AttendanceSession).where(AttendanceSession.id.in_(session_ids)))
        await db.execute(delete(Enrollment).where(Enrollment.occurrence_id.in_(occ_ids)))
        await db.execute(delete(ClassOccurrence).where(ClassOccurrence.id.in_(occ_ids)))
    await db.execute(delete(Course).where(Course.id == course.id))
    await db.commit()


async def seed(db: AsyncSession, student_id: int, lecturer_id: int) -> int:
    """The E2E039 course with one closed session per status; returns the course id."""
    await clean(db)
    course = Course(code=COURSE_CODE, name=COURSE_NAME)
    db.add(course)
    await db.flush()
    occurrence = ClassOccurrence(
        course_id=course.id, type="LECTURE", day_of_week="Mon", start_time="08:00",
        end_time="10:00", room="E2E Room", lecturer_id=lecturer_id,
    )
    db.add(occurrence)
    await db.flush()
    db.add(Enrollment(student_id=student_id, occurrence_id=occurrence.id))
    for status, d in zip(STATUSES, DATES):
        session = AttendanceSession(
            occurrence_id=occurrence.id,
            lecturer_id=lecturer_id,
            status="closed",
            source="manual",
            class_date=d,
            opened_at=datetime(d.year, d.month, d.day, 8, 0),
            starts_at=datetime(d.year, d.month, d.day, 8, 0),
            ends_at=datetime(d.year, d.month, d.day, 10, 0),
            closed_at=datetime(d.year, d.month, d.day, 10, 0),
        )
        db.add(session)
        await db.flush()
        detected_at = None
        if status == "present":
            detected_at = datetime(d.year, d.month, d.day, 8, 5)
        elif status == "late":
            detected_at = datetime(d.year, d.month, d.day, 8, 25)
        db.add(AttendanceRecord(session_id=session.id, student_id=student_id,
                                status=status, detected_at=detected_at))
    await db.commit()
    return course.id


async def _main(action: str, email: str) -> None:
    async with AsyncSessionLocal() as db:
        if action == "clean":
            await clean(db)
            print(f"{COURSE_CODE} attendance test data removed")
        else:
            student = (await db.execute(
                select(Student).join(User, User.id == Student.user_id).where(User.email == email)
            )).scalar_one_or_none()
            if student is None:
                sys.exit(f"No SmartClass student with email {email}. Sync Moodle or sign them in once first.")
            lecturer_id = await db.scalar(select(Lecturer.id).order_by(Lecturer.id).limit(1))
            if lecturer_id is None:
                sys.exit("No lecturer in SmartClass to own the E2E course. Run scripts/seed.py first.")
            course_id = await seed(db, student.id, lecturer_id)
            print(f"{COURSE_CODE} course {course_id} seeded for {email}")
    await engine.dispose()  # before the loop closes, or Windows prints "Event loop is closed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["seed", "clean"])
    parser.add_argument("--student", default="student4@example.com", help="the student's SmartClass email")
    args = parser.parse_args()
    asyncio.run(_main(args.action, args.student))
