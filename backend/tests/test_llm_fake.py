"""LLM_FAKE=1 (used by the mobile E2E flows): canned answers without any provider call."""
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.ai_chat import ChatMessage, ChatSession
from app.services.kb import llm
from app.services.kb.assistant import SOURCE_COURSE, SOURCE_GENERAL, _REWRITE_PROMPT, _SYSTEM_PROMPT
from tests.test_char_assistant import VEC, _add_material, _new_chat


@pytest.fixture
def fake_mode(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FAKE", True)
    monkeypatch.setattr(settings, "LLM_API_KEY", "")   # proves no provider client is needed

    def no_client():
        raise AssertionError("LLM_FAKE must not create a provider client")

    monkeypatch.setattr(llm, "_get_client", no_client)


@pytest.fixture
def fixed_query_embedding(monkeypatch):
    async def embed_query(text):
        return VEC

    monkeypatch.setattr("app.services.kb.search.embed_query", embed_query)


async def test_fake_answer_cites_first_passage_when_passages_given(fake_mode):
    out = await llm.chat([
        {"role": "system", "content": _SYSTEM_PROMPT.format(course="CS101 Testing")},
        {"role": "user", "content": "Course material passages:\n\n[1] Deck, slide 4\ntext\n\nQuestion: what?"},
    ])
    assert out == llm.FAKE_COURSE_ANSWER
    assert "[1]" in out


async def test_fake_answer_is_general_without_passages(fake_mode):
    out = await llm.chat([
        {"role": "system", "content": _SYSTEM_PROMPT.format(course="CS101 Testing")},
        {"role": "user", "content": "Course material passages:\n\n(No course materials are indexed for this "
                                    "course yet.)\n\nQuestion: what?"},
    ])
    assert out.startswith("This isn't covered in your course materials")
    assert "[" not in out


async def test_fake_rewrite_returns_latest_question(fake_mode):
    out = await llm.chat([
        {"role": "system", "content": _REWRITE_PROMPT},
        {"role": "user", "content": "Conversation:\nuser: hi\n\nLatest question: what about its drawbacks?"},
    ])
    assert out == "what about its drawbacks?"


async def test_fake_flag_off_still_needs_a_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FAKE", False)
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(llm, "_client", None)
    with pytest.raises(llm.LLMUnavailable):
        await llm.chat([{"role": "user", "content": "hi"}])


# ── through the API (what the Maestro flow relies on) ─────────────────────────

@pytest.mark.db
async def test_fake_mode_answer_through_api_has_citation(student_client, classroom, db_session, fake_mode,
                                                         fixed_query_embedding):
    mat = await _add_material(db_session, classroom["course_id"], "Black-box testing",
                              chunks=[("Boundary value analysis tests values at the edges.", 4, 6)])
    chat = await _new_chat(student_client, classroom["course_id"])

    resp = await student_client.post(f"/student/assistant/sessions/{chat['id']}/messages",
                                     json={"content": "What is boundary value analysis?"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == SOURCE_COURSE
    assert body["content"] == llm.FAKE_COURSE_ANSWER
    [cite] = body["citations"]
    assert cite["n"] == 1 and cite["material_id"] == mat.id
    assert cite["file_url"] == f"/student/assistant/materials/{mat.id}/file" and cite["open_page"] == 4

    saved = (await db_session.execute(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == chat["id"]))).scalar_one()
    assert saved == 2
    session = (await db_session.execute(select(ChatSession).where(ChatSession.id == chat["id"]))).scalar_one()
    assert session.title == "What is boundary value analysis?"


@pytest.mark.db
async def test_fake_mode_without_materials_is_general(student_client, classroom, fake_mode, fixed_query_embedding):
    chat = await _new_chat(student_client, classroom["course_id"])
    resp = await student_client.post(f"/student/assistant/sessions/{chat['id']}/messages",
                                     json={"content": "What is a compiler?"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["source_type"] == SOURCE_GENERAL
    assert resp.json()["citations"] == []


@pytest.mark.db
async def test_fake_mode_summary_and_study_tools_are_cited(student_client, classroom, db_session,
                                                           fake_mode, fixed_query_embedding):
    mat = await _add_material(db_session, classroom["course_id"], "Black-box testing",
                              chunks=[("Boundary value analysis tests values at the edges.", 4, 6)])

    # Study tools run inside a chat (the old /summaries and /study-tools endpoints were removed)
    url = f"/student/assistant/sessions/{(await _new_chat(student_client, classroom['course_id']))['id']}/tools"

    # summary (FR-810): the canned answer cites passage [1]
    resp = await student_client.post(url, json={"topic": "boundary value analysis", "kind": "summary"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == SOURCE_COURSE
    assert body["content"] == llm.FAKE_COURSE_ANSWER
    [cite] = body["citations"]
    assert cite["material_id"] == mat.id

    # flashcards (FR-811): the fake returns valid JSON, parsed into a real cited card
    resp = await student_client.post(url, json={"topic": "boundary value analysis", "kind": "flashcards"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kind"] == "flashcards" and body["source_type"] == "course"
    [card] = body["payload"]["cards"]
    assert card["front"] and card["back"] and card["citation"]["material_id"] == mat.id

    # practice questions: same, one question with four options
    resp = await student_client.post(url, json={"topic": "boundary value analysis",
                                                "kind": "practice_questions"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kind"] == "practice_questions" and body["source_type"] == "course"
    [q] = body["payload"]["questions"]
    assert q["stem"] and len(q["options"]) == 4 and q["answer"] == "branch"
    assert q["citation"]["material_id"] == mat.id


async def test_fake_topic_label_is_short_and_not_a_file_name(fake_mode):
    from app.services.kb.assistant import _TOPIC_LABEL_PROMPT
    out = await llm.chat([
        {"role": "system", "content": f"{_TOPIC_LABEL_PROMPT}\n\nExisting topics:\n(none yet)"},
        {"role": "user", "content": "what is boundary value analysis?"},
    ])
    assert out == "What is boundary value analysis"
