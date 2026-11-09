"""
One-off: move an existing database from the old demo seed to Moodle as the source of truth.

Removes the demo accounts and courses, classes, attendance, chats, audit log and cameras.
Keeps administrators, devlecturer, Moodle-linked accounts, accounts with a face enrolment and
those faces, and the courses that have AI materials, with the materials. Then re-creates the
timetable (scripts/seed.py) and brings in Moodle's people and enrolments (a full sync).

Back up first: bash scripts/backup-data.sh

Run from backend/:
    python scripts/reset_to_moodle.py          # shows what would be removed, changes nothing
    python scripts/reset_to_moodle.py --yes    # does it
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.ai_chat import ChatMessage, ChatSession
from app.models.attendance import AttendanceRecord
from app.models.audit import AuditLog
from app.models.camera import Camera
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.face import FaceEmbedding
from app.models.face_review import FaceReviewEntry
from app.models.knowledge import KbMaterial
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.services import moodle_sync
from scripts.seed import DEV_LECTURER, TEST_COURSE, TIMETABLE, seed


async def plan(db: AsyncSession) -> tuple[set[int], set[int]]:
    """Ids of the users and courses that stay."""
    face_owners = select(Student.user_id).join(FaceEmbedding, FaceEmbedding.student_id == Student.id)
    users = set((await db.execute(select(User.id).where(or_(
        User.role == "admin",
        User.email == DEV_LECTURER["email"],
        User.moodle_user_id.is_not(None),
        User.id.in_(face_owners),
    )))).scalars())
    courses = set((await db.execute(select(Course.id).where(or_(
        Course.code.in_([*TIMETABLE, TEST_COURSE[0]]),
        Course.moodle_course_id.is_not(None),
        Course.id.in_(select(KbMaterial.course_id)),
    )))).scalars())
    return users, courses


async def reset(db: AsyncSession) -> None:
    """Everything or nothing: the caller commits. Doesn't touch Moodle, so call the sync after."""
    keep_users, keep_courses = await plan(db)
    for model in (AuditLog, FaceReviewEntry, AttendanceRecord, AttendanceSession, Enrollment,
                  ChatMessage, ChatSession, ClassOccurrence, Camera):
        await db.execute(delete(model))
    await db.execute(delete(Course).where(Course.id.not_in(keep_courses)))
    await db.execute(delete(Lecturer).where(Lecturer.user_id.not_in(keep_users)))
    await db.execute(delete(Student).where(Student.user_id.not_in(keep_users)))
    await db.execute(delete(User).where(User.id.not_in(keep_users)))
    await db.flush()
    db.expire_all()
    await seed(db)


async def _count(db: AsyncSession, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def main() -> None:
    async with AsyncSessionLocal() as db:
        keep_users, keep_courses = await plan(db)
        print(f"Users:   {await _count(db, User)} now, {len(keep_users)} stay")
        print(f"Courses: {await _count(db, Course)} now, {len(keep_courses)} stay")
        print(f"Removed: {await _count(db, AttendanceSession)} sessions, {await _count(db, AttendanceRecord)} attendance "
              f"records, {await _count(db, ChatSession)} chats, {await _count(db, AuditLog)} audit entries")
        print(f"Kept:    {await _count(db, FaceEmbedding)} face enrolments, {await _count(db, KbMaterial)} AI materials")
        if "--yes" not in sys.argv:
            print("Nothing changed. Back up first, then run again with --yes.")
            return
        await reset(db)
        await db.commit()
        report = await moodle_sync.sync_all(db)
        await db.commit()
        print(f"Done. Moodle sync: {report}")


if __name__ == "__main__":
    asyncio.run(main())
