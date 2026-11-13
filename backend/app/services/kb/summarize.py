"""Generate a summary or study guide for a material or topic (FR-810).

Same pipeline as answering a question: retrieve passages (a whole material, or the
top-k for a topic), prompt the LLM for structured Markdown with [n] citations, then
map the citations back through `parse_answer`. A topic the materials don't cover is
labelled general knowledge, exactly like a question (NFR-19).
"""
from app.core.config import settings
from app.services.kb import llm
from app.services.kb.answer_format import clean_latex
from app.services.kb.assistant import format_passages, parse_answer
from app.services.kb.search import material_passages, search_materials

KIND_LABEL = {"summary": "summary", "study_guide": "study guide"}

_SYSTEM_PROMPT = """You are the SmartClass learning assistant for {course}. You write study material \
for a university student.

Write a {kind} in Markdown from the numbered course-material passages below:
- Use "## " headings and "- " bullet points.
- Take every point from the passages and cite it with its number in square brackets,
  like [1] or [1][2].
- If the requested topic is not covered by the passages, write a short general note
  instead, starting with "This isn't covered in your course materials, so here's a
  general explanation:" and cite nothing.
- Never invent citations.
- Plain text only: no LaTeX, no $ signs, no backslash commands. Write formulas in plain text."""


async def summarize(db, course, *, material_id: int | None, topic: str | None,
                    kind: str) -> tuple[str, list[dict], str]:
    """Return (content, citations, source_type) for a summary or study guide."""
    label = KIND_LABEL[kind]
    if material_id is not None:
        passages = await material_passages(db, material_id)
        task = "Summarise this material." if kind == "summary" else "Write a study guide for this material."
        materials = format_passages(passages) if passages else "(This material has no readable text.)"
    else:
        passages = await search_materials(db, course.id, topic, k=settings.ASSISTANT_TOP_K)
        task = f"{label.capitalize()} for the topic: {topic}"
        materials = format_passages(passages) if passages else "(No course materials are indexed for this course yet.)"

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT.format(course=f"{course.code} {course.name}", kind=label)},
        {"role": "user", "content": f"Course material passages:\n\n{materials}\n\nTask: {task}"},
    ]
    raw = await llm.chat(messages, max_tokens=settings.LLM_LONG_OUTPUT_TOKENS)
    content, citations, source = parse_answer(clean_latex(raw), passages)
    return content, citations, source
