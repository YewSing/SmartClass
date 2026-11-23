"""
Test data for the student live class E2E flow (plan-shino.md S38, mobile/student/e2e/interaction.yaml).

    python scripts/e2e_student_interaction.py setup    [--student student4@example.com]
    python scripts/e2e_student_interaction.py actor    [--api http://127.0.0.1:8000]
    python scripts/e2e_student_interaction.py teardown

`setup` makes a local course E2E038 with one lecture, enrols the student and one classmate (any
other active student), and starts the class now through M3's own "Start now"
(`session_schedule.start_now`), so the student's Home shows it as live today.

`actor` plays the lecturer and the classmate through the real API while the flow runs:
  1. the classmate asks three named questions, the lecturer runs and closes an earlier poll and
     quick question (the page must not list them), then opens a quick question;
  2. once the student's question (ACTOR_QUESTION text) arrives, the lecturer marks it answered and
     starts a poll with results shown to students;
  3. once someone presses "I don't understand", the lecturer ends the class (M3's close), so the
     interaction closes (the S30 sweep sends `closed` within INTERACTION_SWEEP_SECONDS).
Access tokens are made in memory by the actor and never written to disk.

`teardown` removes the course, its class, enrolments, sessions (the M5 rows go with them by ON
DELETE CASCADE), attendance records and the notifications that link to its sessions. Audit-log rows
are kept (append-only). The course has no Moodle id and the E2E backend runs with the Moodle
Attendance sync off, so nothing reaches Moodle.

Run from backend/ against the dev database (DATABASE_URL in .env).
"""
import argparse
import asyncio
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.notification import Notification
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.services import session_schedule

COURSE_CODE = "E2E038"
COURSE_NAME = "E2E Live Class"
MARKER = os.path.join(tempfile.gettempdir(), "smartclass-e2e-student-interaction.json")

CLASSMATE_QUESTION = "E2E: Is a heap always a complete tree?"
# Two newer classmate questions, so after the student asks, the first one is only in "See all" (S38c)
CLASSMATE_MORE = ["E2E: Classmate question two", "E2E: Classmate question three"]
ACTOR_QUESTION = "E2E student question about heaps"      # what the flow types
# An earlier poll and quick question, closed before the flow looks: the page shows only the latest
EARLIER_QUICK_PROMPT = "E2E: Earlier quick question"
EARLIER_POLL_QUESTION = "E2E: Earlier poll"
QUICK_PROMPT = "E2E: One word for recursion?"
POLL_QUESTION = "E2E: Which sort is stable?"
POLL_OPTIONS = ["Merge sort", "Quick sort", "Heap sort"]
ACTOR_TIMEOUT_SECONDS = 15 * 60


async def _clean(db) -> list[int]:
    course = await db.scalar(select(Course).where(Course.code == COURSE_CODE))
    if course is None:
        return []
    occ_ids = (await db.execute(select(ClassOccurrence.id).where(ClassOccurrence.course_id == course.id))).scalars().all()
    ids: list[int] = []
    if occ_ids:
        ids = (await db.execute(select(AttendanceSession.id).where(
            AttendanceSession.occurrence_id.in_(occ_ids)))).scalars().all()
        if ids:
            await db.execute(delete(Notification).where(Notification.link.in_([f"/interaction/{i}" for i in ids])))
            await db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id.in_(ids)))
            await db.execute(delete(AttendanceSession).where(AttendanceSession.id.in_(ids)))
        await db.execute(delete(Enrollment).where(Enrollment.occurrence_id.in_(occ_ids)))
        await db.execute(delete(ClassOccurrence).where(ClassOccurrence.id.in_(occ_ids)))
    await db.execute(delete(Course).where(Course.id == course.id))
    await db.commit()
    return list(ids)


async def setup(email: str) -> None:
    async with AsyncSessionLocal() as db:
        await _clean(db)
        student = await db.scalar(select(Student).join(User, User.id == Student.user_id).where(User.email == email))
        if student is None:
            sys.exit(f"No SmartClass student with email {email}. Sign them in once first.")
        classmate = await db.scalar(
            select(Student).join(User, User.id == Student.user_id)
            .where(User.status == "active", User.role == "student", Student.id != student.id)
            .order_by(Student.id).limit(1))
        if classmate is None:
            sys.exit("Need one more active student as the classmate. Run a Moodle sync or scripts/seed.py.")
        lec = await db.scalar(
            select(Lecturer).join(User, User.id == Lecturer.user_id)
            .where(User.status == "active", User.role == "lecturer").order_by(Lecturer.id).limit(1))
        if lec is None:
            sys.exit("No active lecturer to run the class. Run scripts/seed.py first.")

        course = Course(code=COURSE_CODE, name=COURSE_NAME)
        db.add(course)
        await db.flush()
        occ = ClassOccurrence(course_id=course.id, type="LECTURE", room="E2E Room", lecturer_id=lec.id)
        db.add(occ)
        await db.flush()
        db.add_all([Enrollment(student_id=student.id, occurrence_id=occ.id),
                    Enrollment(student_id=classmate.id, occurrence_id=occ.id)])
        await db.flush()
        session = await session_schedule.start_now(db, occ, lec, session_schedule.clock(), duration_minutes=120)
        session_id = session.id
        await db.commit()
        marker = {"session_id": session_id, "lecturer_user_id": lec.user_id, "classmate_user_id": classmate.user_id}
    with open(MARKER, "w") as f:
        json.dump(marker, f)
    print(f"{COURSE_CODE} class session {session_id} started for {email}")


