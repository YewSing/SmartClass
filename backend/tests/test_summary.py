"""T85: summary / study guide (FR-810), run through the chat tools endpoint
(`POST /student/assistant/sessions/{id}/tools`; the old `/student/assistant/summaries` was removed
on 2026-11-13). LLM mocked, embeddings faked."""
import pytest

from app.models.ai_chat import ChatSession
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
            if "Label the student's question" in messages[0]["content"]:
                return "Boundary value analysis"
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

    fake = FakeLLM()
    monkeypatch.setattr(llm, "chat", fake.chat)
    return fake


async def _new_chat(client, course_id):
    resp = await client.post("/student/assistant/sessions", json={"course_id": course_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _summary(student_client, synthetic_kb, topic, kind="summary"):
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    return await student_client.post(f"/student/assistant/sessions/{sid}/tools",
                                     json={"kind": kind, "topic": topic})


async def test_summary_for_topic_is_cited(student_client, synthetic_kb, fake_llm):
    resp = await _summary(student_client, synthetic_kb, "boundary value analysis")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == SOURCE_COURSE and body["kind"] == "summary"
    assert body["citations"] and body["citations"][0]["n"] == 1
    assert body["citations"][0]["material_id"] in synthetic_kb["material_ids"].values()
    assert "Summary" in body["content"]


async def test_study_guide_for_topic_is_cited(student_client, synthetic_kb, fake_llm):
    resp = await _summary(student_client, synthetic_kb, "equivalence partitioning", kind="study_guide")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == SOURCE_COURSE and body["citations"]


async def test_topic_not_in_materials_is_general(student_client, synthetic_kb, fake_llm):
    fake_llm.answer = ("This isn't covered in your course materials, so here's a general "
                       "explanation: quantum entanglement links particles over distance.")
    resp = await _summary(student_client, synthetic_kb, "quantum entanglement", kind="study_guide")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == SOURCE_GENERAL and body["citations"] == []


async def test_summary_validation(student_client, synthetic_kb, fake_llm):
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    url = f"/student/assistant/sessions/{sid}/tools"
    assert (await student_client.post(url, json={"topic": "x", "kind": "essay"})).status_code == 422
    assert (await student_client.post(url, json={"kind": "summary"})).status_code == 422
    assert (await student_client.post(url, json={"topic": "x" * 201, "kind": "summary"})).status_code == 422


async def test_summary_is_student_only(student_client, lecturer_client, admin_client, synthetic_kb):
    sid = await _new_chat(student_client, synthetic_kb["course_id"])
    body = {"topic": "boundary value analysis", "kind": "summary"}
    url = f"/student/assistant/sessions/{sid}/tools"
    assert (await lecturer_client.post(url, json=body)).status_code == 403
    assert (await admin_client.post(url, json=body)).status_code == 403


async def test_summary_not_enrolled_is_403(student_client, users, db_session, fake_llm):
    """A chat whose course the student is no longer enrolled in can't run tools."""
    from sqlalchemy import select

    from app.models.class_ import Course
    from app.models.user import Student

    other = Course(code="CS999", name="Not enrolled")
    db_session.add(other)
    await db_session.flush()
    student_id = await db_session.scalar(select(Student.id).where(Student.user_id == users["student"].id))
    chat = ChatSession(student_id=student_id, course_id=other.id, title="old chat")
    db_session.add(chat)
    await db_session.commit()
    resp = await student_client.post(f"/student/assistant/sessions/{chat.id}/tools",
                                     json={"topic": "x", "kind": "summary"})
    assert resp.status_code == 403


async def test_summary_llm_down_is_503(student_client, synthetic_kb, fake_llm):
    fake_llm.answer = llm.LLMUnavailable("AI provider error: Timeout")
    resp = await _summary(student_client, synthetic_kb, "boundary value analysis")
    assert resp.status_code == 503
