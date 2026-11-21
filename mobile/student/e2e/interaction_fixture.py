"""Local Maestro fixture, scoped to a dedicated course with an exact ownership marker."""
import asyncio
import os
import sys
from datetime import timedelta

import app.models  # noqa: F401
import httpx
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.core.timezone import now_myt
from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.interaction import InteractionEvent
from app.models.notification import Notification
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from sqlalchemy import delete, select

CODE = "E2E050S"
NAME = "Maestro student interaction fixture"


async def clean(db):
    course = await db.scalar(select(Course).where(Course.code == CODE))
    if course is None:
        return
    if course.name != NAME or course.moodle_course_id is not None:
        raise RuntimeError("The fixture course code is already in use")
    occurrences = select(ClassOccurrence.id).where(ClassOccurrence.course_id == course.id)
    sessions = list((await db.scalars(select(AttendanceSession.id).where(
        AttendanceSession.occurrence_id.in_(occurrences)
    ))).all())
    await db.execute(delete(Notification).where(Notification.link.in_(
        [f"/interaction/sessions/{session_id}" for session_id in sessions]
    )))
    await db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id.in_(sessions)))
    await db.execute(delete(AttendanceSession).where(AttendanceSession.id.in_(sessions)))
    await db.execute(delete(Enrollment).where(Enrollment.occurrence_id.in_(occurrences)))
    await db.execute(delete(ClassOccurrence).where(ClassOccurrence.course_id == course.id))
    await db.execute(delete(Course).where(Course.id == course.id))


async def seed(db, client):
    await clean(db)
    student = await db.scalar(select(Student).join(User).where(User.email == "student4@example.com"))
    lecturer = await db.scalar(select(Lecturer).join(User).where(User.email == "lecturer1@example.com"))
    if student is None or lecturer is None:
        raise RuntimeError("Sign in student4 and lecturer1 on the local Moodle before running this fixture")
    course = Course(code=CODE, name=NAME)
    db.add(course)
    await db.flush()
    occurrence = ClassOccurrence(course_id=course.id, lecturer_id=lecturer.id, type="LECTURE")
    db.add(occurrence)
    await db.flush()
    now = now_myt()
    session = AttendanceSession(
        occurrence_id=occurrence.id, lecturer_id=lecturer.id, status="open",
        class_date=now.date(), opened_at=now, starts_at=now, ends_at=now + timedelta(hours=1),
    )
    db.add_all((Enrollment(occurrence_id=occurrence.id, student_id=student.id), session))
    await db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(lecturer.user_id, 'lecturer')}"}
    base = f"/interaction/sessions/{session.id}"
    poll = (await client.post(f"{base}/polls", headers=headers, json={
        "prompt": "Which example helped?", "options": ["Queues", "Stacks"],
    })).raise_for_status().json()
    (await client.post(f"{base}/polls/{poll['id']}/start", headers=headers)).raise_for_status()
    (await client.post(f"{base}/quick-prompts", headers=headers, json={
        "prompt": "Name a use for a queue.",
    })).raise_for_status()


async def close_after_signal(client):
    for _ in range(240):
        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(AttendanceSession.id, Lecturer.user_id)
                .join(ClassOccurrence, ClassOccurrence.id == AttendanceSession.occurrence_id)
                .join(Course, Course.id == ClassOccurrence.course_id)
                .join(Lecturer, Lecturer.id == ClassOccurrence.lecturer_id)
                .where(Course.code == CODE, Course.name == NAME)
            )).one_or_none()
            if row is None:
                return
            session_id, user_id = row
            signal = await db.scalar(select(InteractionEvent.id).where(
                InteractionEvent.attendance_session_id == session_id,
                InteractionEvent.kind == "confusion.reported",
            ).limit(1))
        if signal:
            await asyncio.sleep(2)
            headers = {"Authorization": f"Bearer {create_access_token(user_id, 'lecturer')}"}
            (await client.put(f"/lecturer/sessions/{session_id}/close", headers=headers)).raise_for_status()
            return
        await asyncio.sleep(1)


async def main(action):
    async with httpx.AsyncClient(base_url=os.environ.get("E2E_API_URL", "http://127.0.0.1:8000")) as client:
        if action == "close-after-signal":
            await close_after_signal(client)
            return
        async with AsyncSessionLocal() as db:
            if action == "seed":
                await seed(db, client)
            elif action == "clean":
                await clean(db)
                await db.commit()
            else:
                raise ValueError("Expected seed, clean, or close-after-signal")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
