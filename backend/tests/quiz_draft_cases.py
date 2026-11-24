"""S41: the quiz draft cases shared by the live tests (tests/live/test_live_quiz_draft.py), which call
the real LLM and record its replies, and the replay tests (tests/test_quiz_draft.py).

They check structure and grounding on the synthetic test course, never exact wording.
"""
from datetime import datetime

from sqlalchemy import func, select

from app.models.knowledge import KbChunk, KbMaterial
from app.models.quiz import Quiz
from app.schemas.quiz import QuizDetailOut, QuizDraftIn
from app.services import quiz_store
from app.services.quiz import draft
from tests.fixtures.synthetic import DOCS

NOW = datetime(2026, 11, 25, 10, 0)     # a Wednesday; in the prompt, so a replay sends what was recorded
TITLES = dict(DOCS)

GAME = "Game quiz on boundary value analysis, 3 MCQ and 1 short-answer, 20 seconds per question, shuffle the questions."
ONLY_MATERIAL = ("Graded quiz, 4 MCQ on statement and branch coverage. Use only the notes. 15 minutes in total. "
                 "Open on 30 November 2026 at 9 am and close at 11 am the same day.")
SELECTED = "2 MCQ and 1 short answer question about this material"
NOT_COVERED = "Graded quiz, 3 MCQ on photosynthesis in plants, only from the course material"


async def run_draft(monkeypatch, db, users, kb, prompt: str, stems: tuple[str, ...] = ()) -> QuizDetailOut:
    monkeypatch.setattr(quiz_store, "clock", lambda: NOW)
    body = QuizDraftIn(course_id=kb["course_id"], prompt=prompt,
                       material_ids=[kb["material_ids"][s] for s in stems] or None)
    quiz = await draft.create_draft(db, users["lecturer"], body)
    await db.commit()
    return quiz


async def check_structure(db, quiz: QuizDetailOut, *, mcq: int, short: int, terms: tuple[str, ...]) -> None:
    """Counts, required fields, real sources, and every question from the material is about it."""
    assert quiz.status == "draft" and quiz.title
    assert [q.position for q in quiz.questions] == list(range(mcq + short))
    assert sum(q.type == "mcq" for q in quiz.questions) == mcq
    assert sum(q.type == "short" for q in quiz.questions) == short
    real = {(title, kind, start) for title, kind, start in (await db.execute(
        select(KbMaterial.title, KbChunk.location_type, KbChunk.location_start)
        .join(KbChunk, KbChunk.material_id == KbMaterial.id))).all()}
    for q in quiz.questions:
        assert q.approved is False
        assert q.topic and q.explanation
        if q.type == "mcq":
            assert 2 <= len(q.options) <= 6 and 0 <= q.answer < len(q.options)
        else:
            assert q.suggested_answer
        if q.origin == "from_material":
            assert (q.source_file, q.source_type, q.source_page) in real
            assert f"(Source: {q.source_file}, " in q.explanation
            said = " ".join([q.text, q.explanation, q.suggested_answer or "", *(q.options or [])]).lower()
            assert any(t in said for t in terms), f"not about the material: {q.text!r}"
    assert any(q.origin == "from_material" for q in quiz.questions)


async def check_game(db, quiz: QuizDetailOut) -> None:
    await check_structure(db, quiz, mcq=3, short=1, terms=("boundar", "bva", "minimum", "maximum", "edge"))
    assert (quiz.type, quiz.timer_mode, quiz.timer_seconds, quiz.shuffle) == ("game", "question", 20, True)
    assert quiz.opens_at is None and quiz.closes_at is None


async def check_only_material(db, quiz: QuizDetailOut) -> None:
    await check_structure(db, quiz, mcq=4, short=0, terms=("coverage", "statement", "branch", "decision"))
    assert (quiz.type, quiz.timer_mode, quiz.timer_seconds) == ("graded", "quiz", 900)
    assert quiz.opens_at == datetime(2026, 11, 30, 9) and quiz.closes_at == datetime(2026, 11, 30, 11)
    assert all(q.origin == "from_material" for q in quiz.questions)


async def check_selected(db, quiz: QuizDetailOut) -> None:
    await check_structure(db, quiz, mcq=2, short=1, terms=("partition", "equivalence", "class", "input"))
    files = {q.source_file for q in quiz.questions if q.source_file}
    assert files == {TITLES["equivalence-partitioning"]}


async def count_quizzes(db) -> int:
    return await db.scalar(select(func.count()).select_from(Quiz))
