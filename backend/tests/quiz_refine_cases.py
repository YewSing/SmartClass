"""S42: the regenerate / refine cases shared by the live tests (tests/live/test_live_quiz_refine.py),
which call the real LLM and record its replies, and the replay tests (tests/test_quiz_refine.py).

They check structure and grounding on the synthetic test course, never exact wording.
"""
from sqlalchemy import update

from app.models.quiz import Quiz
from app.schemas.quiz import (
    AiScope,
    QuestionIn,
    QuestionOut,
    QuestionRegenerateIn,
    QuizCreate,
    QuizDetailOut,
    QuizRefineIn,
)
from app.services import quiz_questions, quiz_store
from app.services.quiz import refine
from tests.fixtures.synthetic import DOCS

TITLES = dict(DOCS)
BVA = TITLES["boundary-value-analysis"]
COVERAGE = TITLES["statement-and-branch-coverage"]

EASIER = "An easier one, about what a boundary value is"
HARDER = "Make question 2 harder, remove question 3 and add one short-answer question on branch coverage."
ONLY_MATERIAL = "Replace question 1 with a question on equivalence partitioning, using only the notes."
NOT_COVERED = "Add two questions about photosynthesis in plants."
TIMER = "Give the students 20 seconds per question."

QUESTIONS = [
    QuestionIn(type="mcq", text="For an input range of 1 to 100, which value is on a boundary?",
               options=["50", "100", "42", "7"], answer=1, topic="Boundary value analysis", origin="from_material",
               source_file=BVA, source_type="page", source_page=1, explanation="100 is the maximum."),
    QuestionIn(type="mcq", text="What does branch coverage require?",
               options=["Every comment is read", "Every branch is taken", "Every variable is named",
                        "Every file is opened"],
               answer=1, topic="Branch coverage", origin="from_material", source_file=COVERAGE, source_type="page",
               source_page=1, explanation="Each decision outcome is exercised."),
    QuestionIn(type="short", text="What is equivalence partitioning?",
               suggested_answer="Dividing the inputs into classes that are treated the same way.",
               topic="Equivalence partitioning", explanation="One value stands for its class."),
]


async def make_quiz(db, users, kb, *, questions=QUESTIONS, scope: AiScope | None = None) -> QuizDetailOut:
    """A draft whose questions are all approved."""
    actor = users["lecturer"]
    quiz = await quiz_store.create(db, actor, QuizCreate(course_id=kb["course_id"], title="Testing", type="graded"),
                                   questions, scope)
    if questions:
        quiz = await quiz_questions.set_approval(db, actor, quiz.id, [q.id for q in quiz.questions], True)
    await db.commit()
    return quiz


async def set_scope(db, quiz_id: int, scope: AiScope) -> None:
    await db.execute(update(Quiz).where(Quiz.id == quiz_id).values(ai_scope=scope.model_dump()))
    await db.commit()


async def run_regenerate(db, users, quiz, number: int, instruction: str | None = None) -> QuizDetailOut:
    out = await refine.regenerate(db, users["lecturer"], quiz.id, quiz.questions[number - 1].id,
                                  QuestionRegenerateIn(instruction=instruction))
    await db.commit()
    return out


async def run_refine(db, users, quiz, prompt: str) -> QuizDetailOut:
    out = await refine.refine(db, users["lecturer"], quiz.id, QuizRefineIn(prompt=prompt))
    await db.commit()
    return out


def check_new(q: QuestionOut, *, kind: str, terms: tuple[str, ...], old: QuestionOut | None = None) -> None:
    """A question the AI wrote: unapproved, complete, and about what it should be about."""
    assert q.type == kind and q.approved is False and q.topic and q.explanation
    if q.type == "mcq":
        assert 2 <= len(q.options) <= 6 and 0 <= q.answer < len(q.options)
    else:
        assert q.suggested_answer
    if q.origin == "from_material":
        assert q.source_file in TITLES.values() and f"(Source: {q.source_file}, " in q.explanation
    said = " ".join([q.text, q.topic, q.explanation, q.suggested_answer or "", *(q.options or [])]).lower()
    assert any(t in said for t in terms), f"not about it: {q.text!r}"
    if old is not None:
        assert q.text != old.text


def check_regenerated(before: QuizDetailOut, after: QuizDetailOut) -> None:
    assert [q.id for q in after.questions] == [q.id for q in before.questions]
    assert after.questions[1:] == before.questions[1:]
    check_new(after.questions[0], kind="mcq", terms=("boundar", "minimum", "maximum", "edge"),
              old=before.questions[0])


def check_harder(before: QuizDetailOut, after: QuizDetailOut) -> None:
    """Question 1 untouched, 2 rewritten in its place, 3 gone, a short answer at the end."""
    one, two, three = before.questions
    assert len(after.questions) == 3 and [q.position for q in after.questions] == [0, 1, 2]
    assert after.questions[0] == one
    assert after.questions[1].id == two.id and three.id not in [q.id for q in after.questions]
    check_new(after.questions[1], kind="mcq", terms=("branch", "coverage", "decision"), old=two)
    check_new(after.questions[2], kind="short", terms=("branch", "coverage", "decision"))


def check_only_material(before: QuizDetailOut, after: QuizDetailOut) -> None:
    assert after.questions[1:] == before.questions[1:]
    new = after.questions[0]
    check_new(new, kind="mcq", terms=("partition", "equivalence", "class"), old=before.questions[0])
    assert new.origin == "from_material"
