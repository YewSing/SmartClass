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
    query: str | None = None,
) -> list[QuizQuestion]:
    """Draft `count` questions from the selected materials and persist them as drafts.

    `query` is the retrieval text for picking passages (FR-814): the lecturer's
    instruction when one exists, otherwise each material's own title. Returns the
    created `QuizQuestion` rows (status "draft", quiz_id None).
    """
    # Retrieve with meaningful text: a bare "material 5" scores nothing in vector or
    # keyword search, so every pool came back empty and questions fell back to the
    # instruction alone. Without a query, use each material's own title/filename.
    if query:
        search_texts = {mid: query for mid in material_ids}
    else:
        from app.models.knowledge import KbMaterial
        async with AsyncSessionLocal() as db:
            rows = await db.execute(
                select(KbMaterial.id, KbMaterial.title).where(KbMaterial.id.in_(material_ids))
            )
        title_map = dict(rows.all())
        search_texts = {
            mid: (title_map.get(mid) or f"material {mid}")
            for mid in material_ids
        }

    # Gather candidate passages per material. `search` is scoped to course_id; we keep
    # passages whose material_id matches the material we searched for. Each material is
    # asked for an equal share of `count` (ceil) — a material with no retrievable text
    # simply contributes nothing rather than stealing another's quota.
    quota = -(-count // len(material_ids))
    # all materials share the same query, so one can dominate the top hits — ask for
    # enough to cover every material's share before filtering by material_id
    k = max(quota * len(material_ids), 8)
    per_material: dict[int, list] = {}
    for material_id in material_ids:
        passages = await retrieval_api.search(course_id, search_texts[material_id], k=k)
        per_material[material_id] = [p for p in passages if p.material_id == material_id]

    created: list[QuizQuestion] = []
    for material_id in material_ids:
        made = 0
        while made < quota:
            pool = per_material.get(material_id, [])
            if not pool:
                # re-search once before giving up on the material (the fake/live search
                # may return one passage per call; asking again yields the next chunk)
                passages = await retrieval_api.search(course_id, search_texts[material_id], k=k)
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
                validator=GeneratedQuestion.model_validate,
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
        validator=QuickAddSpec.model_validate,
    )


_INSTRUCTION_PROMPT = """You draft one exam question for a university course, based ONLY on
the lecturer's instruction below (no course material is provided). Return a single JSON
object with exactly these keys:
- "question": the question text (string)
- "options": 2-5 option strings (mcq) or an empty list (short_answer)
- "correct_answer": the correct option text (mcq) or null (short_answer)
- "suggested_answer": the ideal short answer (short_answer) or null (mcq)
- "level": one of beginner, intermediate, advanced
- "topic": a short topic name (2-5 words) drawn from the instruction
Reply with only the JSON object.

Lecturer's instruction: {instruction}

Question type: {qtype}. Level: {level}."""


async def generate_questions_from_instruction(
    course_id: int,
    instruction: str,
    qtype: str,
    level: str,
    count: int,
) -> list["QuizQuestion"]:
    """Draft `count` questions from the lecturer's instruction alone — used when the
    quick-add flow runs without any material selected. Questions carry no source
    material (source_material_id NULL); topic comes from the LLM."""
    created: list["QuizQuestion"] = []
    for _ in range(count):
        prompt = _INSTRUCTION_PROMPT.format(instruction=instruction[:2000], qtype=qtype, level=level)
        generated = await llm.chat_json(
            [{"role": "user", "content": prompt}],
            validator=GeneratedQuestion.model_validate,
        )
        q = QuizQuestion(
            course_id=course_id,
            type=qtype,
            question=generated.question,
            options=generated.options or None,
            correct_answer=generated.correct_answer,
            suggested_answer=generated.suggested_answer,
            level=level,  # the lecturer's requested level wins (FR-602)
            source_material_id=None,
            topic=generated.topic,
            status="draft",
        )
        async with AsyncSessionLocal() as db:
            db.add(q)
            await db.commit()
            await db.refresh(q)
            created.append(q)
    return created


async def quick_add_quiz(
    db,
    course_id: int,
    prompt: str,
    material_ids: list[int],
    level: str,
    created_by: int,
) -> tuple["Quiz", list["QuizQuestion"]]:
    """Parse the prompt, draft the requested questions and save everything as one draft
    quiz (review → publish later). Returns (quiz, questions).

    With materials selected the questions are grounded in them (retrieval per material);
    with none, the course's latest indexed materials are used; if the course has none
    indexed at all the questions are drafted from the prompt + level alone.
    """
    spec = await parse_quick_add(prompt)

    # A natural message may not state any counts ("make me a quiz about chapter 3").
    # Rather than 422-ing, default to a small quiz: 3 MCQs.
    if spec.mcq_count == 0 and spec.short_answer_count == 0:
        spec.mcq_count = 3

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

    questions: list["QuizQuestion"] = []
    for qtype, count in (("mcq", spec.mcq_count), ("short_answer", spec.short_answer_count)):
        if count <= 0:
            continue
        if ids:
            # grounded: retrieval per material (FR-814 — materials are never parsed)
            questions.extend(await generate_questions(course_id, ids, qtype, level, count, query=prompt))
            # the selected materials may have no retrievable text for this course (e.g.
            # stale indexing) — fall back to the prompt alone rather than failing
            if len(questions) == 0:
                questions.extend(
                    await generate_questions_from_instruction(course_id, prompt, qtype, level, count)
                )
        else:
            # no materials selected: prompt + level only
            questions.extend(
                await generate_questions_from_instruction(course_id, prompt, qtype, level, count)
            )
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
