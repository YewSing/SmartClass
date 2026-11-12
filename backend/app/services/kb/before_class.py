"""A short "before next class" summary for a lecturer (FR-816, NFR-09).

Built ONLY from the anonymised question trends (FR-813): topics asked by at least 3 distinct
students. The LLM prompt never carries student names, question texts, or a topic below that
minimum, so it can never leak an individual chat. With no aggregate above the minimum there
is no LLM call at all — the lecturer gets a fixed "not enough questions yet" note instead.

The result is cached in memory per course until the aggregate trends change (a new topic or a
student-count change), so repeated reads don't re-invoke the LLM.
"""
import hashlib
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.kb import llm, trends
from app.services.kb.answer_format import clean_latex
from app.services.kb.assistant import format_passages, parse_answer
from app.services.kb.search import Passage

NOT_ENOUGH_DATA = (
    "There are not enough questions yet to build a summary. Once several students have "
    "asked the assistant about this course, this note will show what to revisit and what "
    "the materials don't cover."
)

_SYSTEM_PROMPT = """You are the SmartClass learning assistant for {course}. Write a short "before next \
class" note for the lecturer.

Below are anonymised aggregates of what students asked (each topic was asked by at least 3 \
different students; there are no names, counts or question texts) and the numbered course \
material sections that cover them.

Write exactly two short sections in Markdown:
- "## Revisit" — what the lecturer should revisit next class, citing the relevant material \
  sections with their number in square brackets, like [1] or [1][2].
- "## Not covered by the materials" — the topics students asked about that the course \
  materials do not cover.

Rules:
- Cite only the numbered sections below; never invent a citation.
- Do not mention student names, counts or question texts.
- Plain text only: no LaTeX, no $ signs, no backslash commands."""

_cache: dict[int, tuple[str, dict]] = {}


def reset_cache() -> None:
    """Clear the in-memory cache (used by tests)."""
    _cache.clear()


def _trends_fingerprint(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def _empty() -> dict:
    return {"content": NOT_ENOUGH_DATA, "citations": [], "not_enough_data": True}


async def _sections_for_materials(db: AsyncSession, material_ids: list[int]) -> list[Passage]:
    """The first passage of each still-existing material, in material order.

    Only sections that exist are returned, so a deleted material can never be cited.
    """
    if not material_ids:
        return []
    rows = (await db.execute(text("""
        SELECT DISTINCT ON (c.material_id)
               c.id, c.material_id, m.title, m.section_name, c.location_type,
               c.location_start, c.location_end, c.heading, c.text
        FROM kb_chunks c JOIN kb_materials m ON m.id = c.material_id
        WHERE c.material_id = ANY(:ids)
        ORDER BY c.material_id, c.chunk_index
    """), {"ids": material_ids})).all()
    return [
        Passage(
            chunk_id=r.id, material_id=r.material_id, title=r.title, section_name=r.section_name,
            location_type=r.location_type, location_start=r.location_start,
            location_end=r.location_end, heading=r.heading, text=r.text,
            score=0.0, vector_similarity=0.0,
        )
        for r in rows
    ]


def _build_prompt(course, data: dict, sections: list[Passage]) -> list[dict]:
    asked = ", ".join(t["topic"] for t in data["most_asked_topics"]) or "(none)"
    uncovered = ", ".join(t["topic"] for t in data["topics_materials_dont_cover"]) or "(none)"
    sections_text = format_passages(sections) if sections else "(no cited material sections remain)"
    user = (
        f"Most-asked topics: {asked}\n\n"
        f"Course material sections to cite:\n\n{sections_text}\n\n"
        f"Topics the materials do not cover: {uncovered}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT.format(course=f"{course.code} {course.name}")},
        {"role": "user", "content": user},
    ]


async def _generate(db: AsyncSession, course, data: dict) -> dict:
    material_ids = [m["material_id"] for m in data["most_cited_materials"]]
    sections = await _sections_for_materials(db, material_ids)
    raw = await llm.chat(_build_prompt(course, data, sections))
    content, citations, _ = parse_answer(clean_latex(raw), sections)
    return {"content": content, "citations": citations, "not_enough_data": False}


async def before_class_summary(db: AsyncSession, course) -> dict:
    """The lecturer's "before next class" note (FR-816), cached until the trends change."""
    data = await trends.question_trends(db, course.id)
    if not (data["most_asked_topics"] or data["most_cited_materials"]
            or data["topics_materials_dont_cover"]):
        return _empty()

    fingerprint = _trends_fingerprint(data)
    cached = _cache.get(course.id)
    if cached is not None and cached[0] == fingerprint:
        return cached[1]

    result = await _generate(db, course, data)
    _cache[course.id] = (fingerprint, result)
    return result
