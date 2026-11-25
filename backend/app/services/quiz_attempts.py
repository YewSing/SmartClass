"""A student's graded attempt (FR-607, FR-608) — S44.

One attempt per student and quiz. Answers are saved one by one as the student works, so an attempt
resumes after a lost connection; its time never stops (rules in `quiz_timer`).

Access (NFR-04): students enrolled in the quiz's course, their own attempt only. Anyone else, an unknown
quiz and a draft get 403 (ids can't be probed).

Students get a question's text and options, never its answer, suggested answer, explanation, topic or
source (NFR-41).
"""
from __future__ import annotations

import random
import re
from datetime import datetime
from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import run_after_commit
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.quiz import Quiz, QuizAnswer, QuizAttempt, QuizQuestion
from app.models.user import Student, User
from app.schemas.quiz import AnswerIn, AttemptOptionOut, AttemptOut, AttemptQuestionOut
from app.services import quiz_publish, quiz_store, quiz_timer

_random = random.SystemRandom()     # tests replace this

# options that only make sense in their written order: "All of the above", "Both A and C"
_ORDERED = re.compile(r"\b(above|below|(all|both|none|neither|either) of (these|them|the)|"
                      r"(both|neither|either|options?) [a-f]\b)", re.IGNORECASE)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=detail)


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


async def _refuse(db: AsyncSession, detail: str) -> NoReturn:
    """409, keeping what the timers did to the attempt (an exception would roll it back)."""
    await db.commit()
    await run_after_commit(db)
    raise _conflict(detail)


async def _refuse_if_over(db: AsyncSession, attempt: QuizAttempt) -> None:
    if attempt.status == "submitted":
        await _refuse(db, "This quiz is over. Your answers were submitted." if attempt.auto_submitted
                      else "You have already submitted this quiz")


# ── loading ──────────────────────────────────────────────────────────────────

async def _quiz(db: AsyncSession, actor: User, quiz_id: int, *, share_lock: bool = False) -> tuple[Quiz, int]:
    """The quiz and the caller's students.id; 403 unless it is out and they are enrolled in its course."""
    student_id = await db.scalar(select(Student.id).where(Student.user_id == actor.id))
    quiz = None
    if student_id is not None:
        enrolled = (select(ClassOccurrence.course_id)
                    .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
                    .where(Enrollment.student_id == student_id))
        stmt = select(Quiz).where(Quiz.id == quiz_id, Quiz.course_id.in_(enrolled),
                                  Quiz.status.in_(("published", "closed")))
        if share_lock:
            stmt = stmt.with_for_update(read=True)
        quiz = (await db.execute(stmt.execution_options(populate_existing=True))).scalar_one_or_none()
    if quiz is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You can't take this quiz")
    if quiz.type != "graded":
        raise _conflict("This quiz is a live game. Join it in class.")
    return quiz, student_id


async def _attempt(db: AsyncSession, quiz_id: int, student_id: int) -> QuizAttempt | None:
    """The student's attempt, row-locked."""
    return (await db.execute(
        select(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.student_id == student_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()


async def _touch(db: AsyncSession, actor: User, quiz_id: int) -> tuple[Quiz, QuizAttempt, datetime]:
    """The caller's attempt, locked and brought up to now (404 when not started). The quiz needs no lock:
    closing it submits its attempts, which waits for this lock or is seen here."""
    quiz, student_id = await _quiz(db, actor, quiz_id)
    attempt = await _attempt(db, quiz.id, student_id)
    if attempt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="You haven't started this quiz")
    now = quiz_store.clock()
    quiz_timer.settle(quiz, attempt, now)
    return quiz, attempt, now


def _place(attempt: QuizAttempt, question_id: int) -> int:
    for i, item in enumerate(attempt.layout):
        if item["question_id"] == question_id:
            return i
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail="This quiz has no such question")


# ── the student's view ───────────────────────────────────────────────────────

def _question_out(question: QuizQuestion, item: dict, number: int, answer: QuizAnswer | None) -> AttemptQuestionOut:
    return AttemptQuestionOut(
        id=question.id, number=number, type=question.type, text=question.text,
        options=([AttemptOptionOut(index=i, text=question.options[i]) for i in item["options"]]
                 if question.type == "mcq" else None),
        option_index=answer.option_index if answer else None,
        answer_text=answer.text if answer else None,
        answered_at=answer.answered_at if answer else None)


async def _out(db: AsyncSession, quiz: Quiz, attempt: QuizAttempt, now: datetime) -> AttemptOut:
    await db.flush()
    running = attempt.status == "in_progress"
    by_question = running and quiz.timer_mode == "question"
    answers = {a.question_id: a for a in (await db.execute(
        select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id))).scalars()}
    questions = {}
    if running:
        questions = {q.id: q for q in await quiz_publish.published_questions(db, quiz.id)}
    shown = [(n, item) for n, item in enumerate(attempt.layout, start=1)
             if running and (not by_question or n - 1 == attempt.current_index)]

    def left(until: datetime) -> float:
        return round(max(0.0, (until - now).total_seconds()), 3)

    return AttemptOut(
        quiz_id=quiz.id, title=quiz.title,
        course_code=await db.scalar(select(Course.code).where(Course.id == quiz.course_id)),
        timer_mode=quiz.timer_mode, timer_seconds=quiz.timer_seconds, status=attempt.status,
        started_at=attempt.started_at, ends_at=attempt.ends_at, submitted_at=attempt.submitted_at,
        auto_submitted=attempt.auto_submitted, server_time=now,
        remaining_seconds=left(attempt.ends_at) if running else 0.0,
        current_number=attempt.current_index + 1 if by_question else None,
        question_ends_at=attempt.question_ends_at if by_question else None,
        question_remaining_seconds=left(attempt.question_ends_at) if by_question else None,
        question_count=len(attempt.layout), answered_count=len(answers),
        questions=[_question_out(questions[item["question_id"]], item, n, answers.get(item["question_id"]))
                   for n, item in shown])


