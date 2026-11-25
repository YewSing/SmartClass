"""Results of graded quizzes: the student's own (FR-618) and the lecturer's (FR-619) — S46.

Every question is worth one mark. An answer's score is its share of that mark (`quiz_grading`); a question
without an answer scores 0; a pending short answer isn't counted until it is graded.

A student gets only what the lecturer has released (`quiz_release.released_parts`, NFR-41):
- marks: the totals, nothing per question (a right multiple-choice answer would give the key away);
- answers: their answer, the correct one and the explanation of each question, without any mark;
- both: also each question's score, the AI's reason and the lecturer's feedback.

Read live: a score the lecturer or the AI sets after the release shows at once.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.class_ import Course
from app.models.quiz import QuizAnswer, QuizAttempt, QuizQuestion
from app.models.user import Student, User
from app.schemas.quiz import (
    AttemptOptionOut,
    MarksOut,
    QuestionResultOut,
    QuizResultsOut,
    ScoreBandOut,
    StudentResultOut,
    StudentResultQuestionOut,
    SubmissionOut,
)
from app.services import quiz_attempts, quiz_grading, quiz_publish, quiz_release, quiz_store

BANDS = 10      # of the score distribution


# ── numbers ──────────────────────────────────────────────────────────────────

def _rounded(value: Decimal, places: str) -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _share(part: Decimal | int, whole: int) -> float | None:
    """`part` of `whole`, 0 to 1; None of nothing."""
    return _rounded(Decimal(part) / whole, "0.001") if whole else None


def _percent(score: Decimal, max_score: int) -> float:
    return _rounded(100 * score / max_score, "0.1") if max_score else 0.0


def _total(answers: Iterable[QuizAnswer]) -> Decimal:
    return sum((a.score for a in answers if a.score is not None), Decimal(0))


def _pending(answer: QuizAnswer) -> bool:
    """Of a submitted attempt, whose multiple-choice answers always have a score."""
    return answer.score is None


def _marks(answers: list[QuizAnswer], question_count: int) -> MarksOut:
    score = _total(answers)
    return MarksOut(score=_rounded(score, "0.001"), max_score=question_count,
                    percent=_percent(score, question_count), pending_count=sum(map(_pending, answers)))


# ── the student ──────────────────────────────────────────────────────────────

def _question_out(question: QuizQuestion, item: dict, number: int, answer: QuizAnswer | None,
                  with_marks: bool) -> StudentResultQuestionOut:
    out = StudentResultQuestionOut(
        id=question.id, number=number, type=question.type, text=question.text,
        options=([AttemptOptionOut(index=i, text=question.options[i]) for i in item["options"]]
                 if question.type == "mcq" else None),
        option_index=answer.option_index if answer else None, answer_text=answer.text if answer else None,
        correct_option_index=question.answer, suggested_answer=question.suggested_answer,
        explanation=question.explanation,
        pending=None, score=None, correct=None, reason=None, feedback=None)
    if with_marks:
        out.pending = answer is not None and _pending(answer)
        if answer is None:
            out.score, out.correct = 0.0, False
        elif not out.pending:
            out.score, out.correct = float(answer.score), answer.correct
            out.reason, out.feedback = answer.reason, answer.feedback
    return out


async def student_result(db: AsyncSession, actor: User, quiz_id: int) -> StudentResultOut:
    """The caller's own result, cut down to what is released. Access as for the attempt: 403 unless
    enrolled, 409 for a game, 404 when not taken."""
    quiz, attempt, _ = await quiz_attempts.touch(db, actor, quiz_id)
    await db.flush()
    marks_out, answers_out = quiz_release.released_parts(quiz)
    if attempt.status != "submitted":
        marks_out = answers_out = False
    out = StudentResultOut(
        quiz_id=quiz.id, title=quiz.title,
        course_code=await db.scalar(select(Course.code).where(Course.id == quiz.course_id)),
        status=attempt.status, submitted_at=attempt.submitted_at, auto_submitted=attempt.auto_submitted,
        released_at=quiz.released_at if marks_out or answers_out else None,
        marks_released=marks_out, answers_released=answers_out, marks=None, questions=None)
    if not (marks_out or answers_out):
        return out
    answers = {a.question_id: a for a in (await db.execute(
        select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id)
        .execution_options(populate_existing=True))).scalars()}
    if marks_out:
        out.marks = _marks(list(answers.values()), len(attempt.layout))
    if answers_out:
        questions = {q.id: q for q in await quiz_publish.published_questions(db, quiz.id)}
        out.questions = [
            _question_out(questions[item["question_id"]], item, n, answers.get(item["question_id"]), marks_out)
            for n, item in enumerate(attempt.layout, start=1)]
    return out


# ── the lecturer ─────────────────────────────────────────────────────────────

def _question_result(question: QuizQuestion, number: int, answers: list[QuizAnswer],
                     submitted: int) -> QuestionResultOut:
    pending = sum(map(_pending, answers))
    correct = sum(1 for a in answers if a.correct)
    graded = submitted - pending
    chosen = Counter(a.option_index for a in answers)
    return QuestionResultOut(
        id=question.id, number=number, type=question.type, text=question.text, topic=question.topic,
        correct_count=correct, incorrect_count=len(answers) - pending - correct,
        unanswered_count=submitted - len(answers), pending_count=pending,
        correct_rate=_share(correct, graded), average_score=_share(_total(answers), graded),
        option_counts=[chosen[i] for i in range(len(question.options))] if question.type == "mcq" else None)


def _most_missed(questions: list[QuestionResultOut]) -> list[int]:
    """The questions with the lowest correct rate, the worst first; never one everybody got right."""
    missed = []
    for q in questions:
        wrong = q.incorrect_count + q.unanswered_count
        if wrong:
            missed.append((-Decimal(wrong) / (wrong + q.correct_count), q.number, q.id))
    return [question_id for *_, question_id in sorted(missed)[:settings.QUIZ_MOST_MISSED]]


def _distribution(percents: list[float]) -> list[ScoreBandOut]:
    width = 100 // BANDS
    counts = Counter(min(int(p // width), BANDS - 1) for p in percents)
    return [ScoreBandOut(from_percent=i * width, to_percent=(i + 1) * width, count=counts[i]) for i in range(BANDS)]


async def lecturer_results(db: AsyncSession, actor: User, quiz_id: int) -> QuizResultsOut:
    """How the class did. Every student's attempt counts, also of one who has left the course since."""
    quiz = await quiz_grading.graded_quiz(db, actor, quiz_id)
    questions = await quiz_publish.published_questions(db, quiz.id)
    rows = (await db.execute(
        select(QuizAttempt, Student, User.name)
        .join(Student, Student.id == QuizAttempt.student_id).join(User, User.id == Student.user_id)
        .where(QuizAttempt.quiz_id == quiz.id).order_by(User.name, QuizAttempt.id))).all()
    submitted = [attempt.id for attempt, *_ in rows if attempt.status == "submitted"]
    by_attempt, by_question = defaultdict(list), defaultdict(list)
    for a in (await db.execute(select(QuizAnswer).where(QuizAnswer.attempt_id.in_(submitted)))).scalars():
        by_attempt[a.attempt_id].append(a)
        by_question[a.question_id].append(a)

    marks = {attempt_id: _marks(by_attempt[attempt_id], len(questions)) for attempt_id in submitted}
    complete = [attempt_id for attempt_id in submitted if marks[attempt_id].pending_count == 0]
    total = sum((_total(by_attempt[i]) for i in complete), Decimal(0))
    scores = [marks[i].score for i in complete]
    results = [_question_result(q, n, by_question[q.id], len(submitted)) for n, q in enumerate(questions, start=1)]
    enrolled = set(await quiz_publish.enrolled_user_ids(db, quiz.course_id))
    release = quiz_release.release_out(quiz, quiz_store.clock())
    return QuizResultsOut(
        **release.model_dump(), quiz_id=quiz.id, title=quiz.title, status=quiz.status,
        question_count=len(questions), enrolled_count=len(enrolled),
        not_started_count=len(enrolled - {student.user_id for _, student, _ in rows}),
        in_progress_count=len(rows) - len(submitted), submitted_count=len(submitted), graded_count=len(complete),
        pending_answer_count=sum(m.pending_count for m in marks.values()),
        average_score=_rounded(total / len(complete), "0.001") if complete else None,
        average_percent=_percent(total, len(questions) * len(complete)) if complete else None,
        highest_score=max(scores, default=None), lowest_score=min(scores, default=None),
        distribution=_distribution([marks[i].percent for i in complete]),
        questions=results, most_missed=_most_missed(results),
        submissions=[
            SubmissionOut(student_id=student.id, student_name=name, matric_no=student.matric_no,
                          status=attempt.status, started_at=attempt.started_at, submitted_at=attempt.submitted_at,
                          auto_submitted=attempt.auto_submitted, marks=marks.get(attempt.id))
            for attempt, student, name in rows])
