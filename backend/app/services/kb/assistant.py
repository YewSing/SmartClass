"""Answer a student's question from their course materials (retrieval-augmented generation).

Flow for one question:
1. quiz lock     - refuse while a graded quiz attempt is open in this course
2. rewrite       - turn a follow-up ("what about its drawbacks?") into a standalone query
3. retrieve      - hybrid search for the top passages in this course only
4. prompt        - numbered passages [1]..[k] + rules + recent turns + the question
5. generate      - LLM answers, citing passages as [n]
6. cite          - map the [n] actually used back to material + page/slide; an answer
                   with citations is "course", one without is "general"
7. save          - store both messages (retrieval_query feeds later lecturer insights)
"""
import asyncio
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timezone import now_myt
from app.models.ai_chat import ChatMessage, ChatSession
from app.models.class_ import Course
from app.services.kb import llm
from app.services.kb.answer_format import clean_latex
from app.services.kb.integrations import get_active_attempt
from app.services.kb.search import Passage, search_materials

SOURCE_COURSE, SOURCE_GENERAL, SOURCE_REFUSED = "course", "general", "refused"

QUIZ_LOCK_MESSAGE = (
    "You have a graded quiz open for this course, so I can't help with course questions "
    "until you submit it. Good luck!"
)

_SYSTEM_PROMPT = """You are the SmartClass learning assistant for {course}, a course at Universiti Malaya.
You help students understand their lecturer's materials.

Rules:
1. Answer from the numbered course material passages when they cover the question. Cite every
   fact you take from them with its number in square brackets, like [2] or [1][3].
2. If the passages do not cover the question, you may answer from general knowledge, but start
   with: "This isn't covered in your course materials, so here's a general explanation:" and
   cite nothing anywhere in the answer.
3. Never invent citations or cite a passage that does not support the sentence.
4. Be clear and concise for a university student. Use short paragraphs or bullet points.
5. If the question has nothing to do with studying, politely steer back to the course. You may
   name course topics when you do, but do not cite passages for them: an answer that does not
   use the passages cites nothing.
6. Students read your answer as plain text on a phone. Never use LaTeX, $ signs or backslash
   commands. Write formulas in plain text, like (a + b) / c, x^2, sqrt(n), 3 × 4 or 50%."""

_REWRITE_PROMPT = """Rewrite the student's latest question as a standalone search query for their course
materials, resolving words like "it" or "that" from the conversation. Reply with the query only."""

_TOPIC_LABEL_PROMPT = ("Label the student's question with a short topic of 2-5 words in sentence case "
                       "(for example \"Boundary value analysis\"), so a lecturer can see what students "
                       "ask about. Name the concept, not a file or lecture. If one of the existing topics "
                       "below fits, reply with it exactly, so the same question is counted together. "
                       "Reply with the topic only.")

# Budget for the short helper calls (follow-up rewrite, topic label). Thinking models
# (deepseek-flash, Gemini 3.x) count hidden reasoning tokens against max_tokens, so a tight
# limit like 60 can be spent entirely on reasoning and return an empty or cut-off reply.
_SHORT_CALL_MAX_TOKENS = 400

_CITE_RE = re.compile(r"\[(\d{1,2})\]")


def format_passages(passages: list[Passage]) -> str:
    blocks = []
    for n, p in enumerate(passages, start=1):
        where = f"{p.title}, {p.location_label}" + (f" ({p.section_name})" if p.section_name else "")
        blocks.append(f"[{n}] {where}\n{p.text}")
    return "\n\n".join(blocks)


def parse_answer(raw: str, passages: list[Passage]) -> tuple[str, list[dict], str]:
    """Keep only citation numbers that exist, and build citation objects.

    Citations are renumbered 1, 2, 3... by first appearance, in the text and in the list, so an
    answer citing passages [4] and [2] shows [1] and [2] under it.
    """
    text = raw.rstrip()

    used: list[int] = []
    for m in _CITE_RE.finditer(text):
        n = int(m.group(1))
        if 1 <= n <= len(passages) and n not in used:
            used.append(n)
    new_number = {old: new for new, old in enumerate(used, start=1)}
    # Renumber, and drop citations to passages that don't exist ("[9]" with only 8 passages)
    text = _CITE_RE.sub(lambda m: f"[{new_number[int(m.group(1))]}]" if int(m.group(1)) in new_number else "",
                        text)

    citations = []
    for new, n in enumerate(used, start=1):
        p = passages[n - 1]
        citations.append({
            "n": new, "material_id": p.material_id, "title": p.title, "section": p.section_name,
            "location": p.location_label, "location_type": p.location_type,
            "location_start": p.location_start, "location_end": p.location_end,
            "snippet": p.text[:280],
        })

    # The label comes from evidence, not from asking the model: cited -> course material.
    source = SOURCE_COURSE if citations else SOURCE_GENERAL
    return text, citations, source