def _wait(what: str, check, deadline: float, every: float = 1.5):
    while time.monotonic() < deadline:
        got = check()
        if got:
            return got
        time.sleep(every)
    sys.exit(f"actor: timed out waiting for {what}")


def actor(api: str) -> None:
    with open(MARKER) as f:
        m = json.load(f)
    sid = m["session_id"]
    lecturer = {"Authorization": f"Bearer {create_access_token(m['lecturer_user_id'], 'lecturer')}"}
    classmate = {"Authorization": f"Bearer {create_access_token(m['classmate_user_id'], 'student')}"}
    deadline = time.monotonic() + ACTOR_TIMEOUT_SECONDS
    with httpx.Client(base_url=api, timeout=15) as c:
        for text in [CLASSMATE_QUESTION, *CLASSMATE_MORE]:
            c.post(f"/interaction/{sid}/questions", json={"text": text, "anonymous": False},
                   headers=classmate).raise_for_status()
        earlier_qq = c.post(f"/lecturer/interaction/{sid}/quick-questions",
                            json={"prompt": EARLIER_QUICK_PROMPT, "max_chars": 40}, headers=lecturer)
        earlier_qq.raise_for_status()
        c.post(f"/lecturer/interaction/{sid}/quick-questions/{earlier_qq.json()['id']}/close",
               headers=lecturer).raise_for_status()
        earlier_poll = c.post(f"/lecturer/interaction/{sid}/polls", json={
            "question": EARLIER_POLL_QUESTION, "options": ["Yes", "No"], "multiple": False, "show_results": True,
        }, headers=lecturer)
        earlier_poll.raise_for_status()
        epid = earlier_poll.json()["id"]
        c.post(f"/lecturer/interaction/{sid}/polls/{epid}/start", headers=lecturer).raise_for_status()
        c.post(f"/lecturer/interaction/{sid}/polls/{epid}/close", headers=lecturer).raise_for_status()
        c.post(f"/lecturer/interaction/{sid}/quick-questions", json={"prompt": QUICK_PROMPT, "max_chars": 40},
               headers=lecturer).raise_for_status()
        print("actor: classmate asked 3; earlier poll/quick closed; quick question open", flush=True)

        def student_question():
            qs = c.get(f"/interaction/{sid}/questions", headers=lecturer).json()["questions"]
            return next((q for q in qs if q["text"] == ACTOR_QUESTION), None)
        q = _wait("the student's question", student_question, deadline)
        c.patch(f"/lecturer/interaction/{sid}/questions/{q['id']}", json={"answered": True},
                headers=lecturer).raise_for_status()
        poll = c.post(f"/lecturer/interaction/{sid}/polls", json={
            "question": POLL_QUESTION, "options": POLL_OPTIONS, "multiple": False, "show_results": True,
        }, headers=lecturer)
        poll.raise_for_status()
        c.post(f"/lecturer/interaction/{sid}/polls/{poll.json()['id']}/start", headers=lecturer).raise_for_status()
        print(f"actor: answered question {q['id']} (anonymous={q['anonymous']}); poll started", flush=True)

        _wait("an \"I don't understand\" press",
              lambda: c.get(f"/lecturer/interaction/{sid}/confusion", headers=lecturer).json()["total"] >= 1,
              deadline)
        c.put(f"/lecturer/sessions/{sid}/close", headers=lecturer).raise_for_status()
        print("actor: class ended", flush=True)


async def teardown() -> None:
    async with AsyncSessionLocal() as db:
        ids = await _clean(db)
    if os.path.exists(MARKER):
        os.remove(MARKER)
    print(f"removed {COURSE_CODE} and its sessions {ids}")


async def _run(coro) -> None:
    try:
        await coro
    finally:
        await engine.dispose()  # before the loop closes, or Windows prints "Event loop is closed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("action", choices=["setup", "actor", "teardown"])
    parser.add_argument("--student", default="student4@example.com", help="the student's SmartClass email")
    parser.add_argument("--api", default=os.environ.get("E2E_API_URL", "http://127.0.0.1:8000"))
    args = parser.parse_args()
    if args.action == "setup":
        asyncio.run(_run(setup(args.student)))
    elif args.action == "actor":
        actor(args.api)
    else:
        asyncio.run(_run(teardown()))
