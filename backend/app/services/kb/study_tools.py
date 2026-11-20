"""Flashcards and practice questions (FR-811).

Same retrieval as summaries/answers: a whole material's chunks, or the top-k for a
topic. The LLM is asked for a single JSON object, which is validated against the
`LLMCards`/`LLMQuestions` schemas; `llm.chat_json` retries malformed output once and
then fails (→ 502). Each item's `citation` (a 1-based passage index) is mapped to a
real `Citation`, and the source is "course" when any item cites a passage.
"""
import re

from app.core.config import settings
from app.schemas.assistant import (
    Citation, FlashcardOut, LLMCards, LLMQuestions, PracticeQuestionOut,
)
from app.services.kb import llm
from app.services.kb.assistant import format_passages
from app.services.kb.search import material_passages, search_materials

_SYSTEM = """You are the SmartClass learning assistant for {course}. Create {kind_label} for a \
university student from the numbered course-material passages below.

Reply with a single JSON object and nothing else (no markdown fences, no commentary).

{shape}

Rules:
- Take every item from the passages.
- "citation" is the number of the passage an item comes from (1 = the first passage below).
- If the passages don't cover the topic, return an empty list.
- Never invent citations or facts."""

_SHAPE = {
    "flashcards": 'JSON shape: {"cards": [{"front": "question side", "back": "answer side", "citation": 1}]}',
    "practice_questions": ('JSON shape: {"questions": [{"stem": "question", '
                           '"options": ["first option", "second option", "third option", "fourth option"], '
                           '"answer": "second option", "explanation": "why", "citation": 1}]}\n'
                           '"answer" is the full text of the correct option, copied exactly from "options" '
                           '(not a letter or number).'),
}

_LETTER = re.compile(r"^\(?([A-Ha-h1-8])[\).:]?(?:\s+(.*))?$", re.S)


def _answer_text(answer: str, options: list[str]) -> str | None:
    """The option the model meant as the answer, or None when it can't be told.

    Models often reply "B" or "B) text" even when asked for the option text; the app compares
    the pick with the option text, so a letter made every pick look wrong.
    """
    a = answer.strip()
    if a in options:
        return a
    by_lower = {o.strip().lower(): o for o in options}
    if a.lower() in by_lower:
        return by_lower[a.lower()]
    m = _LETTER.match(a)
    if m:
        key, rest = m.group(1), (m.group(2) or "").strip()
        if rest and rest.lower() in by_lower:
            return by_lower[rest.lower()]
        i = ord(key.upper()) - ord("A") if key.isalpha() else int(key) - 1
        if not rest and 0 <= i < len(options):
            return options[i]
    return None


_KIND_LABEL = {"flashcards": "flashcards", "practice_questions": "practice questions"}


def _citation(n: int | None, passages: list) -> Citation | None:
    if n is None or not (1 <= n <= len(passages)):
        return None
    p = passages[n - 1]
    return Citation(
        n=1, material_id=p.material_id, title=p.title, section=p.section_name,
        location=p.location_label, location_type=p.location_type,
        location_start=p.location_start, location_end=p.location_end,
        snippet=p.text[:280],
    )


async def generate_study_tools(db, course, *, material_id: int | None, topic: str | None,
                               kind: str) -> tuple[list, list, str]:
    """Return (cards, questions, source_type); the empty list is the other kind."""
    label = _KIND_LABEL[kind]
    if material_id is not None:
        passages = await material_passages(db, material_id)
        task = f"Create {label} covering this material."
        materials = format_passages(passages) if passages else "(This material has no readable text.)"
    else:
        passages = await search_materials(db, course.id, topic, k=settings.ASSISTANT_TOP_K)
        task = f"Create {label} for the topic: {topic}"
        materials = format_passages(passages) if passages else "(No course materials are indexed for this course yet.)"

    messages = [
        {"role": "system", "content": _SYSTEM.format(course=f"{course.code} {course.name}",
                                                     kind_label=label, shape=_SHAPE[kind])},
        {"role": "user", "content": f"Course material passages:\n\n{materials}\n\nTask: {task}"},
    ]

    if kind == "flashcards":
        data = await llm.chat_json(messages, max_tokens=settings.LLM_LONG_OUTPUT_TOKENS, validator=LLMCards.model_validate)
        cards = [FlashcardOut(front=c.front, back=c.back, citation=_citation(c.citation, passages))
                 for c in data.cards]
        source = "course" if any(c.citation for c in cards) else "general"
        return cards, [], source
    data = await llm.chat_json(messages, max_tokens=settings.LLM_LONG_OUTPUT_TOKENS, validator=LLMQuestions.model_validate)
    questions = []
    for q in data.questions:
        answer = _answer_text(q.answer, q.options)
        if answer is None:   # no option matches: the question can't be marked, so leave it out
            continue
        questions.append(PracticeQuestionOut(stem=q.stem, options=q.options, answer=answer,
                                             explanation=q.explanation,
                                             citation=_citation(q.citation, passages)))
    source = "course" if any(q.citation for q in questions) else "general"
    return [], questions, source
