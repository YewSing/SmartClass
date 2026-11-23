"""
Test data for the lecturer live interaction E2E flow (plan-shino.md S37).

    python scripts/e2e_interaction.py setup    --course WIA0000 --day Wed [--students 3]
    python scripts/e2e_interaction.py teardown

`setup` starts the course's lecture on that weekday now, through M3's own "Start now"
(`session_schedule.start_now`, as the S03 test helper does), and prints one JSON line:
`{"session_id", "students": [{"name", "token"}]}` with short-lived access tokens of active enrolled
students, so the flow can ask, vote, answer, react and press "I don't understand" through the real
API. Tokens (normal access-token lifetime) are printed only to the caller and never written to disk.

`teardown` deletes the sessions the flow made (their attendance records; the M5 rows go with them
by ON DELETE CASCADE) and the notifications that link to them (`poll.started`, `confusion.spike`).
The E2E backend runs with the Moodle Attendance sync off, so nothing reaches Moodle. Audit-log rows
(session start/close, interaction pause/resume) are kept: the audit log is append-only.

Run from backend/ against the dev database (DATABASE_URL in .env).
"""
import argparse
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.notification import Notification
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.services import session_schedule

MARKER = os.path.join(tempfile.gettempdir(), "smartclass-e2e-interaction.json")


async def setup(code: str, day: str, n_students: int) -> None:
    async with AsyncSessionLocal() as db:
        occ = await db.scalar(
            select(ClassOccurrence).join(Course, Course.id == ClassOccurrence.course_id)
            .where(Course.code == code, ClassOccurrence.type == "LECTURE", ClassOccurrence.day_of_week == day)
            .order_by(ClassOccurrence.id).limit(1))
        if occ is None:
            sys.exit(f"No {code} lecture on {day}. Run scripts/seed.py first.")
        lec = await db.get(Lecturer, occ.lecturer_id) if occ.lecturer_id else None
        if lec is None:
            sys.exit(f"The {code} {day} lecture has no lecturer.")
        if await db.scalar(select(AttendanceSession.id).where(
                AttendanceSession.occurrence_id == occ.id, AttendanceSession.status == "open")) is not None:
            sys.exit(f"The {code} {day} lecture already has an open session; end it in the app and retry.")
        rows = (await db.execute(
            select(User.id, User.role, User.name).join(Student, Student.user_id == User.id)
            .join(Enrollment, Enrollment.student_id == Student.id)
            .where(Enrollment.occurrence_id == occ.id, User.status == "active")
            .order_by(Student.id).limit(n_students))).all()
        if len(rows) < 2:
            sys.exit(f"The {code} {day} lecture needs at least 2 active enrolled students (has {len(rows)}).")
        after_id = await db.scalar(select(func.max(AttendanceSession.id))) or 0
        session = await session_schedule.start_now(db, occ, lec, session_schedule.clock(), duration_minutes=120)
        session_id = session.id
        await db.commit()
    with open(MARKER, "w") as f:
        json.dump({"occurrence_id": occ.id, "after_id": after_id}, f)
    students = [{"name": name, "token": create_access_token(uid, role)} for uid, role, name in rows]
    print(json.dumps({"session_id": session_id, "students": students}))


async def teardown() -> None:
    if not os.path.exists(MARKER):
        print("no setup marker; nothing to remove")
        return
    with open(MARKER) as f:
        marker = json.load(f)
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(select(AttendanceSession.id).where(
            AttendanceSession.occurrence_id == marker["occurrence_id"],
            AttendanceSession.id > marker["after_id"],
        ))).scalars().all()
        if ids:
            await db.execute(delete(Notification).where(
                Notification.link.in_([f"/interaction/{i}" for i in ids])))
            await db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id.in_(ids)))
            await db.execute(delete(AttendanceSession).where(AttendanceSession.id.in_(ids)))
            await db.commit()
    os.remove(MARKER)
    print(f"removed E2E sessions {ids} and their interaction data")


async def _main(args) -> None:
    try:
        if args.action == "setup":
            await setup(args.course, args.day, args.students)
        else:
            await teardown()
    finally:
        await engine.dispose()  # before the loop closes, or Windows prints "Event loop is closed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("action", choices=["setup", "teardown"])
    parser.add_argument("--course", default="WIA0000")
    parser.add_argument("--day", default="Wed", help="the lecture on this weekday (Mon..Sun)")
    parser.add_argument("--students", type=int, default=3)
    asyncio.run(_main(parser.parse_args()))
