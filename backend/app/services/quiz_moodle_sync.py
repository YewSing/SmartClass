"""Published quizzes -> Moodle `mod_quiz` (same pattern as attendance_moodle_sync, FR-311).

Rules:
- Publishing a quiz queues it: `moodle_sync_status = "pending"`. The background loop
  creates the quiz in Moodle via `local_smartclass_create_quiz` (a local plugin: Moodle
  core has no WS to create activities), storing `moodle_quiz_id`/`moodle_cmid` and the
  per-question `moodle_question_id`. Any failure makes it `failed` and retries with
  exponential backoff — retries never stop.
- `local_smartclass_quiz_attempts` is read on a schedule for synced quizzes: finished
  Moodle attempts are imported as SmartClass attempts (score, answers) so lecturers can
  grade short answers and students see their results in the app. Students who already
  attempted in the app are skipped (the app attempt wins).
- MCQ questions are created as Moodle multichoice (auto-graded there); short answers as
  essay (manual grading) — imported attempts keep those unscored, so they land in the
  lecturer's "Needs review" queue.
- The sync is "on" when MOODLE_TOKEN is set and MOODLE_QUIZ_SYNC_INTERVAL_SECONDS > 0.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import Course
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAnswer, QuizAttempt
from app.models.user import Student, User
from app.services.kb.moodle_client import MoodleClient, MoodleError

log = logging.getLogger(__name__)

DUE_STATUSES = ("pending", "failed")

_run_lock = asyncio.Lock()
_background: set[asyncio.Task] = set()


class SyncError(Exception):
    """A sync problem worth showing the lecturer (no secrets in the message)."""


def sync_enabled() -> bool:
    return bool(settings.MOODLE_TOKEN) and settings.MOODLE_QUIZ_SYNC_INTERVAL_SECONDS > 0


def retry_delay(attempts: int) -> timedelta:
    seconds = settings.MOODLE_ATTENDANCE_RETRY_BASE_SECONDS * 2 ** max(0, attempts - 1)
    return timedelta(seconds=min(seconds, settings.MOODLE_ATTENDANCE_RETRY_MAX_SECONDS))


def _error_text(exc: Exception) -> str:
    if isinstance(exc, SyncError):
        return str(exc)[:255]
    return exc.__class__.__name__


def queue_quiz(db: AsyncSession, quiz: Quiz) -> None:
    """Mark a published quiz for the next Moodle push."""
    if not sync_enabled() or quiz.status != "published":
        return
    quiz.moodle_sync_status = "pending"
    quiz.moodle_sync_attempts = 0
    quiz.moodle_sync_next_at = None
    quiz.moodle_sync_error = None
    db.flush()


def sync_in_background(quiz_id: int) -> None:
    """After the caller's transaction commits, push (and then pull) in a background task."""
    if not sync_enabled():
        return

    async def _run() -> None:
        try:
            async with AsyncSessionLocal() as db:
                await run_one(db, quiz_id)
        except Exception:  # pragma: no cover - logged, never raised into the request
            log.exception("quiz moodle sync for quiz %s failed", quiz_id)

    task = asyncio.get_running_loop().create_task(_run())
    _background.add(task)
    task.add_done_callback(_background.discard)


async def run_one(db: AsyncSession, quiz_id: int) -> None:
    """Push the quiz to Moodle, then import any attempts already there."""
    quiz = await db.get(Quiz, quiz_id)
    if quiz is None or quiz.status != "published":
        return
    async with MoodleClient(settings.MOODLE_URL, settings.MOODLE_TOKEN) as client:
        try:
            if quiz.moodle_sync_status != "synced":
                await push_quiz(db, quiz, client)
            await db.commit()
            imported = await pull_attempts(db, quiz, client)
            await db.commit()
            if imported:
                log.info("imported %s Moodle attempt(s) into quiz %s", imported, quiz_id)
        except (MoodleError, SyncError) as exc:
            quiz = await db.get(Quiz, quiz_id)
            if quiz is not None:
                quiz.moodle_sync_status = "failed"
                quiz.moodle_sync_attempts += 1
                quiz.moodle_sync_next_at = datetime.now() + retry_delay(quiz.moodle_sync_attempts)
                quiz.moodle_sync_error = _error_text(exc)
                await db.commit()
        except Exception:
            await db.rollback()
            raise


async def push_quiz(db: AsyncSession, quiz: Quiz, client: MoodleClient) -> None:
    """Create the quiz activity in Moodle (idempotent: existing quizzes are left alone)."""
    if quiz.moodle_quiz_id is not None:
        return
    course = await db.get(Course, quiz.course_id)
    if course.moodle_course_id is None:
        raise SyncError(f"Course {course.code} is not in Moodle")

    questions = (await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.quiz_id == quiz.id, QuizQuestion.status != "deleted",
        ).order_by(QuizQuestion.id)
    )).scalars().all()
    payload = [{
        "index": i,
        "type": q.type,
        "question": q.question,
        "options": q.options or [],
        "correct_answer": q.correct_answer,
        "suggested_answer": q.suggested_answer,
        "score": float(q.score),
    } for i, q in enumerate(questions)]

    result = await client.call(
        "local_smartclass_create_quiz",
        courseid=course.moodle_course_id,
        name=quiz.title or f"SmartClass quiz {quiz.id}",
        timeopen=int(quiz.opens_at.timestamp()) if quiz.opens_at else 0,
        timeclose=int(quiz.closes_at.timestamp()) if quiz.closes_at else 0,
        timelimit=int(quiz.time_limit_minutes or 0),
        attempts=quiz.attempts_allowed,
        questions=payload,
    )
    quiz.moodle_quiz_id = int(result["quiz_id"])
    quiz.moodle_cmid = int(result["cmid"])
    for row in result.get("questions", []):
        q = questions[int(row["index"])]
        q.moodle_question_id = int(row["questionid"])
    quiz.moodle_sync_status = "synced"
    quiz.moodle_synced_at = datetime.now()
    quiz.moodle_sync_error = None
    await db.flush()


