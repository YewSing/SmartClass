"""T85: summary / study guide endpoint (FR-810) — LLM mocked, embeddings faked."""
import pytest

from app.models.knowledge import EMBEDDING_DIM
from app.services.kb import llm
from app.services.kb.assistant import SOURCE_COURSE, SOURCE_GENERAL

pytestmark = pytest.mark.db

VEC = [1.0] + [0.0] * (EMBEDDING_DIM - 1)


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
        answer = "## Summary\n\nBoundary value analysis tests values at the edges of a range [1]."

        async def chat(self, messages, **kw):
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

    fake = FakeLLM()
    monkeypatch.setattr(llm, "chat", fake.chat)
    return fake


async def _summary(student_client, synthetic_kb, **body):
    resp = await student_client.post("/student/assistant/summaries",
                                     json={"course_id": synthetic_kb["course_id"], **body})
    return resp


async def test_summary_of_material_is_cited(student_client, synthetic_kb, fake_llm):
    resp = await _summary(student_client, synthetic_kb,
                          material_id=synthetic_kb["material_ids"]["boundary-value-analysis"],
                          kind="summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == SOURCE_COURSE
    assert body["citations"] and body["citations"][0]["n"] == 1
    assert body["citations"][0]["material_id"] == synthetic_kb["material_ids"]["boundary-value-analysis"]
    assert "Summary" in body["content"] and body["kind"] == "summary"


async def test_study_guide_for_topic_is_cited(student_client, synthetic_kb, fake_llm):
    resp = await _summary(student_client, synthetic_kb, topic="equivalence partitioning",
                          kind="study_guide")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == SOURCE_COURSE and body["citations"]


async def test_topic_not_in_materials_is_general(student_client, synthetic_kb, fake_llm):
    fake_llm.answer = ("This isn't covered in your course materials, so here's a general "
                       "explanation: quantum entanglement links particles over distance.")
    resp = await _summary(student_client, synthetic_kb, topic="quantum entanglement",
                          kind="study_guide")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == SOURCE_GENERAL and body["citations"] == []


async def test_summary_validation(student_client, synthetic_kb, fake_llm):
    url = "/student/assistant/summaries"
    cid = synthetic_kb["course_id"]
    # neither material_id nor topic
    assert (await student_client.post(url, json={"course_id": cid})).status_code == 422
    # both
    assert (await student_client.post(url, json={
        "course_id": cid, "material_id": 1, "topic": "x"})).status_code == 422
    # bad kind
    assert (await student_client.post(url, json={
        "course_id": cid, "topic": "x", "kind": "essay"})).status_code == 422
    # unknown material -> 404
    assert (await student_client.post(url, json={
        "course_id": cid, "material_id": 999999})).status_code == 404


async def test_summary_is_student_only(lecturer_client, admin_client, synthetic_kb):
    body = {"course_id": synthetic_kb["course_id"], "topic": "boundary value analysis"}
    assert (await lecturer_client.post("/student/assistant/summaries", json=body)).status_code == 403
    assert (await admin_client.post("/student/assistant/summaries", json=body)).status_code == 403


async def test_summary_not_enrolled_is_403(student_client, classroom, db_session):
    from app.models.class_ import Course

    other = Course(code="CS999", name="Not enrolled")
    db_session.add(other)
    await db_session.flush()
    resp = await student_client.post("/student/assistant/summaries",
                                     json={"course_id": other.id, "topic": "x"})
    assert resp.status_code == 403


async def test_summary_llm_down_is_503(student_client, synthetic_kb, fake_llm):
    fake_llm.answer = llm.LLMUnavailable("AI provider error: Timeout")
    resp = await _summary(student_client, synthetic_kb, topic="boundary value analysis")
    assert resp.status_code == 503
