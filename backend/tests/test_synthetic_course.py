"""T82: the synthetic test course indexes cleanly (shared by the live + replay suites)."""
import pytest
from sqlalchemy import select

from app.models.knowledge import EMBEDDING_DIM, MAT_INDEXED, KbChunk, KbMaterial
from tests.fixtures.synthetic import DOCS

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    vec = [1.0] + [0.0] * (EMBEDDING_DIM - 1)

    async def embed_query(text):
        return vec

    async def embed_passages(texts):
        return [vec for _ in texts]

    monkeypatch.setattr("app.services.kb.search.embed_query", embed_query)
    monkeypatch.setattr("app.services.kb.ingest.embed_passages", embed_passages)


async def test_synthetic_course_indexes_three_docs(synthetic_kb, db_session):
    mats = (await db_session.execute(
        select(KbMaterial).where(KbMaterial.course_id == synthetic_kb["course_id"])
    )).scalars().all()
    assert len(mats) == 3
    assert {m.title for m in mats} == {title for _, title in DOCS}
    assert all(m.status == MAT_INDEXED and m.chunk_count >= 1 for m in mats)

    chunks = (await db_session.execute(
        select(KbChunk).where(KbChunk.course_id == synthetic_kb["course_id"])
    )).scalars().all()
    assert len(chunks) >= 3


async def test_synthetic_docs_mention_the_key_terms(synthetic_kb, db_session):
    """The grounding checks in the live suite depend on these key terms being present."""
    text = " ".join(
        c.text for c in (await db_session.execute(
            select(KbChunk).where(KbChunk.course_id == synthetic_kb["course_id"])
        )).scalars()
    ).lower()
    for term in ("boundary", "equivalence", "representative", "branch", "weakest", "else", "statement"):
        assert term in text, f"synthetic course is missing the key term {term!r}"
