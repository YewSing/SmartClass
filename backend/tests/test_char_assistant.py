"""Characterisation: AI Learning Assistant (Module 8) — materials, Moodle sync, chat sessions, answers.

The LLM (through the `llm.chat` adapter), the embedding model and Moodle are all mocked, so these
tests need only the docker postgres.
"""
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.ai_chat import ChatMessage, ChatSession
from app.models.knowledge import EMBEDDING_DIM, MAT_ERROR, MAT_INDEXED, MAT_NO_TEXT, KbChunk, KbMaterial
from app.services.kb import llm
from app.services.kb.assistant import SOURCE_COURSE, SOURCE_GENERAL
from app.services.kb.moodle_client import MoodleError, MoodleFile
from tests.test_kb import make_pdf

pytestmark = pytest.mark.db

VEC = [1.0] + [0.0] * (EMBEDDING_DIM - 1)


# ── mocks ─────────────────────────────────────────────────────────────────────

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
    """Replaces the LLM adapter. Set `.answer` (str or exception); `.calls` records every prompt."""
    class FakeLLM:
        answer: str | Exception = "Boundary value analysis tests the edges of each class [1]."
        calls: list[list[dict]] = []

        async def chat(self, messages, max_tokens=None, temperature=0.2):
            self.calls.append(messages)
            if "standalone search query" in messages[0]["content"]:
                return "rewritten: drawbacks of boundary value analysis"
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

    fake = FakeLLM()
    fake.calls = []
    monkeypatch.setattr(llm, "chat", fake.chat)
    return fake


class FakeMoodle:
    """Stands in for MoodleClient inside the router's `async with MoodleClient() as client`."""
    files: list[MoodleFile] = []
    data: dict[str, bytes] = {}
    error: Exception | None = None
    moodle_course_id: int | None = 42

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_course_id(self, shortname):
        return self.moodle_course_id

    async def list_files(self, course_id):
        if self.error:
            raise self.error
        return self.files

    async def download(self, file_url):
        return self.data[file_url]


@pytest.fixture
def fake_moodle(monkeypatch):
    FakeMoodle.files, FakeMoodle.data, FakeMoodle.error, FakeMoodle.moodle_course_id = [], {}, None, 42
    monkeypatch.setattr("app.routers.assistant.MoodleClient", FakeMoodle)
    return FakeMoodle


def _mf(module_id: int, name: str, modified: int = 100) -> MoodleFile:
    return MoodleFile(module_id, f"Lecture {module_id}", "Week 1", name, "/", f"http://moodle/{name}",
                      modified, 10, "application/pdf")


# ── seeded knowledge base ─────────────────────────────────────────────────────

async def _add_material(db, course_id, title, status=MAT_INDEXED, chunks=(), section="Week 4"):
    mat = KbMaterial(course_id=course_id, source_key=f"local:{title}", source="local", file_name=f"{title}.pdf",
                     title=title, section_name=section, status=status, chunk_count=len(chunks))
    db.add(mat)
    await db.flush()
    for i, (text, start, end) in enumerate(chunks):
        db.add(KbChunk(material_id=mat.id, course_id=course_id, chunk_index=i, text=text, location_type="slide",
                       location_start=start, location_end=end, heading=None, token_count=len(text) // 4,
                       embedding=VEC))
    await db.commit()
    return mat


@pytest.fixture
async def kb(classroom, db_session):
    """CS101 gets one indexed slide deck (one chunk, slides 4-6) and one scanned PDF without text."""
    bva = await _add_material(db_session, classroom["course_id"], "Black-box testing",
                              chunks=[("Boundary value analysis tests values at the edges of each class.", 4, 6)])
    scan = await _add_material(db_session, classroom["course_id"], "PYQ 2018", status=MAT_NO_TEXT)
    return {"bva_id": bva.id, "scan_id": scan.id}


async def _other_course_id(db, classroom):
    from app.models.class_ import ClassOccurrence
    return (await db.execute(select(ClassOccurrence.course_id)
                             .where(ClassOccurrence.id == classroom["other_occurrence_id"]))).scalar_one()


async def _new_chat(student_client, course_id, **body):
    resp = await student_client.post("/student/assistant/sessions", json={"course_id": course_id, **body})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── student: courses ──────────────────────────────────────────────────────────

