"""Read interfaces over Module 6's quizzes for Module 8 (FR-609, FR-620) and Module 7 (FR-621) — S47.
Documented in docs/interfaces.md ("Quiz read interface for Modules 7 and 8").

Rules:
- Only submitted attempts of students enrolled in the course now. So nothing of a game shows before the
  student's attempt in it is submitted, which the game does when it ends.
- `audience` says who will see the figures. "lecturer": everything. "student": the student themselves, so only
  what the lecturer has released (FR-618, NFR-41): a graded score once the marks are out; a graded quiz's
  answers and topics once marks and answers both are, as each of them gives the other away. Games have
  nothing to release. The `course_*` functions are for lecturers.
- A graded question the student left unanswered is a row with `answered` False and counts as not correct. A
  game has rows for answered questions only (a late joiner never saw the others).
- An answer without a grade yet is `pending`: neither right nor wrong.
- Dates are the MYT date the attempt was submitted; ranges are inclusive.
- Read only, never commits. No permission checks: the caller checks the user may see the course (NFR-04) first.
Returned objects are frozen dataclasses; fields may be added later but are never renamed or removed.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, get_args

from sqlalchemy import Date, cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.quiz import Quiz, QuizAnswer, QuizAttempt, QuizQuestion
from app.models.user import Student, User
from app.services import quiz_release, quiz_results, quiz_store

__all__ = [
    "StudentQuizAnswer",
    "GradedScore",
    "TopicResult",
    "GameParticipation",
    "has_active_graded_attempt",
    "student_answers",
    "course_answers",
    "student_graded_scores",
    "course_graded_scores",
    "student_topic_results",
    "course_topic_results",
    "student_game_participation",
    "course_game_participation",
]

Audience = Literal["student", "lecturer"]


@dataclass(frozen=True)
class StudentQuizAnswer:
    """One question of one submitted attempt."""
    student_id: int                     # students.id
    matric_no: str
    name: str
    course_id: int
    course_code: str
    quiz_id: int
    quiz_title: str
    quiz_type: str                      # graded | game
    submitted_at: datetime              # of the attempt, naive MYT
    question_id: int
    question_number: int                # 1-based, in the quiz's own order
    question_type: str                  # mcq | short
    question_text: str
    options: tuple[str, ...] | None     # mcq
    topic: str | None
    source_file: str | None
    source_type: str | None             # page | slide | section
    source_page: int | None
    origin: str                         # from_material | extended
    answered: bool
    option_index: int | None            # the student's choice (mcq)
    answer_text: str | None             # the student's text (short)
    correct_option_index: int | None    # mcq
    suggested_answer: str | None        # short
    explanation: str | None
    pending: bool                       # answered, but not graded yet
    correct: bool | None                # None while pending
    score: float | None                 # 0 to 1, None while pending


@dataclass(frozen=True)
class GradedScore:
    """One student's score in one graded quiz. Every question is worth one mark."""
    student_id: int
    matric_no: str
    name: str
    course_id: int
    course_code: str
    quiz_id: int
    quiz_title: str
    date: date
    submitted_at: datetime              # naive MYT
    score: float
    max_score: int
    percent: float
    pending_count: int                  # short answers without a grade yet: the score is not complete


@dataclass(frozen=True)
class TopicResult:
    """One student's answers on one topic, for one type of quiz (graded and game are kept apart)."""
    student_id: int
    matric_no: str
    name: str
    course_id: int
    course_code: str
    quiz_type: str                      # graded | game
    topic: str | None                   # None: questions without a topic
    question_count: int
    answered_count: int
    correct_count: int
    pending_count: int
    correct_rate: float | None          # 0 to 1, of the questions that aren't pending


@dataclass(frozen=True)
class GameParticipation:
    """One student and one game that was played in the course, whether or not they were in it."""
    student_id: int
    matric_no: str
    name: str
    course_id: int
    course_code: str
    quiz_id: int
    quiz_title: str
    date: date
    played: bool
    questions_asked: int                # questions at least one student answered
    questions_answered: int             # ...by this student
    correct_count: int


# ── FR-609 ───────────────────────────────────────────────────────────────────

