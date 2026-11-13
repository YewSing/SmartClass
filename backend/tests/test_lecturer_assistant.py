"""T100: a lecturer asks their own materials (FR-815) — LLM mocked, embeddings faked.

Mirrors the student chat endpoints under /lecturer/assistant/…, owned by `lecturer_id`,
using the same `answer_question` code (same citations and labels). A lecturer's own chat
is private to them and is never counted in the question trends (FR-813).
"""
import pytest
from sqlalchemy import select

from app.models.ai_chat import ChatMessage, ChatSession
from app.models.knowledge import EMBEDDING_DIM
from app.services.kb import llm
from app.services.kb.assistant import SOURCE_COURSE, SOURCE_GENERAL
from tests.test_assistant_open_source import PDF, _moodle_material  # noqa: F401
from tests.test_assistant_open_source import fake_moodle  # noqa: F401, F811  (shared fixture)

pytestmark = pytest.mark.db

VEC = [1.0] + [0.0] * (EMBEDDING_DIM - 1)

COURSE_ANSWER = "Boundary value analysis tests the edges of a range [1]."
GENERAL_ANSWER = ("This isn't covered in your course materials, so here's a general "
                  "explanation: quantum entanglement links particles over distance.")


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
        answer = COURSE_ANSWER

        async def chat(self, messages, **kw):
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

    fake = FakeLLM()
    monkeypatch.setattr(llm, "chat", fake.chat)
    return fake


async def _new_chat(lecturer_client, course_id):
    resp = await lecturer_client.post("/lecturer/assistant/sessions", json={"course_id": course_id})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_lecturer_creates_lists_renames_deletes(lecturer_client, synthetic_kb):
    chat = await _new_chat(lecturer_client, synthetic_kb["course_id"])
    assert chat["course_id"] == synthetic_kb["course_id"]

    sessions = (await lecturer_client.get("/lecturer/assistant/sessions")).json()
    assert [s["id"] for s in sessions] == [chat["id"]]

    renamed = await lecturer_client.patch(f"/lecturer/assistant/sessions/{chat['id']}",
                                          json={"title": "My review"})
    assert renamed.status_code == 200 and renamed.json()["title"] == "My review"

    assert (await lecturer_client.delete(f"/lecturer/assistant/sessions/{chat['id']}")).status_code == 204
    assert (await lecturer_client.get("/lecturer/assistant/sessions")).json() == []