async def test_student_courses_lists_enrolled_only_with_indexed_count(student_client, kb):
    resp = await student_client.get("/student/assistant/courses")
    assert resp.status_code == 200
    body = resp.json()
    assert [c["code"] for c in body] == ["CS101"]          # not CS202
    assert body[0]["indexed_materials"] == 1               # the no_text PDF is not counted


async def test_assistant_endpoints_are_student_only(lecturer_client, admin_client, classroom):
    for c in (lecturer_client, admin_client):
        assert (await c.get("/student/assistant/courses")).status_code == 403
        assert (await c.get("/student/assistant/sessions")).status_code == 403


# ── student: chat sessions ────────────────────────────────────────────────────

async def test_session_create_list_rename_delete(student_client, classroom):
    cid = classroom["course_id"]
    created = await _new_chat(student_client, cid, title="BVA questions")
    assert created["course_id"] == cid and created["title"] == "BVA questions"
    untitled = await _new_chat(student_client, cid)
    assert untitled["title"] is None

    listed = (await student_client.get("/student/assistant/sessions", params={"course_id": cid})).json()
    assert {s["id"] for s in listed} == {created["id"], untitled["id"]}

    resp = await student_client.patch(f"/student/assistant/sessions/{created['id']}", json={"title": "Renamed"})
    assert resp.status_code == 200 and resp.json()["title"] == "Renamed"
    assert (await student_client.patch(f"/student/assistant/sessions/{created['id']}",
                                       json={"title": ""})).status_code == 422

    assert (await student_client.delete(f"/student/assistant/sessions/{created['id']}")).status_code == 204
    listed = (await student_client.get("/student/assistant/sessions")).json()
    assert [s["id"] for s in listed] == [untitled["id"]]
    assert (await student_client.get(f"/student/assistant/sessions/{created['id']}/messages")).status_code == 404


async def test_create_session_for_course_not_enrolled_is_403(student_client, classroom, db_session):
    other = await _other_course_id(db_session, classroom)
    resp = await student_client.post("/student/assistant/sessions", json={"course_id": other})
    assert resp.status_code == 403


async def test_other_students_chat_is_404(student_client, classroom, db_session):
    """Another student's chat (even in the same course) looks like it doesn't exist."""
    chat = ChatSession(student_id=classroom["student_ids"][1], course_id=classroom["course_id"], title="theirs")
    db_session.add(chat)
    await db_session.commit()
    for call in (student_client.get(f"/student/assistant/sessions/{chat.id}/messages"),
                 student_client.patch(f"/student/assistant/sessions/{chat.id}", json={"title": "x"}),
                 student_client.delete(f"/student/assistant/sessions/{chat.id}"),
                 student_client.post(f"/student/assistant/sessions/{chat.id}/messages", json={"content": "hi"})):
        assert (await call).status_code == 404


async def test_message_after_enrolment_removed_is_403(student_client, classroom, db_session, fake_llm):
    """The session exists, but the student is no longer enrolled in its course."""
    other = await _other_course_id(db_session, classroom)
    chat = ChatSession(student_id=classroom["student_ids"][0], course_id=other)
    db_session.add(chat)
    await db_session.commit()
    resp = await student_client.post(f"/student/assistant/sessions/{chat.id}/messages", json={"content": "hi"})
    assert resp.status_code == 403
    assert fake_llm.calls == []


# ── student: answers ──────────────────────────────────────────────────────────