async def has_active_graded_attempt(db: AsyncSession, student_id: int, course_id: int) -> bool:
    """Whether the student is taking a graded quiz of the course right now. An attempt whose time is up is
    over, also when nothing has submitted it yet."""
    return bool(await db.scalar(select(
        exists().where(QuizAttempt.quiz_id == Quiz.id, QuizAttempt.student_id == student_id,
                       Quiz.course_id == course_id, Quiz.type == "graded", QuizAttempt.status == "in_progress",
                       or_(QuizAttempt.ends_at.is_(None), QuizAttempt.ends_at > quiz_store.clock())))))


# ── loading ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Taken:
    """A submitted attempt with whose it is and in which course."""
    attempt: QuizAttempt
    quiz: Quiz
    who: dict       # the fields every returned object starts with


def _who(student_id: int, matric_no: str, name: str, course_id: int, course_code: str) -> dict:
    return {"student_id": student_id, "matric_no": matric_no, "name": name, "course_id": course_id,
            "course_code": course_code}


def _check_range(from_date: date | None, to_date: date | None) -> None:
    if from_date and to_date and from_date > to_date:
        raise ValueError("from_date must be on or before to_date")


def _check_audience(audience: str) -> None:
    if audience not in get_args(Audience):
        raise ValueError(f"audience must be one of {get_args(Audience)}")


def _in_range(day, from_date: date | None, to_date: date | None) -> list:
    """SQL conditions for a date."""
    return ([day >= from_date] if from_date else []) + ([day <= to_date] if to_date else [])


async def _taken(db: AsyncSession, *, course_id: int | None = None, student_id: int | None = None,
                 quiz_type: str | None = None, from_date: date | None = None,
                 to_date: date | None = None) -> list[_Taken]:
    """By student (matric no), then as they were submitted."""
    _check_range(from_date, to_date)
    enrolled = exists().where(Enrollment.student_id == QuizAttempt.student_id,
                              ClassOccurrence.id == Enrollment.occurrence_id,
                              ClassOccurrence.course_id == Quiz.course_id)
    stmt = (select(QuizAttempt, Quiz, Student.matric_no, User.name, Course.code)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id).join(Course, Course.id == Quiz.course_id)
            .join(Student, Student.id == QuizAttempt.student_id).join(User, User.id == Student.user_id)
            .where(QuizAttempt.status == "submitted", enrolled,
                   *_in_range(cast(QuizAttempt.submitted_at, Date), from_date, to_date))
            .order_by(Student.matric_no, Student.id, QuizAttempt.submitted_at, QuizAttempt.id))
    if course_id is not None:
        stmt = stmt.where(Quiz.course_id == course_id)
    if student_id is not None:
        stmt = stmt.where(QuizAttempt.student_id == student_id)
    if quiz_type is not None:
        stmt = stmt.where(Quiz.type == quiz_type)
    rows = (await db.execute(stmt.execution_options(populate_existing=True))).all()
    return [_Taken(attempt, quiz, _who(attempt.student_id, matric, name, quiz.course_id, code))
            for attempt, quiz, matric, name, code in rows]


async def _answers_of(db: AsyncSession, taken: list[_Taken]) -> dict[int, dict[int, QuizAnswer]]:
    """By attempt, then question."""
    out: dict[int, dict[int, QuizAnswer]] = defaultdict(dict)
    if taken:
        for a in (await db.execute(
                select(QuizAnswer).where(QuizAnswer.attempt_id.in_([t.attempt.id for t in taken]))
                .execution_options(populate_existing=True))).scalars():
            out[a.attempt_id][a.question_id] = a
    return out


def _released_to_student(quiz: Quiz) -> tuple[bool, bool]:
    """Whether the student themselves may see their score, and their answers with what was right."""
    if quiz.type == "game":
        return False, True      # a game has points, not a score
    marks, answers = quiz_release.released_parts(quiz)
    return marks, marks and answers


# ── answers (FR-620) ─────────────────────────────────────────────────────────

def _answer(taken: _Taken, question: QuizQuestion, number: int, answer: QuizAnswer | None) -> StudentQuizAnswer:
    if answer is None:
        pending, correct, score = False, False, 0.0
    else:
        pending, correct = answer.correct is None, answer.correct
        score = None if answer.score is None else float(answer.score)
    return StudentQuizAnswer(
        **taken.who, quiz_id=taken.quiz.id, quiz_title=taken.quiz.title, quiz_type=taken.quiz.type,
        submitted_at=taken.attempt.submitted_at, question_id=question.id, question_number=number,
        question_type=question.type, question_text=question.text,
        options=tuple(question.options) if question.type == "mcq" else None, topic=question.topic,
        source_file=question.source_file, source_type=question.source_type, source_page=question.source_page,
        origin=question.origin, answered=answer is not None, option_index=answer.option_index if answer else None,
        answer_text=answer.text if answer else None, correct_option_index=question.answer,
        suggested_answer=question.suggested_answer, explanation=question.explanation, pending=pending,
        correct=correct, score=score)


