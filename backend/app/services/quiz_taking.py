"""Taking quizzes + auto-grade (FR-606, FR-607, FR-608, S32).

- `list_student_quizzes`: published quizzes of enrolled courses only.
- `start_attempt`: one attempt per student per quiz (second → 409), only within the open
  window (outside → 403), server-side deadline = started_at + time limit.
- `submit_attempt`: MCQ answers auto-graded on submission; short answers left unscored;
  submission after expiry rejected (403).
- `auto_submit_expired_attempts`: background check — started attempts past their deadline
  are auto-submitted (status auto_submitted, score from answers so far).
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import ClassOccurrence, Enrollment
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt, QuizAnswer


def _now() -> datetime:
    return datetime.now()


async def list_student_quizzes(db: AsyncSession, student_id: int) -> list[dict]:
    """Published quizzes of courses the student is enrolled in (FR-607)."""
    # occurrences the student is enrolled in
    enrolled_occ = select(Enrollment.occurrence_id).where(Enrollment.student_id == student_id)
    result = await db.execute(
        select(Quiz).where(
            Quiz.status == "published",
            Quiz.course_id.in_(
                select(ClassOccurrence.course_id).where(
                    ClassOccurrence.id.in_(enrolled_occ)
                )
            ),
        )
    )
    quizzes = result.scalars().all()
    # existing attempts
    attempts = {
        a.quiz_id: a
        for a in (
            await db.execute(
                select(QuizAttempt).where(
                    QuizAttempt.student_id == student_id,
                    QuizAttempt.quiz_id.in_([q.id for q in quizzes]),
                )
            )
        ).scalars().all()
    }
    out = []
    for q in quizzes:
        a = attempts.get(q.id)
        out.append({
            "id": q.id, "course_id": q.course_id, "title": q.title,
            "time_limit_minutes": q.time_limit_minutes, "opens_at": q.opens_at,
            "closes_at": q.closes_at, "status": q.status,
            "has_attempt": a is not None,
            "attempt_id": a.id if a else None,
            "deadline": a.deadline if a else None,
        })
    return out


async def start_attempt(db: AsyncSession, quiz_id: int, student_id: int) -> QuizAttempt:
    """Start one attempt; 409 if already attempted, 403 outside the open window."""
    quiz = await db.get(Quiz, quiz_id)
    if not quiz or quiz.status != "published":
        raise ValueError("quiz_not_published")
    enrolled = await db.scalar(
        select(Enrollment.id).join(
            ClassOccurrence, ClassOccurrence.id == Enrollment.occurrence_id
        ).where(
            Enrollment.student_id == student_id,
            ClassOccurrence.course_id == quiz.course_id,
        ).limit(1)
    )
    if not enrolled:
        raise ValueError("not_enrolled")
    existing = await db.scalar(
        select(QuizAttempt.id).where(
            QuizAttempt.quiz_id == quiz_id, QuizAttempt.student_id == student_id
        ).limit(1)
    )
    if existing:
        raise ValueError("already_attempted")
    now = _now()
    if quiz.opens_at and now < quiz.opens_at:
        raise ValueError("not_yet_open")
    if quiz.closes_at and now > quiz.closes_at:
        raise ValueError("quiz_closed")
    deadline = now + timedelta(minutes=quiz.time_limit_minutes or 0)
    attempt = QuizAttempt(
        quiz_id=quiz_id, student_id=student_id,
        started_at=now, deadline=deadline, status="started",
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt


async def submit_attempt(
    db: AsyncSession, attempt_id: int, answers: list[dict], student_id: int
) -> QuizAttempt:
    """Submit an attempt: window check, one attempt, MCQ auto-grade, short answers unscored."""
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.student_id != student_id:
        raise ValueError("attempt_not_found")
    if attempt.status != "started":
        raise ValueError("already_submitted")
    if attempt.deadline and _now() > attempt.deadline:
        raise ValueError("expired")

    by_question = {a["question_id"]: a.get("answer") for a in answers}
    total = 0.0
    for qid, answer in by_question.items():
        question = await db.get(QuizQuestion, qid)
        if not question or question.quiz_id is not None and question.quiz_id != attempt.quiz_id:
            continue
        auto_graded = False
        score = None
        if question.type == "mcq":
            auto_graded = True
            score = 1.0 if (answer is not None and answer == question.correct_answer) else 0.0
            total += score
        db.add(QuizAnswer(
            attempt_id=attempt_id, question_id=qid, answer=answer,
            score=score, auto_graded=auto_graded,
        ))
    attempt.submitted_at = _now()
    attempt.status = "submitted"
    attempt.score = total
    await db.commit()
    await db.refresh(attempt)
    return attempt


async def auto_submit_expired_attempts(db: AsyncSession) -> int:
    """Background check: auto-submit started attempts past their deadline."""
    now = _now()
    result = await db.execute(
        select(QuizAttempt).where(
            QuizAttempt.status == "started",
            QuizAttempt.deadline < now,
        )
    )
    attempts = result.scalars().all()
    count = 0
    for attempt in attempts:
        attempt.status = "auto_submitted"
        attempt.auto_submitted = True
        attempt.submitted_at = now
        # score from existing answers (queried explicitly: the relationship is lazy and
        # touching it after the loop would need a greenlet)
        scores = (await db.execute(
            select(QuizAnswer.score).where(
                QuizAnswer.attempt_id == attempt.id,
                QuizAnswer.score.is_not(None),
            )
        )).scalars().all()
        attempt.score = sum(scores)
        count += 1
    if count:
        await db.commit()
    return count
