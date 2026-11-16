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
from typing import Optional

import sqlalchemy as sa
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
    attempt_rows = (await db.execute(
        select(QuizAttempt).where(
            QuizAttempt.student_id == student_id,
            QuizAttempt.quiz_id.in_([q.id for q in quizzes]),
        ).order_by(QuizAttempt.started_at.desc())
    )).scalars().all()
    attempts_by_quiz: dict[int, list[QuizAttempt]] = {}
    for a in attempt_rows:
        attempts_by_quiz.setdefault(a.quiz_id, []).append(a)

    out = []
    for q in quizzes:
        ats = attempts_by_quiz.get(q.id, [])
        latest_attempt = ats[0] if ats else None
        used = len(ats)
        out.append({
            "id": q.id, "course_id": q.course_id, "title": q.title,
            "time_limit_minutes": q.time_limit_minutes, "opens_at": q.opens_at,
            "closes_at": q.closes_at, "status": q.status,
            "attempts_allowed": q.attempts_allowed, "attempts_used": used,
            "review_visible": q.review_visible,
            "has_attempt": latest_attempt is not None,
            "attempt_id": latest_attempt.id if latest_attempt else None,
            "deadline": latest_attempt.deadline if latest_attempt else None,
        })
    return out


async def get_quiz_for_taking(db: AsyncSession, quiz_id: int, student_id: int) -> dict:
    """Quiz + its questions (no answers) for a student about to take it (FR-606).

    Enforced: published quiz, enrolled student, inside the open window. Questions are
    returned without correct_answer/suggested_answer/level — the student never sees them.
    """
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
    now = _now()
    if quiz.opens_at and now < quiz.opens_at:
        raise ValueError("not_yet_open")
    if quiz.closes_at and now > quiz.closes_at:
        raise ValueError("quiz_closed")
    questions = (await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.quiz_id == quiz_id,
            QuizQuestion.status.in_(("approved", "draft")),
        ).order_by(QuizQuestion.id)
    )).scalars().all()
    # Check if student has an existing active attempt for this quiz to return saved progress
    active_attempt = (await db.execute(
        select(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.student_id == student_id,
            QuizAttempt.status == "started",
        ).order_by(QuizAttempt.started_at.desc())
    )).scalars().first()

    existing_answers = {}
    if active_attempt:
        ans_rows = (await db.execute(
            select(QuizAnswer).where(QuizAnswer.attempt_id == active_attempt.id)
        )).scalars().all()
        existing_answers = {a.question_id: a.answer for a in ans_rows if a.answer is not None}

    return {
        "id": quiz.id,
        "course_id": quiz.course_id,
        "title": quiz.title,
        "time_limit_minutes": quiz.time_limit_minutes,
        "opens_at": quiz.opens_at,
        "closes_at": quiz.closes_at,
        "attempts_allowed": quiz.attempts_allowed,
        "review_visible": quiz.review_visible,
        "active_attempt_id": active_attempt.id if active_attempt else None,
        "active_deadline": active_attempt.deadline if active_attempt else None,
        "saved_answers": existing_answers,
        "questions": [
            {
                "id": q.id,
                "type": q.type,
                "question": q.question,
                "options": q.options,
                "score": getattr(q, "score", 1.0) or 1.0,
            }
            for q in questions
        ],
    }


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
    now = _now()
    used = (await db.execute(
        select(sa.func.count(QuizAttempt.id)).where(
            QuizAttempt.quiz_id == quiz_id, QuizAttempt.student_id == student_id
        )
    )).scalar_one()
    if used >= (quiz.attempts_allowed or 1):
        raise ValueError("already_attempted")
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


async def save_attempt_progress(
    db: AsyncSession, attempt_id: int, answers: list[dict], student_id: int
) -> int:
    """Save in-progress answers without finalizing or grading."""
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.student_id != student_id:
        raise ValueError("attempt_not_found")
    if attempt.status != "started":
        raise ValueError("already_submitted")
    if attempt.deadline and _now() > attempt.deadline:
        await _auto_submit_single_attempt(db, attempt)
        raise ValueError("expired")

    by_question = {a["question_id"]: a.get("answer") for a in answers}
    saved_count = 0
    for qid, answer in by_question.items():
        existing = (await db.execute(
            select(QuizAnswer).where(
                QuizAnswer.attempt_id == attempt_id,
                QuizAnswer.question_id == qid,
            )
        )).scalars().first()
        if existing:
            existing.answer = answer
        else:
            db.add(QuizAnswer(
                attempt_id=attempt_id, question_id=qid, answer=answer,
                score=None, auto_graded=False,
            ))
        saved_count += 1
    await db.commit()
    return saved_count


