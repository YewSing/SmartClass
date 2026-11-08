"""Hybrid retrieval over a course's knowledge base.

Two searches, merged:
- vector (meaning): cosine distance between the question's embedding and each
  passage's. Finds paraphrases ("testing at range edges" ~ "boundary value analysis")
  but can miss exact codes/acronyms.
- keyword (Postgres full-text): stemmed word matching ranked by ts_rank. Finds exact
  terms ("JUnit", "MC/DC") but misses paraphrases.

Reciprocal Rank Fusion: score = sum over lists of 1 / (RRF_K + rank). It uses
ranks, not raw scores, so the two incomparable scales (cosine vs ts_rank) never
have to be calibrated against each other. A passage high in both lists wins.
"""
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.kb.embedder import embed_query

RRF_K = 60            # standard constant from the original RRF paper
CANDIDATES = 30       # how many each search contributes before fusion


@dataclass
class Passage:
    chunk_id: int
    material_id: int
    title: str
    section_name: str | None
    location_type: str
    location_start: int
    location_end: int
    heading: str | None
    text: str
    score: float              # fused RRF score
    vector_similarity: float  # cosine similarity (1 = identical meaning); used for the grounding check

    @property
    def location_label(self) -> str:
        name = {"page": "page", "slide": "slide", "section": "section"}[self.location_type]
        if self.location_start == self.location_end:
            return f"{name} {self.location_start}"
        return f"{name}s {self.location_start}-{self.location_end}"


_VECTOR_SQL = text("""
    SELECT id, 1 - (embedding <=> CAST(:vec AS vector)) AS sim
    FROM kb_chunks WHERE course_id = :course_id
    ORDER BY embedding <=> CAST(:vec AS vector)
    LIMIT :n
""")

# websearch_to_tsquery accepts free text safely (quotes, OR, -word) without syntax errors
_KEYWORD_SQL = text("""
    SELECT id, ts_rank_cd(tsv, q) AS rank
    FROM kb_chunks, websearch_to_tsquery('english', :query) q
    WHERE course_id = :course_id AND tsv @@ q
    ORDER BY rank DESC
    LIMIT :n
""")

_FETCH_SQL = text("""
    SELECT c.id, c.material_id, m.title, m.section_name, c.location_type, c.location_start,
           c.location_end, c.heading, c.text,
           1 - (c.embedding <=> CAST(:vec AS vector)) AS sim
    FROM kb_chunks c JOIN kb_materials m ON m.id = c.material_id
    WHERE c.id = ANY(:ids)
""")


async def search_materials(db: AsyncSession, course_id: int, query: str, k: int = 8) -> list[Passage]:
    """Top-k passages for `query` within one course (interface shared with Modules 5 and 6)."""
    vec = str(await embed_query(query))
    vector_hits = (await db.execute(_VECTOR_SQL, {"vec": vec, "course_id": course_id, "n": CANDIDATES})).all()
    keyword_hits = (await db.execute(_KEYWORD_SQL, {"query": query, "course_id": course_id, "n": CANDIDATES})).all()

    fused: dict[int, float] = {}
    for hits in (vector_hits, keyword_hits):
        for rank, row in enumerate(hits, start=1):
            fused[row.id] = fused.get(row.id, 0.0) + 1.0 / (RRF_K + rank)

    top_ids = sorted(fused, key=fused.get, reverse=True)[:k]
    if not top_ids:
        return []
    rows = {r.id: r for r in (await db.execute(_FETCH_SQL, {"ids": top_ids, "vec": vec})).all()}
    return [
        Passage(
            chunk_id=r.id, material_id=r.material_id, title=r.title, section_name=r.section_name,
            location_type=r.location_type, location_start=r.location_start, location_end=r.location_end,
            heading=r.heading, text=r.text, score=fused[r.id], vector_similarity=float(r.sim),
        )
        for r in (rows[i] for i in top_ids if i in rows)
    ]
