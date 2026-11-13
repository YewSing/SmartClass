"""Study tools inside the chat (FR-810, FR-811; redesign of 2026-11-13).

A student picks a tool from the chat's study tools menu and types a topic. The request is
saved as a user message and the result as an assistant message of the same `kind`, so it
stays in the chat history and can be reopened. Flashcards and practice questions keep their
structured data in `payload` for the full-screen views; `content` holds a plain-text copy,
so a follow-up like "explain card 3" has the cards in the conversation history.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_myt
from app.models.ai_chat import ChatMessage, ChatSession
from app.models.class_ import Course
from app.services.kb.assistant import QUIZ_LOCK_MESSAGE, SOURCE_REFUSED, _existing_topics, _label_topic
from app.services.kb.integrations import get_active_attempt
from app.services.kb.study_tools import generate_study_tools
from app.services.kb.summarize import summarize

TOOL_LABEL = {
    "summary": "Summary",
    "study_guide": "Study guide",
    "flashcards": "Flashcards",
    "practice_questions": "Practice",
}


def _cards_text(cards) -> str:
    lines = [f"{i}. {c.front} — {c.back}" for i, c in enumerate(cards, start=1)]
    return "Flashcards:\n" + "\n".join(lines) if lines else "No flashcards could be made for this topic."


def _questions_text(questions) -> str:
    lines = [f"{i}. {q.stem} (answer: {q.answer})" for i, q in enumerate(questions, start=1)]
    return "Practice questions:\n" + "\n".join(lines) if lines else "No practice questions could be made for this topic."


def _unique_citations(items) -> list[dict]:
    """The distinct sources the cards/questions cite, numbered for the message's chips."""
    seen, out = set(), []
    for item in items:
        c = item.citation
        if c is None:
            continue
        key = (c.material_id, c.location_start, c.location_end)
        if key in seen:
            continue
        seen.add(key)
        out.append({**c.model_dump(exclude={"open_page", "file_url"}), "n": len(out) + 1})
    return out


async def run_chat_tool(db: AsyncSession, session: ChatSession, course: Course, kind: str,
                        topic: str) -> ChatMessage:
    """Save the tool request and its result in the chat; return the result message.

    `LLMUnavailable` / `LLMMalformedOutput` propagate before anything is written, so a
    failed generation leaves the chat unchanged (the router maps them to 503 / 502).
    """
    topic = topic.strip()
    request = ChatMessage(session_id=session.id, role="user", kind=kind,
                          content=f"{TOOL_LABEL[kind]}: {topic}")

    if session.student_id is not None and await get_active_attempt(session.student_id, course.id) is not None:
        request.source_type = SOURCE_REFUSED
        reply = ChatMessage(session_id=session.id, role="assistant", content=QUIZ_LOCK_MESSAGE,
                            citations=[], source_type=SOURCE_REFUSED)
        db.add_all([request, reply])
        await db.flush()
        return reply

    if kind in ("summary", "study_guide"):
        content, citations, source = await summarize(db, course, material_id=None, topic=topic, kind=kind)
        payload = {"topic": topic}
    else:
        cards, questions, source = await generate_study_tools(db, course, material_id=None, topic=topic,
                                                              kind=kind)
        if kind == "flashcards":
            content = _cards_text(cards)
            citations = _unique_citations(cards)
            payload = {"topic": topic, "cards": [c.model_dump(mode="json") for c in cards]}
        else:
            content = _questions_text(questions)
            citations = _unique_citations(questions)
            payload = {"topic": topic, "questions": [q.model_dump(mode="json") for q in questions],
                       "last_score": None}

    label = await _label_topic(topic, await _existing_topics(db, course.id))
    reply = ChatMessage(session_id=session.id, role="assistant", kind=kind, content=content,
                        citations=citations, source_type=source, topic=label, payload=payload)
    db.add_all([request, reply])
    if not session.title:
        session.title = request.content[:60]
    session.updated_at = now_myt()
    await db.flush()
    return reply