async def _history(db: AsyncSession, session_id: int) -> list[dict]:
    turns = settings.ASSISTANT_HISTORY_TURNS * 2
    rows = (await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id,
                                       ChatMessage.source_type.is_distinct_from(SOURCE_REFUSED))
        .order_by(ChatMessage.id.desc()).limit(turns)
    )).scalars().all()
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


async def _standalone_query(question: str, history: list[dict]) -> str:
    if not history or not settings.ASSISTANT_REWRITE_FOLLOWUPS:
        return question
    convo = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in history[-4:])
    try:
        rewritten = await llm.chat(
            [{"role": "system", "content": _REWRITE_PROMPT},
             {"role": "user", "content": f"Conversation:\n{convo}\n\nLatest question: {question}"}],
            max_tokens=_SHORT_CALL_MAX_TOKENS, temperature=0,
        )
        return rewritten.strip().strip('"') or question
    except llm.LLMUnavailable:
        return question


async def _existing_topics(db: AsyncSession, course_id: int, limit: int = 40) -> list[str]:
    """The course's most recent distinct topic labels, so a new label can reuse one."""
    rows = (await db.execute(
        select(ChatMessage.topic)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(ChatSession.course_id == course_id, ChatMessage.topic.is_not(None))
        .group_by(ChatMessage.topic)
        .order_by(func.max(ChatMessage.id).desc())
        .limit(limit)
    )).scalars().all()
    return list(rows)


async def _label_topic(question: str, existing: list[str] | None = None) -> str | None:
    """A short, anonymised topic for a question (FR-813), reusing an existing one when it fits.

    Best-effort: if the LLM is down or the quota is gone, the question is left untagged
    (it simply won't appear in the lecturer's topic lists).
    """
    known = "\n".join(f"- {t}" for t in existing or []) or "(none yet)"
    try:
        label = await llm.chat(
            [{"role": "system", "content": f"{_TOPIC_LABEL_PROMPT}\n\nExisting topics:\n{known}"},
             {"role": "user", "content": question}],
            max_tokens=_SHORT_CALL_MAX_TOKENS, temperature=0,
        )
    except llm.LLMUnavailable:
        return None
    label = label.strip().strip('"').strip().rstrip(".")
    if not label or len(label) > 80:
        return None
    for t in existing or []:   # same topic, different capitalisation -> one topic
        if t.lower() == label.lower():
            return t
    return label


async def answer_question(db: AsyncSession, session: ChatSession, course: Course, question: str) -> ChatMessage:
    """Save the student's question and the assistant's answer; return the answer message."""
    history = await _history(db, session.id)
    user_msg = ChatMessage(session_id=session.id, role="user", content=question)
    db.add(user_msg)

    if session.student_id is not None and await get_active_attempt(session.student_id, course.id) is not None:
        user_msg.source_type = SOURCE_REFUSED
        reply = ChatMessage(session_id=session.id, role="assistant", content=QUIZ_LOCK_MESSAGE,
                                 citations=[], source_type=SOURCE_REFUSED)
        db.add(reply)
        await db.flush()
        return reply

    query = await _standalone_query(question, history)
    user_msg.retrieval_query = query
    passages = await search_materials(db, course.id, query, k=settings.ASSISTANT_TOP_K)

    messages = [{"role": "system", "content": _SYSTEM_PROMPT.format(course=f"{course.code} {course.name}")}]
    messages += history
    materials = format_passages(passages) if passages else "(No course materials are indexed for this course yet.)"
    messages.append({"role": "user", "content": f"Course material passages:\n\n{materials}\n\nQuestion: {question}"})

    # The topic label (FR-813) runs alongside the answer, so it adds no waiting time. It is
    # a concept like "Boundary value analysis", never a file name, for course answers too.
    existing = await _existing_topics(db, course.id)
    topic, raw = await asyncio.gather(
        _label_topic(query, existing),
        llm.chat(messages),  # LLMUnavailable propagates -> 503, nothing is saved
    )
    content, citations, source = parse_answer(clean_latex(raw), passages)
    if source not in (SOURCE_COURSE, SOURCE_GENERAL):
        topic = None

    reply = ChatMessage(session_id=session.id, role="assistant", content=content,
                             citations=citations, source_type=source, topic=topic)
    db.add(reply)
    if not session.title:
        session.title = question[:60]
    session.updated_at = now_myt()
    await db.flush()
    return reply
