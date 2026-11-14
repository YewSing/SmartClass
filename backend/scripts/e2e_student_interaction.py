"""
Test data for the student interaction E2E flow (S25): an open interaction session
with a live poll, for a student to ask a question, vote, react and press IDU.

    python scripts/e2e_student_interaction.py setup    --student student4@example.com
    python scripts/e2e_student_interaction.py teardown

`setup` opens an interaction session on the student's enrolled occurrence, adds a poll
with two options, and records ids in a marker file. `teardown` removes the session,
poll, options, votes, reactions, IDU signals and questions the flow created.

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
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.interaction import InteractionSession
from app.models.interaction_live import InteractionIDUSignal, InteractionReaction
from app.models.interaction_poll import InteractionPoll, InteractionPollOption, InteractionPollVote
from app.models.interaction_question import InteractionQuestion
from app.models.user import Student

MARKER = os.path.join(tempfile.gettempdir(), "smartclass-e2e-student-interaction.json")


async def _student_id(db, email: str) -> int:
    student = await db.scalar(
        select(Student.id).join(Student.user).where(Student.user.email == email)
    )
    if student is None:
        sys.exit(f"No SmartClass student for {email}. Sign student4 in once, or run a Moodle sync.")
    return student


async def _lecturer_id(db, occurrence_id: int) -> int:
    occ = await db.get(ClassOccurrence, occurrence_id)
    if occ is None:
        sys.exit(f"No occurrence {occurrence_id} in SmartClass.")
    return occ.lecturer_id


async def setup(email: str) -> None:
    async with AsyncSessionLocal() as db:
        student_id = await _student_id(db, email)
        enrol = await db.scalar(
            select(Enrollment).where(Enrollment.student_id == student_id).limit(1)
        )
        if enrol is None:
            sys.exit(f"{email} is not enrolled in any occurrence.")
        occ_id = enrol.occurrence_id
        lecturer_id = await _lecturer_id(db, occ_id)

        open_id = await db.scalar(select(InteractionSession.id).where(
            InteractionSession.occurrence_id == occ_id, InteractionSession.status == "open"))
        if open_id is not None:
            sys.exit(f"Occurrence {occ_id} already has interaction session {open_id} open.")

        last = await db.scalar(select(func.max(InteractionSession.id))) or 0
        last_poll = await db.scalar(select(func.max(InteractionPoll.id))) or 0

        session = InteractionSession(
            occurrence_id=occ_id, status="open",
            opened_by=lecturer_id, opened_at=func.now(),
        )
        db.add(session)
        await db.flush()
        session_id = session.id

        poll = InteractionPoll(
            interaction_id=session_id, question="Ready for the quiz?",
            is_open=True, opened_by=lecturer_id, opened_at=func.now(),
        )
        db.add(poll)
        await db.flush()
        poll_id = poll.id
        for position, text in enumerate(["Yes", "No"]):
            db.add(InteractionPollOption(poll_id=poll_id, option_text=text, position=position))

        await db.commit()
    with open(MARKER, "w") as f:
        json.dump({
            "occurrence_id": occ_id,
            "session_id": session_id,
            "poll_id": poll_id,
            "after_session_id": last,
            "after_poll_id": last_poll,
            "student_email": email,
        }, f)
    print(f"Opened interaction session {session_id} on occurrence {occ_id} with poll {poll_id}")


async def teardown() -> None:
    if not os.path.exists(MARKER):
        print("no setup marker; nothing to remove")
        return
    with open(MARKER) as f:
        marker = json.load(f)
    async with AsyncSessionLocal() as db:
        session_id = marker["session_id"]
        await db.execute(delete(InteractionIDUSignal).where(
            InteractionIDUSignal.interaction_id == session_id))
        await db.execute(delete(InteractionReaction).where(
            InteractionReaction.interaction_id == session_id))
        await db.execute(delete(InteractionQuestion).where(
            InteractionQuestion.interaction_id == session_id))
        await db.execute(delete(InteractionPollVote).where(
            InteractionPollVote.poll_id == marker["poll_id"]))
        await db.execute(delete(InteractionPollOption).where(
            InteractionPollOption.poll_id == marker["poll_id"]))
        await db.execute(delete(InteractionPoll).where(InteractionPoll.id == marker["poll_id"]))
        await db.execute(delete(InteractionSession).where(
            InteractionSession.id == session_id,
            InteractionSession.id > marker["after_session_id"]))
        await db.commit()
    os.remove(MARKER)
    print(f"removed E2E interaction session {marker['session_id']} and poll {marker['poll_id']}")


async def _main(action: str, email: str) -> None:
    if action == "setup":
        await setup(email)
    else:
        await teardown()
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["setup", "teardown"])
    parser.add_argument("--student", default="student4@example.com", help="student email")
    args = parser.parse_args()
    asyncio.run(_main(args.action, args.student))
