"""T87: anonymised question trends for lecturers (FR-813, NFR-09)."""
import pytest
from sqlalchemy import select

from app.models.ai_chat import ChatMessage, ChatSession
from app.models.knowledge import EMBEDDING_DIM
from app.services.kb import llm
from app.services.kb.assistant import SOURCE_GENERAL

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
        answer = "Boundary value analysis tests the edges [1]."

        async def chat(self, messages, **kw):
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

    fake = FakeLLM()
    monkeypatch.setattr(llm, "chat", fake.chat)
    return fake


async def _new_chat(student_client, course_id):
    resp = await student_client.post("/student/assistant/sessions", json={"course_id": course_id})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _seed_answer(db, course_id, student_id, *, topic, source="course",
                       citations=None, content="answer text"):
    """One student asking one question, with the assistant's answer tagged with `topic`."""
    session = ChatSession(student_id=student_id, course_id=course_id)
    db.add(session)
    await db.flush()
    db.add(ChatMessage(session_id=session.id, role="user", content="some question"))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=content,
                       source_type=source, topic=topic, citations=citations))
    await db.commit()


# ── topic tagging at answer time ──────────────────────────────────────────────

async def test_course_answer_is_tagged_with_the_cited_material(student_client, synthetic_kb,
                                                               fake_llm, db_session):
    chat = await _new_chat(student_client, synthetic_kb["course_id"])
    resp = await student_client.post(f"/student/assistant/sessions/{chat['id']}/messages",
                                     json={"content": "What is BVA?"})
    assert resp.status_code == 200, resp.text
    msg = (await db_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant"))).scalar_one()
    assert msg.source_type == "course" and msg.topic in {
        "Boundary Value Analysis", "Equivalence Partitioning", "Statement and Branch Coverage",
    }


async def test_general_answer_is_tagged_with_a_label(student_client, synthetic_kb,
                                                     fake_llm, db_session):
    fake_llm.answer = "This isn't covered in your course materials."
    chat = await _new_chat(student_client, synthetic_kb["course_id"])
    resp = await student_client.post(f"/student/assistant/sessions/{chat['id']}/messages",
                                     json={"content": "What is quantum entanglement?"})
    assert resp.status_code == 200, resp.text
    msg = (await db_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant"))).scalar_one()
    assert msg.source_type == SOURCE_GENERAL and msg.topic is not None


# ── the trends endpoint ───────────────────────────────────────────────────────

async def test_topics_below_three_students_are_hidden(classroom, lecturer_client, db_session):
    course_id = classroom["course_id"]
    ids = classroom["student_ids"]  # 3 enrolled students
    for sid in ids:
        await _seed_answer(db_session, course_id, sid, topic="Boundary value analysis",
                           citations=[{"material_id": 1, "title": "Boundary value analysis"}])
    for sid in ids[:2]:
        await _seed_answer(db_session, course_id, sid, topic="rare topic",
                           citations=[{"material_id": 1, "title": "rare topic"}])

    body = (await lecturer_client.get(f"/lecturer/assistant/trends/{course_id}")).json()
    topics = [t["topic"] for t in body["most_asked_topics"]]
    assert "Boundary value analysis" in topics
    assert "rare topic" not in topics          # 2 students < 3 → hidden
    assert body["most_asked_topics"][0]["students"] == 3


async def test_most_cited_materials(classroom, lecturer_client, db_session):
    course_id = classroom["course_id"]
    ids = classroom["student_ids"]
    for sid in ids:
        await _seed_answer(db_session, course_id, sid, topic="Lecture 4 slides",
                           citations=[{"material_id": 7, "title": "Lecture 4 slides"},
                                      {"material_id": 9, "title": "Lecture 9 slides"}])

    body = (await lecturer_client.get(f"/lecturer/assistant/trends/{course_id}")).json()
    materials = {m["title"]: m for m in body["most_cited_materials"]}
    assert set(materials) == {"Lecture 4 slides", "Lecture 9 slides"}
    assert materials["Lecture 4 slides"]["material_id"] == 7
    assert materials["Lecture 4 slides"]["students"] == 3


async def test_uncovered_topics_are_general_and_filtered(classroom, lecturer_client, db_session):
    course_id = classroom["course_id"]
    ids = classroom["student_ids"]
    for sid in ids:
        await _seed_answer(db_session, course_id, sid, topic="quantum entanglement",
                           source="general")
    for sid in ids[:2]:
        await _seed_answer(db_session, course_id, sid, topic="chess rules", source="general")

    body = (await lecturer_client.get(f"/lecturer/assistant/trends/{course_id}")).json()
    uncovered = [t["topic"] for t in body["topics_materials_dont_cover"]]
    assert uncovered == ["quantum entanglement"]
    assert body["most_asked_topics"] == [] and body["most_cited_materials"] == []


async def test_trends_never_expose_names_or_question_text(classroom, lecturer_client, db_session):
    course_id = classroom["course_id"]
    for sid in classroom["student_ids"]:
        await _seed_answer(db_session, course_id, sid, topic="Boundary value analysis",
                           content="A very private question about BVA",
                           citations=[{"material_id": 1, "title": "Boundary value analysis"}])

    raw = (await lecturer_client.get(f"/lecturer/assistant/trends/{course_id}")).text
    assert "private question" not in raw           # no question text
    assert "Student " not in raw and "Test Student" not in raw  # no names


async def test_trends_access_control(classroom, lecturer_client, other_lecturer_client,
                                     admin_client, student_client, db_session):
    course_id = classroom["course_id"]
    url = f"/lecturer/assistant/trends/{course_id}"
    assert (await other_lecturer_client.get(url)).status_code == 403   # doesn't teach CS101
    assert (await student_client.get(url)).status_code == 403
    assert (await admin_client.get(url)).status_code == 200            # admin fallback
    assert (await lecturer_client.get("/lecturer/assistant/trends/999999")).status_code == 404