async def test_lecturer_asks_and_gets_the_same_cited_answer(lecturer_client, synthetic_kb, fake_llm, db_session):
    chat = await _new_chat(lecturer_client, synthetic_kb["course_id"])
    resp = await lecturer_client.post(f"/lecturer/assistant/sessions/{chat['id']}/messages",
                                      json={"content": "What is BVA?"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "assistant" and body["source_type"] == SOURCE_COURSE
    assert body["citations"] and body["citations"][0]["material_id"] in synthetic_kb["material_ids"].values()

    # the session row is owned by the lecturer (student_id is NULL)
    session = (await db_session.execute(select(ChatSession).where(ChatSession.id == chat["id"]))).scalar_one()
    assert session.lecturer_id == synthetic_kb["lecturer_id"] and session.student_id is None


async def test_lecturer_general_answer_is_labelled(lecturer_client, synthetic_kb, fake_llm):
    fake_llm.answer = GENERAL_ANSWER
    chat = await _new_chat(lecturer_client, synthetic_kb["course_id"])
    resp = await lecturer_client.post(f"/lecturer/assistant/sessions/{chat['id']}/messages",
                                      json={"content": "What is quantum entanglement?"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["source_type"] == SOURCE_GENERAL and resp.json()["citations"] == []


async def test_other_lecturer_gets_403(other_lecturer_client, synthetic_kb):
    assert (await other_lecturer_client.get("/lecturer/assistant/courses")).status_code == 200
    assert (await other_lecturer_client.post(
        "/lecturer/assistant/sessions",
        json={"course_id": synthetic_kb["course_id"]})).status_code == 403  # doesn't teach CS101
    # their courses list must not include CS101
    courses = (await other_lecturer_client.get("/lecturer/assistant/courses")).json()
    assert synthetic_kb["course_id"] not in [c["course_id"] for c in courses]


async def test_student_and_admin_get_403(student_client, admin_client, synthetic_kb, classroom):
    url = "/lecturer/assistant/sessions"
    body = {"course_id": synthetic_kb["course_id"]}
    assert (await student_client.post(url, json=body)).status_code == 403
    assert (await admin_client.post(url, json=body)).status_code == 403


async def test_lecturer_cannot_use_student_chat(lecturer_client, student_client, synthetic_kb):
    # a lecturer cannot read/answer a student's chat through the lecturer endpoints
    chat = (await student_client.post("/student/assistant/sessions",
                                      json={"course_id": synthetic_kb["course_id"]})).json()
    assert (await lecturer_client.get(
        f"/lecturer/assistant/sessions/{chat['id']}/messages")).status_code == 404


async def test_lecturer_chat_is_not_counted_in_trends(classroom, lecturer_client, db_session):
    """A lecturer's own questions never show up in the lecturer trends (FR-815)."""
    course_id = classroom["course_id"]
    # one lecturer chat + one student chat, both on the same topic
    for session_id, student_id, lecturer_id in [
        (None, classroom["student_ids"][0], None),
        (None, classroom["student_ids"][1], None),
        (None, None, classroom["lecturer_id"]),
    ]:
        s = ChatSession(student_id=student_id, lecturer_id=lecturer_id, course_id=course_id)
        db_session.add(s)
        await db_session.flush()
        db_session.add(ChatMessage(session_id=s.id, role="user", content="some question"))
        db_session.add(ChatMessage(session_id=s.id, role="assistant", content="answer",
                                   source_type="course", topic="Boundary value analysis",
                                   citations=[{"material_id": 1, "title": "Boundary value analysis"}]))
    await db_session.commit()

    body = (await lecturer_client.get(f"/lecturer/assistant/trends/{course_id}")).json()
    # only 2 distinct students asked → below the 3-student minimum, and the lecturer
    # (student_id NULL) never contributes. Nothing appears.
    assert body["most_asked_topics"] == []
    assert body["most_cited_materials"] == []


async def test_lecturer_llm_down_is_503(lecturer_client, synthetic_kb, fake_llm):
    fake_llm.answer = llm.LLMUnavailable("AI provider error: Timeout")
    chat = await _new_chat(lecturer_client, synthetic_kb["course_id"])
    resp = await lecturer_client.post(f"/lecturer/assistant/sessions/{chat['id']}/messages",
                                      json={"content": "What is BVA?"})
    assert resp.status_code == 503


async def test_lecturer_can_open_a_cited_source(lecturer_client, other_lecturer_client,
                                                student_client, classroom, db_session, fake_moodle):  # noqa: F811
    mat = await _moodle_material(db_session, classroom["course_id"])
    fake_moodle.data = {mat.file_url: PDF}
    url = f"/lecturer/assistant/materials/{mat.id}/file"
    resp = await lecturer_client.get(url)
    assert resp.status_code == 200, resp.text
    assert resp.content == PDF
    # other lecturer (doesn't teach CS101) and students are refused
    assert (await other_lecturer_client.get(url)).status_code == 403
    assert (await student_client.get(url)).status_code == 403


async def test_a_new_chat_is_listed_first(lecturer_client, synthetic_kb, fake_llm):
    # "New chat" makes an empty chat at once, and coming back reopens the latest chat, so the new
    # empty chat must be listed first.
    course_id = synthetic_kb["course_id"]
    old = (await lecturer_client.post("/lecturer/assistant/sessions", json={"course_id": course_id})).json()
    await lecturer_client.post(f"/lecturer/assistant/sessions/{old['id']}/messages", json={"content": "What is BVA?"})
    new = (await lecturer_client.post("/lecturer/assistant/sessions", json={"course_id": course_id})).json()
    listed = (await lecturer_client.get(f"/lecturer/assistant/sessions?course_id={course_id}")).json()
    assert [s["id"] for s in listed] == [new["id"], old["id"]]


async def test_the_answer_prompt_knows_the_asker_is_the_lecturer(lecturer_client, student_client, synthetic_kb,
                                                                 monkeypatch):
    # Found in the 2026-11-14 check: asked "is my materials up to date", the assistant told the
    # lecturer to "ask your lecturer". A lecturer's chat now says who is asking; a student's doesn't.
    systems = []

    async def chat(messages, **kw):
        if "Label the student's question" not in messages[0]["content"]:
            systems.append(messages[0]["content"])
        return COURSE_ANSWER

    monkeypatch.setattr(llm, "chat", chat)
    chat_l = await _new_chat(lecturer_client, synthetic_kb["course_id"])
    resp = await lecturer_client.post(f"/lecturer/assistant/sessions/{chat_l['id']}/messages",
                                      json={"content": "Are my materials up to date?"})
    assert resp.status_code == 200, resp.text
    assert "The person asking is the lecturer who teaches" in systems[-1]
    assert "{course_code}" not in systems[-1]

    resp = await student_client.post("/student/assistant/sessions", json={"course_id": synthetic_kb["course_id"]})
    sid = resp.json()["id"]
    resp = await student_client.post(f"/student/assistant/sessions/{sid}/messages", json={"content": "What is BVA?"})
    assert resp.status_code == 200, resp.text
    assert "lecturer who teaches" not in systems[-1]