async def _answers(db: AsyncSession, taken: list[_Taken]) -> list[StudentQuizAnswer]:
    """Every question of the attempts, each in its quiz's own order."""
    given = await _answers_of(db, taken)
    questions: dict[int, list[QuizQuestion]] = defaultdict(list)
    if taken:
        for q in (await db.execute(
                select(QuizQuestion)
                .where(QuizQuestion.quiz_id.in_({t.quiz.id for t in taken}), QuizQuestion.approved)
                .order_by(QuizQuestion.quiz_id, QuizQuestion.position)
                .execution_options(populate_existing=True))).scalars():
            questions[q.quiz_id].append(q)
    out = []
    for t in taken:
        mine = given[t.attempt.id]
        for number, q in enumerate(questions[t.quiz.id], start=1):
            if t.quiz.type == "graded" or q.id in mine:
                out.append(_answer(t, q, number, mine.get(q.id)))
    return out


async def student_answers(db: AsyncSession, student_id: int, course_id: int | None = None, *, audience: Audience,
                          from_date: date | None = None, to_date: date | None = None) -> list[StudentQuizAnswer]:
    """The student's answers, question by question, oldest attempt first."""
    _check_audience(audience)
    taken = await _taken(db, student_id=student_id, course_id=course_id, from_date=from_date, to_date=to_date)
    return await _answers(db, [t for t in taken if audience == "lecturer" or _released_to_student(t.quiz)[1]])


async def course_answers(db: AsyncSession, course_id: int, from_date: date | None = None,
                         to_date: date | None = None) -> list[StudentQuizAnswer]:
    """Everyone's answers in the course, by matric no. For lecturers only."""
    return await _answers(db, await _taken(db, course_id=course_id, from_date=from_date, to_date=to_date))


# ── graded scores (FR-621) ───────────────────────────────────────────────────

async def _scores(db: AsyncSession, taken: list[_Taken]) -> list[GradedScore]:
    given = await _answers_of(db, taken)
    out = []
    for t in taken:
        marks = quiz_results.marks_of(list(given[t.attempt.id].values()), len(t.attempt.layout))
        out.append(GradedScore(
            **t.who, quiz_id=t.quiz.id, quiz_title=t.quiz.title, date=t.attempt.submitted_at.date(),
            submitted_at=t.attempt.submitted_at, score=marks.score, max_score=marks.max_score,
            percent=marks.percent, pending_count=marks.pending_count))
    return out


async def student_graded_scores(db: AsyncSession, student_id: int, course_id: int | None = None, *,
                                audience: Audience, from_date: date | None = None,
                                to_date: date | None = None) -> list[GradedScore]:
    """The student's graded quizzes, oldest first. A quiz they didn't take has no row."""
    _check_audience(audience)
    taken = await _taken(db, student_id=student_id, course_id=course_id, quiz_type="graded", from_date=from_date,
                         to_date=to_date)
    return await _scores(db, [t for t in taken if audience == "lecturer" or _released_to_student(t.quiz)[0]])


async def course_graded_scores(db: AsyncSession, course_id: int, from_date: date | None = None,
                               to_date: date | None = None) -> list[GradedScore]:
    """Everyone's graded quizzes in the course, by matric no, then oldest first. For lecturers only."""
    return await _scores(db, await _taken(db, course_id=course_id, quiz_type="graded", from_date=from_date,
                                          to_date=to_date))


# ── topics (FR-621, FR-702) ──────────────────────────────────────────────────

def _topics(answers: list[StudentQuizAnswer]) -> list[TopicResult]:
    groups: dict[tuple, list[StudentQuizAnswer]] = defaultdict(list)
    for a in answers:
        groups[a.matric_no, a.student_id, a.course_code, a.course_id, a.quiz_type, a.topic is None, a.topic or ""
               ].append(a)
    out = []
    for key in sorted(groups):
        rows = groups[key]
        first, pending = rows[0], sum(a.pending for a in rows)
        correct, graded = sum(1 for a in rows if a.correct), len(rows) - pending
        out.append(TopicResult(
            **_who(first.student_id, first.matric_no, first.name, first.course_id, first.course_code),
            quiz_type=first.quiz_type, topic=first.topic, question_count=len(rows),
            answered_count=sum(a.answered for a in rows), correct_count=correct, pending_count=pending,
            correct_rate=round(correct / graded, 3) if graded else None))
    return out


