"""Sync course materials from Moodle into the knowledge base.

Usage (from backend/):
    python scripts/kb_sync.py --course WIF3001
    python scripts/kb_sync.py --all
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.models.class_ import Course  # noqa: E402
from app.services.kb.moodle_client import MoodleClient  # noqa: E402
from app.services.kb.sync import sync_all, sync_course  # noqa: E402


def show(r) -> None:
    print(f"{r.course_code}: added={r.added} updated={r.updated} unchanged={r.unchanged} "
          f"deleted={r.deleted} statuses={r.statuses}")
    for f in r.failed:
        print(f"  FAILED {f}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--course", help="course code, e.g. WIF3001")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()

    start = time.perf_counter()
    if args.all:
        for r in await sync_all():
            show(r)
    else:
        async with AsyncSessionLocal() as db, MoodleClient() as client:
            course = (await db.execute(select(Course).where(Course.code == args.course))).scalar_one()
            show(await sync_course(db, course, client))
            await db.commit()
    print(f"done in {time.perf_counter() - start:.1f}s")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