# ── start / resume ───────────────────────────────────────────────────────────

def _layout(quiz: Quiz, questions: list[QuizQuestion]) -> list[dict]:
    """The attempt's own order of questions and options (shuffled when the quiz says so)."""
    items = []
    for q in questions:
        order = list(range(len(q.options))) if q.type == "mcq" else None
        if quiz.shuffle and order is not None and not any(_ORDERED.search(o) for o in q.options):
            _random.shuffle(order)
        items.append({"question_id": q.id, "options": order})
    if quiz.shuffle:
        _random.shuffle(items)
    return items


async def _create(db: AsyncSession, quiz: Quiz, student_id: int) -> tuple[QuizAttempt, bool]:
    questions = await quiz_publish.published_questions(db, quiz.id)
    now = quiz_store.clock()
    window = quiz_publish.window(quiz, now)
    if window == "upcoming":
        raise _conflict("This quiz isn't open yet")
    if window == "closed":
        raise _conflict("This quiz is closed")
    values = QuizAttempt(layout=_layout(quiz, questions))
    quiz_timer.start_clock(quiz, values, now, len(questions))
    # a second device may be starting at the same moment: the first one's attempt stands
    created = await db.scalar(
        insert(QuizAttempt).values(
            quiz_id=quiz.id, student_id=student_id, status="in_progress", started_at=now, auto_submitted=False,
            layout=values.layout, ends_at=values.ends_at, question_ends_at=values.question_ends_at,
            current_index=values.current_index)
        .on_conflict_do_nothing(constraint="uq_m6_attempts_quiz_student").returning(QuizAttempt.id))
    return await _attempt(db, quiz.id, student_id), created is not None


async def start(db: AsyncSession, actor: User, quiz_id: int) -> tuple[AttemptOut, bool]:
    """The student's attempt, started now or resumed where it is; True when it is new. 409 when the quiz
    can't be taken now or the attempt is over.

    The quiz is share-locked, so it can't be closed, unpublished or edited in between, while other
    students can start at the same time."""
    quiz, student_id = await _quiz(db, actor, quiz_id, share_lock=True)
    attempt = await _attempt(db, quiz.id, student_id)
    new = False
    if attempt is None:
        attempt, new = await _create(db, quiz, student_id)
    now = quiz_store.clock()
    quiz_timer.settle(quiz, attempt, now)
    await _refuse_if_over(db, attempt)
    return await _out(db, quiz, attempt, now), new


# ── taking it ────────────────────────────────────────────────────────────────

async def read(db: AsyncSession, actor: User, quiz_id: int) -> AttemptOut:
    quiz, attempt, now = await _touch(db, actor, quiz_id)
    return await _out(db, quiz, attempt, now)


def _checked(question: QuizQuestion, body: AnswerIn) -> tuple[int | None, str | None]:
    if question.type == "mcq":
        if body.text is not None:
            raise _invalid("Choose one of the options")
        if body.option_index is not None and not 0 <= body.option_index < len(question.options):
            raise _invalid("This question has no such option")
    elif body.option_index is not None:
        raise _invalid("This question needs a written answer")
    return body.option_index, body.text


async def save_answer(db: AsyncSession, actor: User, quiz_id: int, question_id: int, body: AnswerIn) -> AttemptOut:
    """Save (or clear) one answer; 409 once the time of the attempt or of the question is up, or before
    the question's turn. Saving the same answer again changes nothing (NFR-54)."""
    quiz, attempt, now = await _touch(db, actor, quiz_id)
    await _refuse_if_over(db, attempt)
    place = _place(attempt, question_id)
    if quiz.timer_mode == "question" and place != attempt.current_index:
        await _refuse(db, "This question's time is over" if place < attempt.current_index
                      else "This question hasn't started yet")
    question = await db.get(QuizQuestion, question_id)
    option_index, text = _checked(question, body)
    answer = (await db.execute(
        select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id, QuizAnswer.question_id == question_id)
        .execution_options(populate_existing=True))).scalar_one_or_none()
    if option_index is None and text is None:
        if answer is not None:
            await db.delete(answer)
    elif answer is None:
        db.add(QuizAnswer(attempt_id=attempt.id, question_id=question_id, option_index=option_index, text=text,
                          answered_at=now))
    elif (answer.option_index, answer.text) != (option_index, text):
        answer.option_index, answer.text, answer.answered_at = option_index, text, now
    return await _out(db, quiz, attempt, now)


async def next_question(db: AsyncSession, actor: User, quiz_id: int, question_id: int) -> AttemptOut:
    """With a timer per question: lock the current question's answer and go on (after the last one, the
    attempt is submitted). Asking again for a question already passed changes nothing."""
    quiz, attempt, now = await _touch(db, actor, quiz_id)
    if quiz.timer_mode != "question":
        raise _conflict("This quiz has one time limit for all its questions")
    place = _place(attempt, question_id)
    if attempt.status == "in_progress":
        if place > attempt.current_index:
            await _refuse(db, "This question hasn't started yet")
        if place == attempt.current_index:
            quiz_timer.advance(quiz, attempt, now)
    return await _out(db, quiz, attempt, now)


async def submit(db: AsyncSession, actor: User, quiz_id: int) -> AttemptOut:
    """Submit the attempt as it is. Submitting again changes nothing (NFR-54)."""
    quiz, attempt, now = await _touch(db, actor, quiz_id)
    quiz_timer.submit(attempt, now, auto=False)
    return await _out(db, quiz, attempt, now)
