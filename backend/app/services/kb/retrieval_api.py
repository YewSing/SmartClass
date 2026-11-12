"""Retrieval interface for Module 6 (FR-814): quiz generation.

Module 6 needs passages from a course's knowledge base to draft questions, but it should
not have to parse the materials itself. It calls `search(course_id, query, k)` and gets
back the top-k passages, each carrying its source file and page/slide/section location.

This is a thin wrapper over `app.services.kb.search.search_materials` that owns its own
database session, so the caller doesn't need one. Documented in `docs/interfaces.md`.
"""
from app.core.database import AsyncSessionLocal
from app.services.kb.search import Passage, search_materials


async def search(course_id: int, query: str, k: int = 8) -> list[Passage]:
    """Top-k passages for `query` within one course, each with its source location.

    Returns `Passage` objects (`app.services.kb.search`): `material_id`/`title` (the file),
    `section_name`, `location_type` + `location_start`/`location_end` (page / slide /
    section), `heading` and `text`, plus the fused `score` and `vector_similarity`.
    """
    async with AsyncSessionLocal() as db:
        return await search_materials(db, course_id, query, k=k)
