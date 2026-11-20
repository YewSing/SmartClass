"""T101: "before next class" summary for a lecturer (FR-816, NFR-09) — LLM mocked.

The summary is built only from the anonymised question trends (topics asked by ≥3 distinct
students). The LLM prompt must never carry names, chat text, or a topic below that minimum;
with no data above the minimum there is no LLM call at all.
"""
import pytest

from app.models.ai_chat import ChatMessage, ChatSession
from app.models.knowledge import EMBEDDING_DIM
from app.services.kb import llm
from app.services.kb.before_class import _sections_for_materials, reset_cache

pytestmark = pytest.mark.db

VEC = [1.0] + [0.0] * (EMBEDDING_DIM - 1)

SUMMARY_ANSWER = (
    "## Revisit\n\nBoundary value analysis is covered in the notes [1].\n\n"
    "## Not covered by the materials\n\nQuantum entanglement."
)


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    async def embed_query(text):
        return VEC

    async def embed_passages(texts):
        return [VEC for _ in texts]

    monkeypatch.setattr("app.services.kb.search.embed_query", embed_query)
    monkeypatch.setattr("app.services.kb.ingest.embed_passages", embed_passages)


@pytest.fixture(autouse=True)
def _fresh_cache():
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def fake_llm(monkeypatch):
    class FakeLLM:
        answer = SUMMARY_ANSWER
        calls = 0
        last_messages = None

        async def chat(self, messages, **kw):
            self.calls += 1
            self.last_messages = messages
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

    fake = FakeLLM()
    monkeypatch.setattr(llm, "chat", fake.chat)
    return fake


async def _seed_question(db, course_id, student_id, *, topic, source="course",
                         citations=None, content="some private question"):
    session = ChatSession(student_id=student_id, course_id=course_id)
    db.add(session)
    await db.flush()
    db.add(ChatMessage(session_id=session.id, role="user", content=content))
    db.add(ChatMessage(session_id=session.id, role="assistant", content="answer",
                       source_type=source, topic=topic, citations=citations))
    await db.commit()


def _url(course_id):
    return f"/lecturer/assistant/before-class/{course_id}"


async def test_not_enough_data_returns_message_without_llm(lecturer_client, synthetic_kb, fake_llm):
    resp = await lecturer_client.get(_url(synthetic_kb["course_id"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["not_enough_data"] is True
    assert "not enough" in body["content"].lower()
    assert body["citations"] == []
    assert fake_llm.calls == 0  # no LLM call


async def test_summary_cites_real_sections_and_prompt_is_anonymised(
    lecturer_client, classroom, synthetic_kb, fake_llm, db_session
):
    course_id = classroom["course_id"]
    mat_id = synthetic_kb["material_ids"]["boundary-value-analysis"]
    title = "Boundary Value Analysis"
    for sid in classroom["student_ids"]:
        await _seed_question(
            db_session, course_id, sid, topic=title,
            citations=[{"material_id": mat_id, "title": title}],
            content="SECRET-QUESTION-TEXT from Alice Wondering",
        )
    # a topic below the 3-student minimum must never reach the prompt
    for sid in classroom["student_ids"][:2]:
        await _seed_question(db_session, course_id, sid, topic="rare topic",
                             citations=[{"material_id": mat_id, "title": "rare topic"}])

    resp = await lecturer_client.get(_url(course_id))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["not_enough_data"] is False
    assert body["citations"], "summary must cite at least one real section"
    real_ids = set(synthetic_kb["material_ids"].values())
    assert {c["material_id"] for c in body["citations"]} <= real_ids

    prompt = "\n".join(m["content"] for m in fake_llm.last_messages)
    assert "Boundary Value Analysis" in prompt       # the ≥3-student topic is present
    assert "rare topic" not in prompt                # below the minimum → hidden
    assert "SECRET-QUESTION-TEXT" not in prompt      # no question text
    assert "Alice" not in prompt                     # no student name


async def test_result_is_cached_until_the_trends_change(
    lecturer_client, classroom, synthetic_kb, fake_llm, db_session
):
    course_id = classroom["course_id"]
    mat_id = synthetic_kb["material_ids"]["boundary-value-analysis"]
    for sid in classroom["student_ids"]:
        await _seed_question(db_session, course_id, sid, topic="Boundary Value Analysis",
                             citations=[{"material_id": mat_id, "title": "Boundary Value Analysis"}])

    r1 = await lecturer_client.get(_url(course_id))
    assert fake_llm.calls == 1
    r2 = await lecturer_client.get(_url(course_id))
    assert fake_llm.calls == 1                  # cached: no second LLM call
    assert r1.json()["content"] == r2.json()["content"]

    # a new topic reaching 3 students changes the aggregates → regenerate
    for sid in classroom["student_ids"]:
        await _seed_question(db_session, course_id, sid, topic="Equivalence Partitioning",
                             citations=[{"material_id": mat_id, "title": "Equivalence Partitioning"}])
    r3 = await lecturer_client.get(_url(course_id))
    assert r3.status_code == 200, r3.text
    assert fake_llm.calls == 2


async def test_sections_for_materials_skips_deleted(synthetic_kb, db_session):
    real = synthetic_kb["material_ids"]["boundary-value-analysis"]
    sections = await _sections_for_materials(db_session, [real, 999999])
    ids = [s.material_id for s in sections]
    assert real in ids and 999999 not in ids


async def test_before_class_access_control(classroom, lecturer_client, other_lecturer_client,
                                           admin_client, student_client):
    url = _url(classroom["course_id"])
    assert (await other_lecturer_client.get(url)).status_code == 403   # doesn't teach CS101
    assert (await student_client.get(url)).status_code == 403
    assert (await admin_client.get(url)).status_code == 200            # admin fallback
    assert (await lecturer_client.get(url)).status_code == 200
    assert (await lecturer_client.get(_url(999999))).status_code == 404


async def test_before_class_llm_down_is_503(lecturer_client, classroom, synthetic_kb,
                                            fake_llm, db_session):
    course_id = classroom["course_id"]
    mat_id = synthetic_kb["material_ids"]["boundary-value-analysis"]
    for sid in classroom["student_ids"]:
        await _seed_question(db_session, course_id, sid, topic="Boundary Value Analysis",
                             citations=[{"material_id": mat_id, "title": "Boundary Value Analysis"}])
    fake_llm.answer = llm.LLMUnavailable("AI provider error: Timeout")
    resp = await lecturer_client.get(_url(course_id))
    assert resp.status_code == 503