async def test_answer_cites_course_material_and_is_saved(student_client, classroom, kb, fake_llm, db_session):
    chat = await _new_chat(student_client, classroom["course_id"])
    resp = await student_client.post(f"/student/assistant/sessions/{chat['id']}/messages",
                                     json={"content": "  What is BVA?  "})
    assert resp.status_code == 200, resp.text
    reply = resp.json()
    assert reply["role"] == "assistant" and reply["source_type"] == SOURCE_COURSE
    assert reply["content"].endswith("[1].")
    [cit] = reply["citations"]
    assert cit["n"] == 1 and cit["material_id"] == kb["bva_id"]
    assert (cit["title"], cit["section"], cit["location"]) == ("Black-box testing", "Week 4", "slides 4-6")
    assert cit["snippet"].startswith("Boundary value analysis")

    # The prompt carried the numbered passage and the stripped question
    prompt = fake_llm.calls[-1]
    assert prompt[0]["role"] == "system" and "CS101 Intro to Testing" in prompt[0]["content"]
    assert "[1] Black-box testing, slides 4-6 (Week 4)" in prompt[-1]["content"]
    assert prompt[-1]["content"].endswith("Question: What is BVA?")

    # Both messages are stored; the first question becomes the chat title
    msgs = (await student_client.get(f"/student/assistant/sessions/{chat['id']}/messages")).json()
    assert [(m["role"], m["content"]) for m in msgs] == [("user", "What is BVA?"), ("assistant", reply["content"])]
    session = (await student_client.get("/student/assistant/sessions")).json()[0]
    assert session["title"] == "What is BVA?"
    user_msg = (await db_session.execute(select(ChatMessage).where(ChatMessage.role == "user"))).scalar_one()
    assert user_msg.retrieval_query == "What is BVA?"  # first turn: no rewrite


async def test_uncited_answer_is_general_and_invalid_citations_dropped(student_client, classroom, kb, fake_llm):
    fake_llm.answer = "This isn't covered in your course materials, so here's a general explanation: ... [7]"
    chat = await _new_chat(student_client, classroom["course_id"])
    reply = (await student_client.post(f"/student/assistant/sessions/{chat['id']}/messages",
                                       json={"content": "What is mutation testing?"})).json()
    assert reply["source_type"] == SOURCE_GENERAL and reply["citations"] == []
    assert "[7]" not in reply["content"]


async def test_latex_answer_is_cleaned_before_it_is_saved(student_client, classroom, kb, fake_llm):
    """T93: the stored answer is plain text, so the phone never shows raw LaTeX."""
    fake_llm.answer = r"BVA covers $$\frac{\text{edges}}{\text{classes}} \times 100\%$$ of cases [1]."
    chat = await _new_chat(student_client, classroom["course_id"])
    reply = (await student_client.post(f"/student/assistant/sessions/{chat['id']}/messages",
                                       json={"content": "What is BVA?"})).json()
    assert reply["content"] == "BVA covers\nedges/classes × 100%\nof cases [1]."
    msgs = (await student_client.get(f"/student/assistant/sessions/{chat['id']}/messages")).json()
    assert msgs[-1]["content"] == reply["content"]


async def test_no_materials_tells_the_llm_so(student_client, classroom, fake_llm):
    fake_llm.answer = "General answer."
    chat = await _new_chat(student_client, classroom["course_id"])
    reply = (await student_client.post(f"/student/assistant/sessions/{chat['id']}/messages",
                                       json={"content": "What is BVA?"})).json()
    assert reply["source_type"] == SOURCE_GENERAL
    assert "No course materials are indexed" in fake_llm.calls[-1][-1]["content"]


async def test_follow_up_is_rewritten_and_history_sent(student_client, classroom, kb, fake_llm, db_session,
                                                       monkeypatch):
    monkeypatch.setattr(settings, "ASSISTANT_REWRITE_FOLLOWUPS", True)
    chat = await _new_chat(student_client, classroom["course_id"])
    url = f"/student/assistant/sessions/{chat['id']}/messages"
    await student_client.post(url, json={"content": "What is BVA?"})
    await student_client.post(url, json={"content": "What are its drawbacks?"})

    rewrite_call, answer_call = fake_llm.calls[-2], fake_llm.calls[-1]
    assert "standalone search query" in rewrite_call[0]["content"]
    assert [m["role"] for m in answer_call] == ["system", "user", "assistant", "user"]  # history included
    queries = (await db_session.execute(select(ChatMessage.retrieval_query).where(ChatMessage.role == "user")
                                        .order_by(ChatMessage.id))).scalars().all()
    assert queries == ["What is BVA?", "rewritten: drawbacks of boundary value analysis"]


async def test_llm_unavailable_is_503_and_nothing_saved(student_client, classroom, kb, fake_llm, db_session):
    fake_llm.answer = llm.LLMUnavailable("AI provider error: Timeout")
    chat = await _new_chat(student_client, classroom["course_id"])
    resp = await student_client.post(f"/student/assistant/sessions/{chat['id']}/messages",
                                     json={"content": "What is BVA?"})
    assert resp.status_code == 503
    assert "Timeout" in resp.json()["detail"]
    assert (await db_session.execute(select(func.count()).select_from(ChatMessage))).scalar_one() == 0