async def pull_attempts(db: AsyncSession, quiz: Quiz, client: MoodleClient) -> int:
    """Import finished Moodle attempts into SmartClass. Returns how many were new."""
    if quiz.moodle_quiz_id is None:
        return 0
    data = await client.call("local_smartclass_quiz_attempts", quizid=quiz.moodle_quiz_id)
    imported = 0
    known_attempt_ids = set(await db.scalars(
        select(QuizAttempt.moodle_attempt_id).where(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.moodle_attempt_id.is_not(None),
        )))

    existing_by_student = {}
    for a in await db.scalars(select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id)):
        if a.moodle_attempt_id is None:
            existing_by_student.setdefault(a.student_id, a)

    questions = (await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.quiz_id == quiz.id, QuizQuestion.status != "deleted",
        ).order_by(QuizQuestion.id)
    )).scalars().all()
    by_moodle_qid = {q.moodle_question_id: q for q in questions if q.moodle_question_id}

    for att in data.get("attempts", []):
        if att["attempt_id"] in known_attempt_ids:
            continue
        moodle_user_id = int(att["userid"])
        row = (await db.execute(
            select(Student.id, User.id)
            .join(User, User.id == Student.user_id)
            .where(User.moodle_user_id == moodle_user_id)
            .limit(1)
        )).first()
        if row is None:
            continue  # a Moodle user SmartClass doesn't know
        student_id = row[0]

        if student_id in existing_by_student:
            # The student attempted in the app: keep the app attempt's data.
            continue
        started = datetime.fromtimestamp(att["timestart"]) if att["timestart"] else datetime.now()
        finished = datetime.fromtimestamp(att["timefinish"]) if att["timefinish"] else started
        total_max = att["max_grade"] or 0
        score = None
        if total_max and att["state"] == "finished":
            score = round((att["sumgrades"] / total_max) * 100.0, 1)

        attempt = QuizAttempt(
            quiz_id=quiz.id, student_id=student_id,
            started_at=started, deadline=finished,
            submitted_at=finished, status="submitted",
            score=score, auto_submitted=False, moodle_attempt_id=att["attempt_id"],
        )
        db.add(attempt)
        await db.flush()
        for resp in att.get("responses", []):
            q = by_moodle_qid.get(resp["questionid"])
            if q is None:
                continue
            graded = q.type == "mcq" and resp["response"] is not None
            db.add(QuizAnswer(
                attempt_id=attempt.id, question_id=q.id,
                answer=resp["response"],
                score=float(q.score) if graded else None,
                auto_graded=graded,
            ))
        imported += 1
    await db.flush()
    if imported:
        quiz.moodle_synced_at = datetime.now()
    return imported


async def run_due(db: AsyncSession) -> None:
    """Push every due quiz, then refresh attempts for the synced ones."""
    now = datetime.now()
    due = (await db.execute(
        select(Quiz.id).where(
            Quiz.status == "published",
            Quiz.moodle_sync_status.in_(DUE_STATUSES),
            Quiz.moodle_sync_next_at.is_(None) | (Quiz.moodle_sync_next_at <= now),
        )
    )).scalars().all()
    for quiz_id in due:
        await run_one(db, quiz_id)

    if due:
        return  # freshly pushed quizzes were pulled by run_one already
    synced = (await db.execute(
        select(Quiz.id).where(
            Quiz.status == "published", Quiz.moodle_sync_status == "synced",
        ).limit(50)
    )).scalars().all()
    async with MoodleClient(settings.MOODLE_URL, settings.MOODLE_TOKEN) as client:
        for quiz_id in synced:
            quiz = await db.get(Quiz, quiz_id)
            if quiz is None:
                continue
            try:
                imported = await pull_attempts(db, quiz, client)
                if imported:
                    log.info("imported %s Moodle attempt(s) into quiz %s", imported, quiz_id)
            except (MoodleError, SyncError) as exc:
                log.warning("attempt pull for quiz %s failed: %s", quiz_id, exc)
    await db.commit()


async def quiz_moodle_sync_loop() -> None:
    """Background loop: push pending quizzes, pull new Moodle attempts (NFR-20)."""
    if not sync_enabled():
        return
    while True:
        try:
            async with _run_lock:
                async with AsyncSessionLocal() as db:
                    await run_due(db)
        except Exception:
            log.exception("quiz moodle sync loop iteration failed")
        await asyncio.sleep(settings.MOODLE_QUIZ_SYNC_INTERVAL_SECONDS)
