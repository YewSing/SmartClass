"""Remove camera devices the T46 Playwright test registered (rooms starting with "E2E T46 ").

    python scripts/e2e_devices.py clean

Run from backend/ against the dev database (DATABASE_URL in .env). Audit log lines stay.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select, update

from app.core.database import AsyncSessionLocal, engine
from app.models.camera import Camera
from app.models.session import AttendanceSession

PREFIX = "E2E T46 %"


async def clean() -> None:
    async with AsyncSessionLocal() as db:
        camera_ids = (await db.execute(
            select(Camera.id).where(Camera.room.like(PREFIX))
        )).scalars().all()
        if camera_ids:
            # The FK has no ondelete, so a session pointing at one of them would block the delete.
            # None should: the test never opens a class in these rooms.
            await db.execute(
                update(AttendanceSession)
                .where(AttendanceSession.camera_id.in_(camera_ids))
                .values(camera_id=None)
            )
        result = await db.execute(delete(Camera).where(Camera.room.like(PREFIX)))
        removed = result.rowcount or 0
        await db.commit()
    print(f"removed {removed} camera device{'s' if removed != 1 else ''}")


async def _main(args) -> None:
    try:
        await clean()
    finally:
        await engine.dispose()   # before the loop closes, or Windows prints "Event loop is closed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["clean"])
    asyncio.run(_main(parser.parse_args()))
