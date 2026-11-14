"""Tests for quiz question generation (FR-601, FR-602, FR-603, S30).

Mocks `retrieval_api.search` and `llm.chat_json` so no real LLM or KB is needed.
Covers: mcq and short_answer generation, source material + topic carried on each question,
ownership (NFR-04), unknown course, and LLM error mapping (malformed → 502, unavailable → 503).

Live cases (≥3: generation per type + a material with no retrievable text) are recorded in
the T82 suite with `pytest -m live --record-llm` when `LLM_API_KEY` is set.
"""


import pytest
from sqlalchemy import select

from app.models.quiz import QuizQuestion
from app.services.kb.llm import LLMUnavailable, LLMMalformedOutput
from app.services.kb.search import Passage
from app.schemas.quiz import GeneratedQuestion

pytestmark = pytest.mark.db


def _passage(material_id: int, text: str = "passage text", heading: str = "Topic") -> Passage:
    return Passage(
        chunk_id=1, material_id=material_id, title=f"Material {material_id}",
        section_name="Week 1", location_type="page", location_start=1, location_end=1,
        heading=heading, text=text, score=0.9, vector_similarity=0.9,
    )


def _generated(qtext: str = "Q?", qtype: str = "mcq", level: str = "beginner",
               topic: str = "t") -> GeneratedQuestion:
    return GeneratedQuestion(
        question=qtext, options=["A", "B", "C", "D"],
        correct_answer="A" if qtype == "mcq" else None,
        suggested_answer=None if qtype == "mcq" else "ideal answer",
        level=level, topic=topic,
    )


async def _fake_search(course_id: int, query: str, k: int = 8):
    """Return one passage for the material named in the query ("material <id>")."""
    material_id = int(query.split()[-1])
    return [_passage(material_id)]


async def _fake_chat_json(messages, *, max_tokens=None, temperature=0.2, retries=1, validator=None):
    _fake_chat_json.calls += 1
    return _generated(qtext=f"generated question {_fake_chat_json.calls}")


_fake_chat_json.calls = 0


async def _raising_chat_json(messages, *, max_tokens=None, temperature=0.2, retries=1, validator=None):
    raise LLMMalformedOutput("bad json")


async def _unavailable_chat_json(messages, *, max_tokens=None, temperature=0.2, retries=1, validator=None):
    raise LLMUnavailable("down")


async def _apply_monkeypatch(monkeypatch, chat_json_mock):
    monkeypatch.setattr("app.services.quiz_service.retrieval_api.search", _fake_search)
    monkeypatch.setattr("app.services.quiz_service.llm.chat_json", chat_json_mock)


# ── generate ────────────────────────────────────────────────────────────────

async def test_generate_mcq_questions(lecturer_client, classroom, monkeypatch, db_session):
    await _apply_monkeypatch(monkeypatch, _fake_chat_json)
    resp = await lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/generate",
        json={"material_ids": [101, 102, 103], "type": "mcq", "level": "beginner", "count": 3},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body) == 3
    assert all(q["type"] == "mcq" for q in body)
    assert all(q["status"] == "draft" for q in body)
    assert all(q["quiz_id"] is None for q in body)
    assert {q["source_material_id"] for q in body} == {101, 102, 103}
    assert all(q["topic"] for q in body)
    assert all(q["options"] and len(q["options"]) >= 2 for q in body)
    assert all(q["correct_answer"] for q in body)

    result = await db_session.execute(
        select(QuizQuestion).where(QuizQuestion.course_id == classroom["course_id"])
    )
    assert len(result.scalars().all()) == 3


async def test_generate_short_answer_questions(lecturer_client, classroom, monkeypatch, db_session):
    await _apply_monkeypatch(monkeypatch, _fake_chat_json)
    resp = await lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/generate",
        json={"material_ids": [101], "type": "short_answer", "level": "advanced", "count": 2},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body) == 2
    assert all(q["type"] == "short_answer" for q in body)
    assert all(q["level"] == "advanced" for q in body)
    assert all(q["suggested_answer"] for q in body)
    assert all(q["correct_answer"] is None for q in body)


async def test_generate_skips_material_with_no_retrievable_text(
    lecturer_client, classroom, monkeypatch, db_session
):
    async def fake_search_empty_for_102(course_id: int, query: str, k: int = 8):
        material_id = int(query.split()[-1])
        return [] if material_id == 102 else [_passage(material_id)]

    monkeypatch.setattr("app.services.quiz_service.retrieval_api.search", fake_search_empty_for_102)
    monkeypatch.setattr("app.services.quiz_service.llm.chat_json", _fake_chat_json)

    resp = await lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/generate",
        json={"material_ids": [101, 102, 103], "type": "mcq", "level": "beginner", "count": 3},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # material 102 contributed nothing, so only 101 and 103 produced questions
    assert len(body) == 2
    assert {q["source_material_id"] for q in body} == {101, 103}


# ── ownership / errors ──────────────────────────────────────────────────────

async def test_generate_unknown_course_is_404(lecturer_client, monkeypatch):
    await _apply_monkeypatch(monkeypatch, _fake_chat_json)
    resp = await lecturer_client.post(
        "/lecturer/courses/999999/quizzes/generate",
        json={"material_ids": [101], "type": "mcq", "level": "beginner", "count": 1},
    )
    assert resp.status_code == 404, resp.text


async def test_generate_other_lecturer_is_403(other_lecturer_client, classroom, monkeypatch):
    await _apply_monkeypatch(monkeypatch, _fake_chat_json)
    resp = await other_lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/generate",
        json={"material_ids": [101], "type": "mcq", "level": "beginner", "count": 1},
    )
    assert resp.status_code == 403, resp.text


async def test_generate_malformed_llm_is_502(lecturer_client, classroom, monkeypatch):
    monkeypatch.setattr("app.services.quiz_service.retrieval_api.search", _fake_search)
    monkeypatch.setattr("app.services.quiz_service.llm.chat_json", _raising_chat_json)
    resp = await lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/generate",
        json={"material_ids": [101], "type": "mcq", "level": "beginner", "count": 1},
    )
    assert resp.status_code == 502, resp.text


async def test_generate_llm_unavailable_is_503(lecturer_client, classroom, monkeypatch):
    monkeypatch.setattr("app.services.quiz_service.retrieval_api.search", _fake_search)
    monkeypatch.setattr("app.services.quiz_service.llm.chat_json", _unavailable_chat_json)
    resp = await lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/generate",
        json={"material_ids": [101], "type": "mcq", "level": "beginner", "count": 1},
    )
    assert resp.status_code == 503, resp.text


async def test_generate_invalid_type_is_422(lecturer_client, classroom):
    resp = await lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/generate",
        json={"material_ids": [101], "type": "essay", "level": "beginner", "count": 1},
    )
    assert resp.status_code == 422, resp.text
