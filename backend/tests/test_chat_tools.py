"""Study tools inside the chat (FR-810, FR-811; redesign 2026-11-13).

A tool run is saved as two chat messages (the request and the result) so it shows in the
chat history; flashcards and practice keep their data in `payload`, and a practice set
remembers the student's last score. LLM mocked, embeddings faked.
"""
import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.ai_chat import ChatMessage
from app.models.knowledge import EMBEDDING_DIM
from app.services.kb import llm
from tests.conftest import _client

pytestmark = pytest.mark.db

VEC = [1.0] + [0.0] * (EMBEDDING_DIM - 1)

CARDS_JSON = ('{"cards": [{"front": "What is BVA?", "back": "Testing the edges of a range", "citation": 1}, '
              '{"front": "Why test edges?", "back": "Off-by-one errors hide there", "citation": 1}]}')
QUESTIONS_JSON = ('{"questions": [{"stem": "Which criterion is stronger?", '
                  '"options": ["statement", "branch", "neither", "both"], "answer": "branch", '
                  '"explanation": "Branch coverage subsumes statement coverage.", "citation": 1}]}')


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    async def embed_query(text):
        return VEC

    async def embed_passages(texts):
        return [VEC for _ in texts]

    monkeypatch.setattr("app.services.kb.search.embed_query", embed_query)
    monkeypatch.setattr("app.services.kb.ingest.embed_passages", embed_passages)


@pytest.fixture
def fake_llm(monkeypatch):
    """`.reply` answers the tool prompt (str or exception); topic labels get "Boundary value analysis"."""
    class FakeLLM:
        reply: str | Exception = CARDS_JSON

        async def chat(self, messages, **kw):
            if "Label the student's question" in messages[0]["content"]:
                return "Boundary value analysis"
            if isinstance(self.reply, Exception):
                raise self.reply
            return self.reply

    fake = FakeLLM()
    monkeypatch.setattr(llm, "chat", fake.chat)
    return fake


async def _new_chat(client, course_id):
    resp = await client.post("/student/assistant/sessions", json={"course_id": course_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _run(client, session_id, kind, topic="boundary value analysis"):
    return await client.post(f"/student/assistant/sessions/{session_id}/tools",
                             json={"kind": kind, "topic": topic})


async def test_flashcards_are_saved_in_the_chat(student_client, synthetic_kb, fake_llm):
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    resp = await _run(student_client, sid, "flashcards")
    assert resp.status_code == 200, resp.text
    reply = resp.json()
    assert reply["role"] == "assistant" and reply["kind"] == "flashcards"
    assert reply["source_type"] == "course" and reply["topic"] == "Boundary value analysis"
    cards = reply["payload"]["cards"]
    assert [c["front"] for c in cards] == ["What is BVA?", "Why test edges?"]
    assert reply["payload"]["topic"] == "boundary value analysis"
    # both cards cite the same passage, so the message lists that source once
    assert len(reply["citations"]) == 1 and reply["citations"][0]["n"] == 1
    # plain-text copy for follow-up questions
    assert "1. What is BVA? — Testing the edges of a range" in reply["content"]

    history = (await student_client.get(f"/student/assistant/sessions/{sid}/messages")).json()
    assert [(m["role"], m["kind"]) for m in history] == [("user", "flashcards"), ("assistant", "flashcards")]
    assert history[0]["content"] == "Flashcards: boundary value analysis"
    assert history[1]["payload"]["cards"] == cards
    session = (await student_client.get("/student/assistant/sessions")).json()[0]
    assert session["title"] == "Flashcards: boundary value analysis"


async def test_summary_is_saved_as_markdown_with_citations(student_client, synthetic_kb, fake_llm):
    fake_llm.reply = "## Boundary value analysis\n\n- Test the edges of each range [1]."
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    resp = await _run(student_client, sid, "study_guide")
    assert resp.status_code == 200, resp.text
    reply = resp.json()
    assert reply["kind"] == "study_guide" and reply["source_type"] == "course"
    assert reply["content"].startswith("## Boundary value analysis")
    assert reply["citations"][0]["material_id"] in synthetic_kb["material_ids"].values()


async def test_chat_messages_are_kind_chat(student_client, synthetic_kb, fake_llm):
    fake_llm.reply = "BVA tests the edges [1]."
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    resp = await student_client.post(f"/student/assistant/sessions/{sid}/messages", json={"content": "What is BVA?"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["kind"] == "chat" and resp.json()["payload"] is None


async def test_practice_score_is_remembered(student_client, synthetic_kb, fake_llm):
    fake_llm.reply = QUESTIONS_JSON
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    reply = (await _run(student_client, sid, "practice_questions", topic="coverage")).json()
    assert reply["kind"] == "practice_questions" and reply["payload"]["last_score"] is None
    assert len(reply["payload"]["questions"]) == 1

    resp = await student_client.patch(f"/student/assistant/messages/{reply['id']}/score",
                                      json={"correct": 1, "total": 1})
    assert resp.status_code == 200, resp.text
    assert resp.json()["payload"]["last_score"] == {"correct": 1, "total": 1}
    history = (await student_client.get(f"/student/assistant/sessions/{sid}/messages")).json()
    assert history[-1]["payload"]["last_score"] == {"correct": 1, "total": 1}
    assert history[-1]["payload"]["questions"] == reply["payload"]["questions"]  # questions kept

    bad = await student_client.patch(f"/student/assistant/messages/{reply['id']}/score",
                                     json={"correct": 2, "total": 1})
    assert bad.status_code == 422


async def test_score_only_for_own_practice_sets(student_client, synthetic_kb, classroom, fake_llm):
    fake_llm.reply = QUESTIONS_JSON
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    reply = (await _run(student_client, sid, "practice_questions")).json()

    other_user_id = classroom["student_user_ids"][1]
    async with _client(create_access_token(other_user_id, "student")) as other:
        resp = await other.patch(f"/student/assistant/messages/{reply['id']}/score",
                                 json={"correct": 0, "total": 1})
    assert resp.status_code == 404

    # and a flashcards message has no score
    fake_llm.reply = CARDS_JSON
    cards = (await _run(student_client, sid, "flashcards")).json()
    resp = await student_client.patch(f"/student/assistant/messages/{cards['id']}/score",
                                      json={"correct": 0, "total": 1})
    assert resp.status_code == 404


async def test_tools_only_in_own_chat(student_client, synthetic_kb, classroom, fake_llm):
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    other_user_id = classroom["student_user_ids"][1]
    async with _client(create_access_token(other_user_id, "student")) as other:
        resp = await _run(other, sid, "flashcards")
    assert resp.status_code == 404


async def test_failed_generation_saves_nothing(student_client, synthetic_kb, fake_llm, db_session):
    fake_llm.reply = "not json at all"
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    resp = await _run(student_client, sid, "flashcards")
    assert resp.status_code == 502
    count = (await db_session.execute(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == sid))).scalar_one()
    assert count == 0

    fake_llm.reply = llm.LLMUnavailable("down")
    resp = await _run(student_client, sid, "summary")
    assert resp.status_code == 503


async def test_empty_topic_is_rejected(student_client, synthetic_kb, fake_llm):
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    resp = await _run(student_client, sid, "flashcards", topic="")
    assert resp.status_code == 422
