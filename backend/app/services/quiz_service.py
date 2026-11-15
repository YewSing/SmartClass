"""Quiz question generation (FR-601, FR-602, FR-603, S30).

Drafts questions for a course by calling `retrieval_api.search` per selected material
(FR-814 — materials are never parsed) and the LLM via `chat_json`. Malformed LLM output
is retried once, then a 502 (`LLMMalformedOutput`); provider errors propagate as
`LLMUnavailable` (503). Every question carries its source material id and topic (from the
Passage source). Ownership (NFR-04: only the course's lecturer) is checked by the caller.

Draft questions are standalone (quiz_id NULL, status "draft"); S31 links them to a quiz.
"""

from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.quiz import Quiz, QuizQuestion
from app.schemas.quiz import GeneratedQuestion, QuickAddSpec
from app.services.kb import llm, retrieval_api

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
    # Gather candidate passages per material. `search` is scoped to course_id; we keep
    # passages whose material_id matches the material we searched for. Each material is
    # asked for an equal share of `count` (ceil) — a material with no retrievable text
    # simply contributes nothing rather than stealing another's quota.
    quota = -(-count // len(material_ids))
    per_material: dict[int, list] = {}
    for material_id in material_ids:
        passages = await retrieval_api.search(course_id, f"material {material_id}", k=quota)
        per_material[material_id] = [p for p in passages if p.material_id == material_id]

    created: list[QuizQuestion] = []
    for material_id in material_ids:
        made = 0
        while made < quota:
            pool = per_material.get(material_id, [])
            if not pool:
                # re-search once before giving up on the material (the fake/live search
                # may return one passage per call; asking again yields the next chunk)
                passages = await retrieval_api.search(course_id, f"material {material_id}", k=quota)
                pool = [p for p in passages if p.material_id == material_id]
                per_material[material_id] = pool
                if not pool:
                    break  # no retrievable text for this material
            passage = pool.pop(0)

            prompt = _QUESTION_PROMPT.format(
                source=passage.title,
                location=passage.location_label,
                text=passage.text[:2500],
                qtype=qtype,
                level=level,
            )
            # LLMMalformedOutput / LLMUnavailable propagate (the adapter already retries
            # once); the router maps them to 502/503 — malformed output is never silently
            # skipped, or the lecturer would get fewer questions than asked
            generated = await llm.chat_json(
                [{"role": "user", "content": prompt}],
                validator=GeneratedQuestion,
            )

            q = QuizQuestion(
                course_id=course_id,
                type=qtype,
                question=generated.question,
                options=generated.options or None,
                correct_answer=generated.correct_answer,
                suggested_answer=generated.suggested_answer,
                level=level,  # the lecturer's requested level wins (FR-602)
                source_material_id=passage.material_id,
                topic=generated.topic or passage.heading,
                status="draft",
            )
            async with AsyncSessionLocal() as db:
                db.add(q)
                await db.commit()
                await db.refresh(q)
                created.append(q)
            made += 1
    return created


# ── LLM quick-add (S35): "create 5 mcq, 2 short answer, 15min, valid two days" ──

_QUICK_ADD_PROMPT = """A lecturer typed a quick instruction for building a quiz. Extract the
quiz spec. Return a single JSON object with exactly these keys:
- "title": a short quiz title (string or null if not given)
- "mcq_count": how many multiple-choice questions (0 if none)
- "short_answer_count": how many short-answer questions (0 if none)
- "time_limit_minutes": the time limit in minutes (null if not given)
- "valid_days": how many days from now the quiz stays open ("valid two days" -> 2; null if not given)
- "attempts_allowed": how many attempts students get (default 1)
- "review_visible": whether students may see results after answering (default true)
Instruction: {prompt}

Reply with only the JSON object."""


async def parse_quick_add(prompt: str) -> QuickAddSpec:
    """Parse the lecturer's quick-add sentence into a spec via `chat_json`
    (malformed output retried once by the adapter, then LLMMalformedOutput)."""
    return await llm.chat_json(
        [{"role": "user", "content": _QUICK_ADD_PROMPT.format(prompt=prompt)}],
        validator=QuickAddSpec,
    )


async def quick_add_quiz(
    db,
    course_id: int,
    prompt: str,
    material_ids: list[int],
    level: str,
    created_by: int,
) -> tuple["Quiz", list["QuizQuestion"]]:
    """Parse the prompt, draft the requested questions from the materials and save
    everything as one draft quiz (review → publish later). Returns (quiz, questions).

    Materials default to every indexed material of the course when none are passed.
    """
    spec = await parse_quick_add(prompt)

    if material_ids:
        ids = material_ids
    else:
        from app.models.knowledge import KbMaterial
        rows = await db.execute(
            select(KbMaterial.id).where(
                KbMaterial.course_id == course_id,
                KbMaterial.status.in_(("indexed", "no_text")),
            ).order_by(KbMaterial.id.desc()).limit(5)
        )
        ids = [r for (r,) in rows.all()]
    if not ids:
        raise ValueError("no_materials")

    questions: list[QuizQuestion] = []
    for qtype, count in (("mcq", spec.mcq_count), ("short_answer", spec.short_answer_count)):
        if count <= 0:
            continue
        # generate_questions commits with its own session; rows come back detached-safe
        questions.extend(await generate_questions(course_id, ids, qtype, level, count))
    if not questions:
        raise ValueError("no_questions_generated")

    now = datetime.now()
    quiz = Quiz(
        course_id=course_id,
        title=spec.title or "Untitled quiz",
        time_limit_minutes=spec.time_limit_minutes,
        opens_at=now,
        closes_at=now + timedelta(days=spec.valid_days) if spec.valid_days is not None else None,
        attempts_allowed=spec.attempts_allowed,
        review_visible=spec.review_visible,
        status="draft",
        created_by=created_by,
    )
    db.add(quiz)
    await db.flush()
    # the generated rows belong to generate_questions' own session — link them with an
    # UPDATE so detached objects are handled the same as session-attached ones
    import sqlalchemy as sa
    await db.execute(
        sa.update(QuizQuestion)
        .where(QuizQuestion.id.in_([q.id for q in questions]))
        .values(quiz_id=quiz.id)
    )
    await db.commit()
    await db.refresh(quiz)
    return quiz, questions
