"""Keep each course's knowledge base in step with its Moodle (SPeCTRUM) page.

Diff by the file's stable key (module id + path + name):
- new key, or Moodle's timemodified changed, or last attempt errored -> download + ingest
- key gone from Moodle -> delete the material (its chunks cascade)
- otherwise -> skip (no download)
Moodle has no outbound webhooks, so this runs on a timer plus a "Sync now" button.
"""
import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import Course
from app.models.knowledge import MAT_ERROR, KbMaterial
from app.services.kb.ingest import MaterialMeta, ingest_file
from app.services.kb.moodle_client import MoodleClient, MoodleError, MoodleFile

log = logging.getLogger(__name__)


@dataclass
class SyncReport:
    course_code: str
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    failed: list[str] = field(default_factory=list)
    statuses: dict[str, int] = field(default_factory=dict)


def plan_sync(moodle_files: list[MoodleFile], existing: dict[str, KbMaterial]) -> tuple[list[MoodleFile], list[MoodleFile], list[str]]:
    """Pure diff: (new files, changed files, source_keys to delete)."""
    new, changed = [], []
    seen = set()
    for f in moodle_files:
        seen.add(f.source_key)
        mat = existing.get(f.source_key)
        if mat is None:
            new.append(f)
        elif mat.moodle_timemodified != f.timemodified or mat.status == MAT_ERROR:
            changed.append(f)
    gone = [key for key, mat in existing.items() if mat.source == "moodle" and key not in seen]
    return new, changed, gone


async def sync_course(db: AsyncSession, course: Course, client: MoodleClient) -> SyncReport:
    report = SyncReport(course.code)
    if course.moodle_course_id is None:
        course.moodle_course_id = await client.get_course_id(course.code)
        if course.moodle_course_id is None:
            raise MoodleError(f"No Moodle course with shortname {course.code}")

    moodle_files = await client.list_files(course.moodle_course_id)
    existing = {m.source_key: m for m in (await db.execute(
        select(KbMaterial).where(KbMaterial.course_id == course.id)
    )).scalars()}
    new, changed, gone = plan_sync(moodle_files, existing)
    report.unchanged = len(moodle_files) - len(new) - len(changed)

    if gone:
        await db.execute(delete(KbMaterial).where(
            KbMaterial.course_id == course.id, KbMaterial.source_key.in_(gone)))
        report.deleted = len(gone)
        await db.commit()

    for f, is_new in [(f, True) for f in new] + [(f, False) for f in changed]:
        try:
            data = await client.download(f.file_url)
        except Exception as exc:
            report.failed.append(f"{f.file_name}: download {exc}")
            continue
        meta = MaterialMeta(
            source_key=f.source_key, source="moodle", file_name=f.file_name, file_path=f.file_path,
            title=f.module_name, section_name=f.section_name, moodle_module_id=f.module_id,
            file_url=f.file_url, mimetype=f.mimetype, size_bytes=f.size, moodle_timemodified=f.timemodified,
        )
        mat = await ingest_file(db, course.id, meta, data)
        await db.commit()  # one file per transaction: a crash mid-sync keeps finished files
        if mat.status == MAT_ERROR:
            report.failed.append(f"{f.file_name}: {mat.error_text}")
        if is_new:
            report.added += 1
        else:
            report.updated += 1

    rows = (await db.execute(select(KbMaterial.status).where(KbMaterial.course_id == course.id))).scalars()
    for status in rows:
        report.statuses[status] = report.statuses.get(status, 0) + 1
    return report


async def sync_all() -> list[SyncReport]:
    """Sync every course that exists in Moodle (courses without a Moodle match are skipped)."""
    reports = []
    async with AsyncSessionLocal() as db, MoodleClient() as client:
        course_ids = (await db.execute(select(Course.id).order_by(Course.code))).scalars().all()
        for course_id in course_ids:
            # Re-fetch each course fresh: a failed course's rollback below expires every loaded
            # object, so holding onto Course instances across iterations breaks the next one.
            course = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one()
            code = course.code  # plain value, safe to log after the rollback
            try:
                if course.moodle_course_id is None and await client.get_course_id(code) is None:
                    continue
                reports.append(await sync_course(db, course, client))
                await db.commit()
            except Exception as exc:
                await db.rollback()
                log.warning("KB sync failed for %s: %s", code, exc)
    return reports


async def kb_sync_loop() -> None:
    """Background task started in main.py; disabled without a Moodle token."""
    if not settings.MOODLE_TOKEN or settings.KB_SYNC_INTERVAL_SECONDS <= 0:
        return
    while True:
        try:
            for r in await sync_all():
                if r.added or r.updated or r.deleted or r.failed:
                    log.info("KB sync %s: +%d ~%d -%d failed=%d", r.course_code, r.added, r.updated, r.deleted, len(r.failed))
        except Exception as exc:
            log.warning("KB sync loop error: %s", exc)
        await asyncio.sleep(settings.KB_SYNC_INTERVAL_SECONDS)
