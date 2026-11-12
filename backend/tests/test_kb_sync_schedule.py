"""T81: scheduled material sync (FR-803) + lecturer materials status access (FR-804).

The manual "Sync now" endpoint (`POST /kb/courses/{id}/sync`), the status list
(`GET /kb/courses/{id}/materials`) and their access control are covered in
test_char_assistant.py. This file covers the *scheduled* path: `sync_all` runs over
every course, and `kb_sync_loop` is gated on the config.
"""
import asyncio

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.knowledge import EMBEDDING_DIM, MAT_INDEXED, KbMaterial
from app.services.kb import sync as kb_sync
from app.services.kb.moodle_client import MoodleFile
from tests.test_kb import make_pdf

pytestmark = pytest.mark.db

VEC = [1.0] + [0.0] * (EMBEDDING_DIM - 1)


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    async def embed_query(text):
        return VEC

    async def embed_passages(texts):
        return [VEC for _ in texts]

    monkeypatch.setattr("app.services.kb.search.embed_query", embed_query)
    monkeypatch.setattr("app.services.kb.ingest.embed_passages", embed_passages)


class FakeMoodle:
    """Async context manager standing in for MoodleClient inside sync_all()."""

    course_ids: dict[str, int | None] = {}
    files: dict[int, list[MoodleFile]] = {}
    data: dict[str, bytes] = {}
    error: Exception | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_course_id(self, shortname):
        return self.course_ids.get(shortname)

    async def list_files(self, course_id):
        if self.error:
            raise self.error
        return self.files.get(course_id, [])

    async def download(self, file_url):
        return self.data[file_url]


@pytest.fixture
def fake_moodle(monkeypatch):
    FakeMoodle.course_ids = {}
    FakeMoodle.files = {}
    FakeMoodle.data = {}
    FakeMoodle.error = None
    monkeypatch.setattr(kb_sync, "MoodleClient", FakeMoodle)
    return FakeMoodle


def _mf(module_id: int, name: str, modified: int = 100) -> MoodleFile:
    return MoodleFile(module_id, f"Lecture {module_id}", "Week 1", name, "/", f"http://m/{name}",
                      modified, 10, "application/pdf")


# ── the scheduled sync ─────────────────────────────────────────────────────────

async def test_sync_all_indexes_every_moodle_linked_course(classroom, fake_moodle, db_session):
    """The scheduled job syncs every course with a Moodle match, not just one."""
    pdf = make_pdf(["Verification checks we built the product right, against the specification."])
    FakeMoodle.course_ids = {"CS101": 101, "CS202": 202}
    FakeMoodle.files = {101: [_mf(1, "week1.pdf")], 202: [_mf(1, "other.pdf")]}
    FakeMoodle.data = {"http://m/week1.pdf": pdf, "http://m/other.pdf": pdf}

    reports = await kb_sync.sync_all()

    assert {r.course_code for r in reports} == {"CS101", "CS202"}
    by_code = {r.course_code: r for r in reports}
    assert (by_code["CS101"].added, by_code["CS101"].failed) == (1, [])
    assert (by_code["CS202"].added, by_code["CS202"].failed) == (1, [])

    db_session.expire_all()
    mats = (await db_session.execute(select(KbMaterial))).scalars().all()
    assert {m.file_name for m in mats} == {"week1.pdf", "other.pdf"}
    assert all(m.status == MAT_INDEXED and m.chunk_count >= 1 for m in mats)


async def test_sync_all_skips_courses_without_a_moodle_match(classroom, fake_moodle, db_session):
    """A course with no Moodle counterpart is skipped, the rest are synced."""
    pdf = make_pdf(["Verification checks we built the product right."])
    FakeMoodle.course_ids = {"CS101": 101}  # CS202 has no Moodle course
    FakeMoodle.files = {101: [_mf(1, "week1.pdf")]}
    FakeMoodle.data = {"http://m/week1.pdf": pdf}

    reports = await kb_sync.sync_all()

    assert [r.course_code for r in reports] == ["CS101"]
    db_session.expire_all()
    mats = (await db_session.execute(select(KbMaterial))).scalars().all()
    assert [m.file_name for m in mats] == ["week1.pdf"]


async def test_sync_all_isolates_a_failing_course(classroom, fake_moodle, db_session, monkeypatch):
    """One course failing to sync must not stop the others."""
    pdf = make_pdf(["Verification checks we built the product right."])
    FakeMoodle.course_ids = {"CS101": 101, "CS202": 202}

    class FlakyMoodle(FakeMoodle):
        async def list_files(self, course_id):
            if course_id == 101:
                raise RuntimeError("Moodle down")
            return self.files.get(course_id, [])

    FakeMoodle.files = {202: [_mf(1, "other.pdf")]}
    FakeMoodle.data = {"http://m/other.pdf": pdf}
    monkeypatch.setattr(kb_sync, "MoodleClient", FlakyMoodle)

    reports = await kb_sync.sync_all()

    assert [r.course_code for r in reports] == ["CS202"]
    db_session.expire_all()
    mats = (await db_session.execute(select(KbMaterial))).scalars().all()
    assert [m.file_name for m in mats] == ["other.pdf"]


# ── the loop's config gating ───────────────────────────────────────────────────

async def test_kb_sync_loop_disabled_without_token(monkeypatch):
    monkeypatch.setattr(settings, "MOODLE_TOKEN", "")
    assert await asyncio.wait_for(kb_sync.kb_sync_loop(), 1) is None


async def test_kb_sync_loop_disabled_at_zero_interval(monkeypatch):
    monkeypatch.setattr(settings, "MOODLE_TOKEN", "dummy-token")
    monkeypatch.setattr(settings, "KB_SYNC_INTERVAL_SECONDS", 0)
    assert await asyncio.wait_for(kb_sync.kb_sync_loop(), 1) is None
