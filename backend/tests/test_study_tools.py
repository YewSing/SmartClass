"""T86: flashcards / practice questions endpoint (FR-811) — LLM mocked, embeddings faked."""
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
    class FakeLLM:
        responses = [CARDS_JSON]
        calls = 0

        async def chat(self, messages, **kw):
            self.calls += 1
            resp = self.responses.pop(0) if self.responses else (self.responses[-1] if self.responses else "")
            if isinstance(resp, Exception):
                raise resp
            return resp

    fake = FakeLLM()
    monkeypatch.setattr(llm, "chat", fake.chat)
    return fake


async def _tools(student_client, synthetic_kb, **body):
    resp = await student_client.post("/student/assistant/study-tools",
                                     json={"course_id": synthetic_kb["course_id"], **body})
    return resp


async def test_flashcards_for_material(student_client, synthetic_kb, fake_llm):
    resp = await _tools(student_client, synthetic_kb,
                        material_id=synthetic_kb["material_ids"]["boundary-value-analysis"],
                        kind="flashcards")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == "course" and body["kind"] == "flashcards"
    [card] = body["cards"]
    assert card["front"] == "What is BVA?" and card["back"] == "Testing values at the edges of a range"
    assert card["citation"]["material_id"] == synthetic_kb["material_ids"]["boundary-value-analysis"]
    assert body["questions"] == []


async def test_practice_questions_for_topic(student_client, synthetic_kb, fake_llm):
    fake_llm.responses = [QUESTIONS_JSON]
    resp = await _tools(student_client, synthetic_kb, topic="coverage", kind="practice_questions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == "course" and body["kind"] == "practice_questions"
    [q] = body["questions"]
    assert q["stem"] and len(q["options"]) == 4 and q["answer"] == "branch"
    assert q["citation"]["material_id"] in synthetic_kb["material_ids"].values()
    assert body["cards"] == []


async def test_malformed_json_is_retried_once_then_502(student_client, synthetic_kb, fake_llm):
    fake_llm.responses = ["not json at all", "still not json"]
    resp = await _tools(student_client, synthetic_kb, topic="bva", kind="flashcards")
    assert resp.status_code == 503
    assert "malformed" in resp.json()["detail"].lower()
    assert fake_llm.calls == 2  # one retry, no more


async def test_malformed_json_retry_recovers(student_client, synthetic_kb, fake_llm):
    fake_llm.responses = ["oops", CARDS_JSON]
    resp = await _tools(student_client, synthetic_kb, topic="bva", kind="flashcards")
    assert resp.status_code == 200, resp.text
    assert fake_llm.calls == 2
    assert resp.json()["cards"]


async def test_topic_not_in_materials_is_general(student_client, synthetic_kb, fake_llm):
    fake_llm.responses = ['{"cards": []}']
    resp = await _tools(student_client, synthetic_kb, topic="quantum entanglement", kind="flashcards")
    assert resp.status_code == 200, resp.text
    assert resp.json()["source_type"] == "general" and resp.json()["cards"] == []


async def test_study_tools_validation(student_client, synthetic_kb, fake_llm):
    url = "/student/assistant/study-tools"
    cid = synthetic_kb["course_id"]
    assert (await student_client.post(url, json={"course_id": cid})).status_code == 422
    assert (await student_client.post(url, json={
        "course_id": cid, "material_id": 1, "topic": "x", "kind": "flashcards"})).status_code == 422
    assert (await student_client.post(url, json={
        "course_id": cid, "topic": "x", "kind": "quiz"})).status_code == 422
    assert (await student_client.post(url, json={
        "course_id": cid, "material_id": 999999, "kind": "flashcards"})).status_code == 404


async def test_study_tools_student_only(lecturer_client, admin_client, synthetic_kb):
    body = {"course_id": synthetic_kb["course_id"], "topic": "bva", "kind": "flashcards"}
    assert (await lecturer_client.post("/student/assistant/study-tools", json=body)).status_code == 403
    assert (await admin_client.post("/student/assistant/study-tools", json=body)).status_code == 403


async def test_study_tools_llm_down_is_503(student_client, synthetic_kb, fake_llm):
    fake_llm.responses = [llm.LLMUnavailable("AI provider error: Timeout")]
    resp = await _tools(student_client, synthetic_kb, topic="bva", kind="flashcards")
    assert resp.status_code == 503
