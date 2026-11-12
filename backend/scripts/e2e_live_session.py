"""
Test data for the lecturer live session E2E flow (T38): a class with no session running.

    python scripts/e2e_live_session.py setup    --course WIF3001
    python scripts/e2e_live_session.py teardown --course WIF3001

`setup` checks the course's lecture has no open session (the flow starts one with "Start now") and
remembers the newest session id. `teardown` deletes the sessions the flow made after that, with
their attendance records, so the course's reports and rates are as before. The E2E backend runs
with the Moodle Attendance sync off, so nothing reaches Moodle.

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
from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Course
from app.models.session import AttendanceSession

MARKER = os.path.join(tempfile.gettempdir(), "smartclass-e2e-live-session.json")


async def _lecture_id(db, code: str, day: str | None) -> int:
    q = (select(ClassOccurrence.id).join(Course, Course.id == ClassOccurrence.course_id)
         .where(Course.code == code, ClassOccurrence.type == "LECTURE"))
    if day:   # WIA0000 has one lecture per weekday
        q = q.where(ClassOccurrence.day_of_week == day)
    occ_id = await db.scalar(q.order_by(ClassOccurrence.id).limit(1))
    if occ_id is None:
        sys.exit(f"No {code} lecture{f' on {day}' if day else ''} in SmartClass. "
                 "Run scripts/seed.py and a Moodle sync first.")
    return occ_id


async def setup(code: str, day: str | None) -> None:
    async with AsyncSessionLocal() as db:
        occ_id = await _lecture_id(db, code, day)
        open_id = await db.scalar(select(AttendanceSession.id).where(
            AttendanceSession.occurrence_id == occ_id, AttendanceSession.status == "open"))
        if open_id is not None:
            sys.exit(f"{code} lecture already has session {open_id} open; end it in the app and retry.")
        last = await db.scalar(select(func.max(AttendanceSession.id))) or 0
    with open(MARKER, "w") as f:
        json.dump({"occurrence_id": occ_id, "after_id": last}, f)
    print(f"{code} lecture (occurrence {occ_id}) is free; sessions after {last} are removed on teardown")


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
            await db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id.in_(ids)))
            await db.execute(delete(AttendanceSession).where(AttendanceSession.id.in_(ids)))
            await db.commit()
    os.remove(MARKER)
    print(f"removed E2E sessions {ids}")


async def _main(action: str, code: str, day: str | None) -> None:
    if action == "setup":
        await setup(code, day)
    else:
        await teardown()
    await engine.dispose()  # before the loop closes, or Windows prints "Event loop is closed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["setup", "teardown"])
    parser.add_argument("--course", default="WIF3001", help="course code whose lecture the flow starts")
    parser.add_argument("--day", help="the lecture on this weekday (Mon..Sun), for a course with several")
    args = parser.parse_args()
    asyncio.run(_main(args.action, args.course, args.day))