async def student_topic_results(db: AsyncSession, student_id: int, course_id: int | None = None, *,
                                audience: Audience, from_date: date | None = None,
                                to_date: date | None = None) -> list[TopicResult]:
    """The student's `student_answers` by course, quiz type and topic."""
    return _topics(await student_answers(db, student_id, course_id, audience=audience, from_date=from_date,
                                         to_date=to_date))


async def course_topic_results(db: AsyncSession, course_id: int, from_date: date | None = None,
                               to_date: date | None = None) -> list[TopicResult]:
    """Everyone's answers in the course by student, quiz type and topic. For lecturers only."""
    return _topics(await course_answers(db, course_id, from_date, to_date))


# ── game participation (FR-621, FR-702) ──────────────────────────────────────

async def _participation(db: AsyncSession, *, course_id: int | None = None, student_id: int | None = None,
                         from_date: date | None = None, to_date: date | None = None) -> list[GameParticipation]:
    _check_range(from_date, to_date)
    played_on = cast(func.max(QuizAttempt.submitted_at), Date)
    games_stmt = (select(Quiz.id, Quiz.title, Quiz.course_id, played_on)
                  .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
                  .where(Quiz.type == "game", QuizAttempt.status == "submitted")
                  .group_by(Quiz.id).having(*_in_range(played_on, from_date, to_date))
                  .order_by(func.max(QuizAttempt.submitted_at), Quiz.id))
    students_stmt = (select(Student.id, Student.matric_no, User.name, Course.id, Course.code)
                     .join(User, User.id == Student.user_id).join(Enrollment, Enrollment.student_id == Student.id)
                     .join(ClassOccurrence, ClassOccurrence.id == Enrollment.occurrence_id)
                     .join(Course, Course.id == ClassOccurrence.course_id)
                     .distinct().order_by(Student.matric_no, Student.id, Course.code, Course.id))
    if course_id is not None:
        games_stmt = games_stmt.where(Quiz.course_id == course_id)
        students_stmt = students_stmt.where(Course.id == course_id)
    if student_id is not None:
        students_stmt = students_stmt.where(Student.id == student_id)
    games = (await db.execute(games_stmt)).all()
    if not games:
        return []
    of_games = QuizAttempt.quiz_id.in_([game_id for game_id, *_ in games])
    players = {(quiz_id, sid) for quiz_id, sid in (await db.execute(
        select(QuizAttempt.quiz_id, QuizAttempt.student_id)
        .where(of_games, QuizAttempt.status == "submitted"))).all()}
    asked: dict[int, set[int]] = defaultdict(set)
    answered: dict[tuple[int, int], list[bool]] = defaultdict(list)
    for quiz_id, sid, question_id, correct in (await db.execute(
            select(QuizAttempt.quiz_id, QuizAttempt.student_id, QuizAnswer.question_id, QuizAnswer.correct)
            .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
            .where(of_games, QuizAttempt.status == "submitted"))).all():
        asked[quiz_id].add(question_id)
        answered[quiz_id, sid].append(bool(correct))
    return [GameParticipation(
        **_who(*student), quiz_id=quiz_id, quiz_title=title, date=day, played=(quiz_id, student[0]) in players,
        questions_asked=len(asked[quiz_id]), questions_answered=len(answered[quiz_id, student[0]]),
        correct_count=sum(answered[quiz_id, student[0]]))
        for student in (await db.execute(students_stmt)).all()
        for quiz_id, title, game_course_id, day in games if game_course_id == student[3]]


async def student_game_participation(db: AsyncSession, student_id: int, course_id: int | None = None,
                                     from_date: date | None = None, to_date: date | None = None
                                     ) -> list[GameParticipation]:
    """One row per game played in the student's courses, by course, then oldest first."""
    return await _participation(db, student_id=student_id, course_id=course_id, from_date=from_date, to_date=to_date)


async def course_game_participation(db: AsyncSession, course_id: int, from_date: date | None = None,
                                    to_date: date | None = None) -> list[GameParticipation]:
    """One row per enrolled student and game played in the course, by matric no. For lecturers only."""
    return await _participation(db, course_id=course_id, from_date=from_date, to_date=to_date)
