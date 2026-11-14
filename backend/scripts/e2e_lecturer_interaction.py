"""
Test data for the lecturer interaction E2E flow (S26): an open interaction session
with a live poll, on a class lecturer1 teaches.

    python scripts/e2e_lecturer_interaction.py setup    --course WIF3001
    python scripts/e2e_lecturer_interaction.py teardown --course WIF3001

`setup` finds lecturer1's lecture occurrence for the course, opens an interaction
session on it, adds a poll with two options, and records ids in a marker file.
`teardown` removes the session, poll, options, votes, reactions, IDU signals and
questions the flow created.

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
from app.models.class_ import ClassOccurrence, Course
from app.models.interaction import InteractionSession
from app.models.interaction_live import InteractionIDUSignal, InteractionReaction
from app.models.interaction_poll import InteractionPoll, InteractionPollOption, InteractionPollVote
from app.models.interaction_question import InteractionQuestion
from app.models.user import Lecturer, User

MARKER = os.path.join(tempfile.gettempdir(), "smartclass-e2e-lecturer-interaction.json")


async def _lecturer_id(db, email: str) -> int:
    lecturer = await db.scalar(
        select(Lecturer.id).join(User, User.id == Lecturer.user_id).where(User.email == email)
    )
    if lecturer is None:
        sys.exit(f"No SmartClass lecturer for {email}. Sign lecturer1 in once, or run a Moodle sync.")
    return lecturer


async def _lecture_occurrence(db, lecturer_id: int, code: str) -> int:
    occ = await db.scalar(
        select(ClassOccurrence.id)
        .join(Course, Course.id == ClassOccurrence.course_id)
        .where(
            ClassOccurrence.lecturer_id == lecturer_id,
            ClassOccurrence.type == "LECTURE",
            Course.code == code,
        )
    )
    if occ is None:
        sys.exit(f"No lecture occurrence for course {code} taught by lecturer {lecturer_id}.")
    return occ


async def setup(email: str, code: str) -> None:
    async with AsyncSessionLocal() as db:
        lecturer_id = await _lecturer_id(db, email)
        occ_id = await _lecture_occurrence(db, lecturer_id, code)

        open_id = await db.scalar(select(InteractionSession.id).where(
            InteractionSession.occurrence_id == occ_id, InteractionSession.status == "open"))
        if open_id is not None:
            sys.exit(f"Occurrence {occ_id} already has interaction session {open_id} open.")

        last_session = await db.scalar(select(func.max(InteractionSession.id))) or 0
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
            "after_session_id": last_session,
            "after_poll_id": last_poll,
            "lecturer_email": email,
            "course_code": code,
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


async def _main(action: str, email: str, code: str) -> None:
    if action == "setup":
        await setup(email, code)
    else:
        await teardown()
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["setup", "teardown"])
    parser.add_argument("--lecturer", default="lecturer1@example.com", help="lecturer email")
    parser.add_argument("--course", default="WIF3001", help="course code whose lecture the flow uses")
    args = parser.parse_args()
    asyncio.run(_main(args.action, args.lecturer, args.course))
