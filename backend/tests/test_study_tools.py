"""T86: flashcards / practice questions (FR-811), run through the chat tools endpoint
(`POST /student/assistant/sessions/{id}/tools`; the old `/student/assistant/study-tools` was removed
on 2026-11-13). LLM mocked, embeddings faked."""
import pytest

from app.models.knowledge import EMBEDDING_DIM
from app.services.kb import llm

pytestmark = pytest.mark.db

VEC = [1.0] + [0.0] * (EMBEDDING_DIM - 1)

CARDS_JSON = ('{"cards": [{"front": "What is BVA?", "back": "Testing values at the edges of a range", '
              '"citation": 1}]}')
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
    """`responses` answer the study-tool prompt in order; `calls` counts only those (not topic labels)."""
    class FakeLLM:
        responses = [CARDS_JSON]
        calls = 0

        async def chat(self, messages, **kw):
            if "Label the student's question" in messages[0]["content"]:
                return "Boundary value analysis"
            self.calls += 1
            resp = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
            if isinstance(resp, Exception):
                raise resp
            return resp

    fake = FakeLLM()
    monkeypatch.setattr(llm, "chat", fake.chat)
    return fake


async def _tools(student_client, synthetic_kb, topic, kind):
    resp = await student_client.post("/student/assistant/sessions",
                                     json={"course_id": synthetic_kb["course_id"]})
    assert resp.status_code == 201, resp.text
    return await student_client.post(f"/student/assistant/sessions/{resp.json()['id']}/tools",
                                     json={"kind": kind, "topic": topic})


async def test_flashcards_for_topic(student_client, synthetic_kb, fake_llm):
    resp = await _tools(student_client, synthetic_kb, "boundary value analysis", "flashcards")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == "course" and body["kind"] == "flashcards"
    [card] = body["payload"]["cards"]
    assert card["front"] == "What is BVA?" and card["back"] == "Testing values at the edges of a range"
    assert card["citation"]["material_id"] in synthetic_kb["material_ids"].values()
    assert "questions" not in body["payload"]


async def test_practice_questions_for_topic(student_client, synthetic_kb, fake_llm):
    fake_llm.responses = [QUESTIONS_JSON]
    resp = await _tools(student_client, synthetic_kb, "coverage", "practice_questions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == "course" and body["kind"] == "practice_questions"
    [q] = body["payload"]["questions"]
    assert q["stem"] and len(q["options"]) == 4 and q["answer"] == "branch"
    assert q["citation"]["material_id"] in synthetic_kb["material_ids"].values()
    assert "cards" not in body["payload"]


async def test_malformed_json_is_retried_once_then_502(student_client, synthetic_kb, fake_llm):
    fake_llm.responses = ["not json at all", "still not json"]
    resp = await _tools(student_client, synthetic_kb, "bva", "flashcards")
    assert resp.status_code == 502  # spec (T86): malformed after one retry -> 502, not 503
    assert "malformed" in resp.json()["detail"].lower()
    assert fake_llm.calls == 2  # one retry, no more


async def test_malformed_json_retry_recovers(student_client, synthetic_kb, fake_llm):
    fake_llm.responses = ["oops", CARDS_JSON]
    resp = await _tools(student_client, synthetic_kb, "bva", "flashcards")
    assert resp.status_code == 200, resp.text
    assert fake_llm.calls == 2
    assert resp.json()["payload"]["cards"]


async def test_topic_not_in_materials_is_general(student_client, synthetic_kb, fake_llm):
    fake_llm.responses = ['{"cards": []}']
    resp = await _tools(student_client, synthetic_kb, "quantum entanglement", "flashcards")
    assert resp.status_code == 200, resp.text
    assert resp.json()["source_type"] == "general" and resp.json()["payload"]["cards"] == []
