"""Quiz question generation (FR-601, FR-602, FR-603, S30).

Drafts questions for a course by calling `retrieval_api.search` per selected material
(FR-814 — materials are never parsed) and the LLM via `chat_json`. Malformed LLM output
is retried once, then a 502 (`LLMMalformedOutput`); provider errors propagate as
`LLMUnavailable` (503). Every question carries its source material id and topic (from the
Passage source). Ownership (NFR-04: only the course's lecturer) is checked by the caller.

Draft questions are standalone (quiz_id NULL, status "draft"); S31 links them to a quiz.
"""

from app.core.database import AsyncSessionLocal
from app.models.quiz import QuizQuestion
from app.schemas.quiz import GeneratedQuestion
from app.services.kb import llm
from app.services.kb.retrieval_api import search

_QUESTION_PROMPT = """You draft one exam question for a university course, based ONLY on the
passage below. Return a single JSON object with exactly these keys:
- "question": the question text (string)
- "options": 2-5 option strings (mcq) or an empty list (short_answer)
- "correct_answer": the correct option text (mcq) or null (short_answer)
- "suggested_answer": the ideal short answer (short_answer) or null (mcq)
- "level": one of beginner, intermediate, advanced
- "topic": a short topic name (2-5 words) drawn from the passage
Reply with only the JSON object.

Passage (source: {source}, {location}):
{text}

Question type: {qtype}. Level: {level}."""


async def generate_questions(
    course_id: int,
    material_ids: list[int],
    qtype: str,
    level: str,
    count: int,
) -> list[QuizQuestion]:
    """Draft `count` questions from the selected materials and persist them as drafts.

    Returns the created `QuizQuestion` rows (status "draft", quiz_id None).
    """
    # Gather candidate passages, round-robin across the selected materials so each
    # material contributes. `search` is scoped to course_id; we keep passages whose
    # material_id matches the material we searched for.
    per_material: dict[int, list] = {}
    for material_id in material_ids:
        passages = await search(course_id, f"material {material_id}", k=count)
        per_material[material_id] = [p for p in passages if p.material_id == material_id]

    created: list[QuizQuestion] = []
    idx = 0
    while len(created) < count:
        material_id = material_ids[idx % len(material_ids)]
        pool = per_material.get(material_id, [])
        if not pool:
            # move on; if every pool is exhausted we stop with what we have
            if all(not per_material[m] for m in material_ids):
                break
            idx += 1
            continue
        passage = pool.pop(0)
        idx += 1

        prompt = _QUESTION_PROMPT.format(
            source=passage.title,
            location=passage.location_label,
            text=passage.text[:2500],
            qtype=qtype,
            level=level,
        )
        try:
            generated = await llm.chat_json(
                [{"role": "user", "content": prompt}],
                validator=GeneratedQuestion,
            )
        except llm.LLMMalformedOutput:
            # skip this passage, try the next
            continue

        q = QuizQuestion(
            course_id=course_id,
            type=qtype,
            question=generated.question,
            options=generated.options or None,
            correct_answer=generated.correct_answer,
            suggested_answer=generated.suggested_answer,
            level=generated.level,
            source_material_id=passage.material_id,
            topic=generated.topic or passage.heading,
            status="draft",
        )
        async with AsyncSessionLocal() as db:
            db.add(q)
            await db.commit()
            await db.refresh(q)
            created.append(q)
    return created