async def test_message_validation(student_client, classroom, fake_llm):
    chat = await _new_chat(student_client, classroom["course_id"])
    url = f"/student/assistant/sessions/{chat['id']}/messages"
    assert (await student_client.post(url, json={"content": ""})).status_code == 422
    assert (await student_client.post(url, json={"content": "x" * 2001})).status_code == 422
    assert fake_llm.calls == []


# ── lecturer / admin: materials + sync ────────────────────────────────────────

async def test_materials_list_for_teaching_lecturer_and_admin(lecturer_client, admin_client, kb, classroom):
    for c in (lecturer_client, admin_client):
        resp = await c.get(f"/kb/courses/{classroom['course_id']}/materials")
        assert resp.status_code == 200
        rows = {m["title"]: m for m in resp.json()}
        assert rows["Black-box testing"]["status"] == MAT_INDEXED and rows["Black-box testing"]["chunk_count"] == 1
        assert rows["PYQ 2018"]["status"] == MAT_NO_TEXT


async def test_materials_access_control(other_lecturer_client, student_client, admin_client, kb, classroom):
    url = f"/kb/courses/{classroom['course_id']}/materials"
    assert (await other_lecturer_client.get(url)).status_code == 403   # doesn't teach CS101
    assert (await student_client.get(url)).status_code == 403          # wrong role
    assert (await admin_client.get("/kb/courses/999999/materials")).status_code == 404


async def test_sync_adds_skips_and_deletes(lecturer_client, classroom, fake_moodle, db_session):
    pdf = make_pdf(["Verification checks we built the product right, against the specification."])
    fake_moodle.files = [_mf(1, "week1.pdf"), _mf(2, "broken.pdf")]
    fake_moodle.data = {"http://moodle/week1.pdf": pdf, "http://moodle/broken.pdf": b"not a pdf"}
    url = f"/kb/courses/{classroom['course_id']}/sync"

    resp = await lecturer_client.post(url)
    assert resp.status_code == 200, resp.text
    report = resp.json()
    assert report["course_code"] == "CS101"
    assert (report["added"], report["updated"], report["unchanged"], report["deleted"]) == (2, 0, 0, 0)
    assert len(report["failed"]) == 1 and report["failed"][0].startswith("broken.pdf")
    assert report["statuses"] == {MAT_INDEXED: 1, MAT_ERROR: 1}

    mats = {m.file_name: m for m in (await db_session.execute(select(KbMaterial))).scalars()}
    assert mats["week1.pdf"].title == "Lecture 1" and mats["week1.pdf"].section_name == "Week 1"
    assert mats["week1.pdf"].chunk_count >= 1

    # Second sync: week1 is unchanged (not downloaded again); broken.pdf left Moodle, so it is deleted
    fake_moodle.files = [_mf(1, "week1.pdf")]
    report = (await lecturer_client.post(url)).json()
    assert (report["added"], report["updated"], report["unchanged"], report["deleted"]) == (0, 0, 1, 1)
    db_session.expire_all()
    assert [m.file_name for m in (await db_session.execute(select(KbMaterial))).scalars()] == ["week1.pdf"]


async def test_sync_moodle_error_is_502(lecturer_client, classroom, fake_moodle):
    fake_moodle.error = MoodleError("core_course_get_contents: invalidtoken - Invalid token")
    resp = await lecturer_client.post(f"/kb/courses/{classroom['course_id']}/sync")
    assert resp.status_code == 502 and "invalidtoken" in resp.json()["detail"]


async def test_sync_course_missing_in_moodle_is_502(lecturer_client, classroom, fake_moodle):
    fake_moodle.moodle_course_id = None
    resp = await lecturer_client.post(f"/kb/courses/{classroom['course_id']}/sync")
    assert resp.status_code == 502 and "No Moodle course with shortname CS101" in resp.json()["detail"]


async def test_sync_access_control(other_lecturer_client, student_client, classroom, fake_moodle):
    url = f"/kb/courses/{classroom['course_id']}/sync"
    assert (await other_lecturer_client.post(url)).status_code == 403
    assert (await student_client.post(url)).status_code == 403
