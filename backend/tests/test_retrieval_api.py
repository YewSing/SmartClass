"""T88: retrieval interface for Module 6 (FR-814)."""
import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.class_ import ClassOccurrence
from app.models.knowledge import EMBEDDING_DIM
from app.services.kb.retrieval_api import search

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


async def test_search_returns_passages_with_source(synthetic_kb):
    passages = await search(synthetic_kb["course_id"], "boundary value analysis", k=3)
    assert passages, "expected at least one passage"
    material_ids = set(synthetic_kb["material_ids"].values())
    for p in passages:
        assert p.material_id in material_ids
        assert p.title and p.text
        assert p.location_type in ("page", "slide", "section")
        assert p.location_start <= p.location_end


async def test_search_is_scoped_to_the_course(synthetic_kb, classroom):
    async with AsyncSessionLocal() as db:
        other_course_id = (await db.execute(
            select(ClassOccurrence.course_id)
            .where(ClassOccurrence.id == classroom["other_occurrence_id"])
        )).scalar_one()
    # CS202 has no indexed materials, so a search there returns nothing
    assert await search(other_course_id, "boundary value analysis") == []


async def test_search_honours_k(synthetic_kb):
    assert len(await search(synthetic_kb["course_id"], "testing", k=2)) <= 2