async def _auto_submit_single_attempt(db: AsyncSession, attempt: QuizAttempt) -> None:
    """Auto-submit a single expired attempt, grading any MCQ answers submitted so far."""
    if attempt.status != "started":
        return
    attempt.status = "auto_submitted"
    attempt.auto_submitted = True
    attempt.submitted_at = _now()

    # Get all questions of this quiz to ensure missing questions get an answer row with 0 points
    questions = (await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.quiz_id == attempt.quiz_id,
            QuizQuestion.status.in_(("approved", "draft")),
        )
    )).scalars().all()

    existing_answers = {
        a.question_id: a
        for a in (await db.execute(
            select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id)
        )).scalars().all()
    }

    total = 0.0
    for q in questions:
        q_score = getattr(q, "score", 1.0) or 1.0
        ans_row = existing_answers.get(q.id)
        if ans_row:
            if q.type == "mcq":
                is_correct = _check_mcq_correct(ans_row.answer, q.correct_answer)
                ans_row.score = float(q_score) if is_correct else 0.0
                ans_row.auto_graded = True
                total += ans_row.score
            elif q.type == "short_answer":
                if not ans_row.answer or not str(ans_row.answer).strip():
                    ans_row.score = 0.0
                    ans_row.auto_graded = True
                elif ans_row.score is not None:
                    total += ans_row.score
        else:
            # Unanswered question gets 0.0 score directly (both MCQ and empty short answer)
            db.add(QuizAnswer(
                attempt_id=attempt.id, question_id=q.id, answer=None,
                score=0.0, auto_graded=True,
            ))

    attempt.score = total
    await db.commit()
    await db.refresh(attempt)


def _check_mcq_correct(user_ans: Optional[str], correct_ans: Optional[str]) -> bool:
    """Auto-grade MCQ answers supporting single choice or multiple choices (comma or semicolon separated)."""
    if not user_ans or not correct_ans:
        return False
    # Normalize by splitting on comma/semicolon, trimming and lowercasing
    def _parse_items(s: str) -> set[str]:
        parts = [p.strip().lower() for p in s.replace(";", ",").split(",") if p.strip()]
        return set(parts)

    user_set = _parse_items(user_ans)
    correct_set = _parse_items(correct_ans)
    return bool(user_set and user_set == correct_set)


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
        await _auto_submit_single_attempt(db, attempt)
        raise ValueError("expired")

    # Ensure all questions on this quiz get an answer row (missing/unanswered gets 0.0 for MCQ, None for SA)
    all_questions = (await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.quiz_id == attempt.quiz_id,
            QuizQuestion.status.in_(("approved", "draft")),
        )
    )).scalars().all()

    existing_rows = {
        a.question_id: a
        for a in (await db.execute(
            select(QuizAnswer).where(QuizAnswer.attempt_id == attempt_id)
        )).scalars().all()
    }

    by_question = {a["question_id"]: a.get("answer") for a in answers}
    total = 0.0
    for question in all_questions:
        qid = question.id
        answer = by_question.get(qid)
        ans_row = existing_rows.get(qid)
        auto_graded = False
        score = None
        q_score = getattr(question, "score", 1.0) or 1.0
        if question.type == "mcq":
            auto_graded = True
            is_correct = _check_mcq_correct(answer, question.correct_answer)
            score = float(q_score) if is_correct else 0.0
            total += score
        elif question.type == "short_answer":
            if not answer or not str(answer).strip():
                # Student didn't input any words — directly give 0.0, lecturer no need to review
                auto_graded = True
                score = 0.0

        if ans_row:
            ans_row.answer = answer
            ans_row.score = score
            ans_row.auto_graded = auto_graded
        else:
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
