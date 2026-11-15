"""Quiz question generation + draft lifecycle + publish (FR-601..FR-605, FR-211, S30/S31).

POST   /lecturer/courses/{course_id}/quizzes/generate   draft questions (S30)
GET    /lecturer/quizzes/drafts?course_id=                list draft questions (S31)
PUT    /lecturer/quizzes/questions/{id}                  edit a draft (S31)
POST   /lecturer/quizzes/questions/{id}/approve          approve a draft (S31)
DELETE /lecturer/quizzes/questions/{id}                  soft-delete a draft (S31)
POST   /lecturer/quizzes                                 publish a quiz; emits quiz.published (S31, FR-211)

Only approved questions can go into a quiz (server-enforced). Publish calls
`notify.emit(..., priority="important")` to the lecturer; channels are not used in tests.
"""


from fastapi import APIRouter, Depends, HTTPException, Query, status
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.class_ import ClassOccurrence
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt
from app.models.user import Lecturer, User
from app.schemas.quiz import (
    CreateQuizQuestionRequest,
    EditQuizQuestionRequest,
    GenerateQuizRequest,
    PublishDraftQuizRequest,
    PublishQuizRequest,
    QuickAddRequest,
    QuizAttemptResultOut,
    QuizAttemptSummaryOut,
    QuizOut,
    QuizQuestionOut,
    SaveQuizDraftRequest,
    ScoreShortAnswerIn,
    SuggestScoreOut,
    UpdateQuizDraftRequest,
)
from app.services.notify import emit
from app.services.quiz_grading import (
    get_attempt_result,
    list_quiz_attempts,
    list_unscored_short_answers,
    score_short_answer,
    suggest_score,
)
from app.services.quiz_service import generate_questions, quick_add_quiz

router = APIRouter(tags=["quizzes"])

_lecturer = require_role("lecturer")


async def _lecturer_for_actor(db: AsyncSession, actor: User) -> Lecturer:
    lecturer = (await db.execute(select(Lecturer).where(Lecturer.user_id == actor.id))).scalar_one_or_none()
    if not lecturer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecturer profile not found")
    return lecturer


async def _course_accessible(db: AsyncSession, lecturer: Lecturer, course_id: int) -> bool:
    """NFR-04: the lecturer teaches at least one occurrence of the course."""
    return await db.scalar(
        select(ClassOccurrence.id).where(
            ClassOccurrence.course_id == course_id,
            ClassOccurrence.lecturer_id == lecturer.id,
        ).limit(1)
    ) is not None


# ── S30: generate draft questions ───────────────────────────────────────────

@router.post("/lecturer/courses/{course_id}/quizzes/generate",
             response_model=list[QuizQuestionOut], status_code=status.HTTP_201_CREATED)
async def generate_quiz_questions(
    course_id: int,
    body: GenerateQuizRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Draft `count` questions of `type`/`level` from the selected materials (FR-601/602/603)."""
    lecturer = await _lecturer_for_actor(db, actor)

    course_exists = await db.scalar(select(ClassOccurrence.id).where(ClassOccurrence.course_id == course_id).limit(1))
    if not course_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if not await _course_accessible(db, lecturer, course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")

    try:
        questions = await generate_questions(
            course_id=course_id,
            material_ids=body.material_ids,
            qtype=body.type,
            level=body.level,
            count=body.count,
        )
    except Exception as exc:  # LLM errors surface as HTTP via the service's own handlers
        from app.services.kb.llm import LLMMalformedOutput, LLMUnavailable
        if isinstance(exc, LLMMalformedOutput):
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
        if isinstance(exc, LLMUnavailable):
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
        raise
    return [QuizQuestionOut.model_validate(q) for q in questions]


# ── S31: draft question lifecycle ───────────────────────────────────────────

@router.get("/lecturer/quizzes/drafts", response_model=list[QuizQuestionOut])
async def list_draft_questions(
    course_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Draft (and approved) questions for a course the lecturer teaches (FR-604)."""
    lecturer = await _lecturer_for_actor(db, actor)
    if not await _course_accessible(db, lecturer, course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    result = await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.status.in_(("draft", "approved")),
        ).order_by(QuizQuestion.created_at.desc())
    )
    return [QuizQuestionOut.model_validate(q) for q in result.scalars().all()]


@router.put("/lecturer/quizzes/questions/{question_id}", response_model=QuizQuestionOut)
async def edit_draft_question(
    question_id: int,
    body: EditQuizQuestionRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Edit a draft question (only draft, only the lecturer's course) (FR-604)."""
    lecturer = await _lecturer_for_actor(db, actor)
    q = await db.get(QuizQuestion, question_id)
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    if not await _course_accessible(db, lecturer, q.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    if q.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft questions can be edited")

    if body.question is not None:
        q.question = body.question
    if body.options is not None:
        q.options = body.options
    if body.correct_answer is not None:
        q.correct_answer = body.correct_answer
    if body.suggested_answer is not None:
        q.suggested_answer = body.suggested_answer
    if body.level is not None:
        q.level = body.level
    if body.topic is not None:
        q.topic = body.topic
    await db.commit()
    await db.refresh(q)
    return QuizQuestionOut.model_validate(q)


@router.post("/lecturer/quizzes/questions/{question_id}/approve", response_model=QuizQuestionOut)
async def approve_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Approve a draft question (draft → approved) (FR-604)."""
    lecturer = await _lecturer_for_actor(db, actor)
    q = await db.get(QuizQuestion, question_id)
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    if not await _course_accessible(db, lecturer, q.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    if q.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft questions can be approved")
    q.status = "approved"
    await db.commit()
    await db.refresh(q)
    return QuizQuestionOut.model_validate(q)


@router.delete("/lecturer/quizzes/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Soft-delete a draft question (draft → deleted) (FR-604)."""
    lecturer = await _lecturer_for_actor(db, actor)
    q = await db.get(QuizQuestion, question_id)
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    if not await _course_accessible(db, lecturer, q.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    if q.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft questions can be deleted")
    q.status = "deleted"
    await db.commit()
    return None


# ── S31: publish ────────────────────────────────────────────────────────────

async def _publish_for_course(
    db: AsyncSession, lecturer: Lecturer, course_id: int, questions: list[QuizQuestion],
    body: PublishQuizRequest, clone: bool,
) -> Quiz:
    """Create one published quiz for `course_id` from `questions`.

    When `clone` (publishing to an additional course), copies of the questions are
    created in the target course first.
    """
    if clone:
        copies = []
        for q in questions:
            copies.append(QuizQuestion(
                course_id=course_id, type=q.type, question=q.question,
                options=q.options, correct_answer=q.correct_answer,
                suggested_answer=q.suggested_answer, level=q.level,
                source_material_id=q.source_material_id, topic=q.topic,
                status="approved",
            ))
        db.add_all(copies)
        await db.flush()
        questions = copies

    quiz = Quiz(
        course_id=course_id,
        title=body.title,
        time_limit_minutes=body.time_limit_minutes,
        opens_at=body.opens_at,
        closes_at=body.closes_at,
        attempts_allowed=body.attempts_allowed,
        review_visible=body.review_visible,
        status="published",
        created_by=lecturer.id,
    )
    db.add(quiz)
    await db.flush()
    for q in questions:
        q.quiz_id = quiz.id
    return quiz


@router.post("/lecturer/quizzes", response_model=list[QuizOut], status_code=status.HTTP_201_CREATED)
async def publish_quiz(
    body: PublishQuizRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Publish approved questions as a quiz (FR-605), optionally to several courses at
    once (S35: one quiz per course — the question copies appear in each class).
    Emits quiz.published to the lecturer."""
    lecturer = await _lecturer_for_actor(db, actor)

    questions = (await db.execute(
        select(QuizQuestion).where(QuizQuestion.id.in_(body.question_ids))
    )).scalars().all()
    if len(questions) != len(body.question_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more questions not found")

    course_ids = {q.course_id for q in questions}
    if len(course_ids) != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All questions must belong to the same course")
    course_id = course_ids.pop()
    if not await _course_accessible(db, lecturer, course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    if any(q.status != "approved" for q in questions):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only approved questions can be published")
    if any(q.quiz_id is not None for q in questions):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A question is already in a quiz")

    extra = [c for c in dict.fromkeys(body.course_ids) if c != course_id]
    for c in extra:
        if not await _course_accessible(db, lecturer, c):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"You do not teach course {c}")

    quizzes = [await _publish_for_course(db, lecturer, course_id, questions, body, clone=False)]
    for c in extra:
        quizzes.append(await _publish_for_course(db, lecturer, c, questions, body, clone=True))

    await db.commit()
    for quiz in quizzes:
        await db.refresh(quiz)
        # FR-211: publish emits an important-priority notification to the lecturer.
        await emit(
            event="quiz.published",
            user_ids=[lecturer.user_id],
            payload={"quiz_id": quiz.id, "course_id": quiz.course_id},
            priority="important",
        )

    return [
        QuizOut(
            id=q.id, course_id=q.course_id, title=q.title,
            time_limit_minutes=q.time_limit_minutes, opens_at=q.opens_at,
            closes_at=q.closes_at, attempts_allowed=q.attempts_allowed,
            review_visible=q.review_visible, status=q.status,
            created_by=q.created_by, created_at=q.created_at,
            question_count=len(questions),
        )
        for q in quizzes
    ]


# ── S35: quiz list / draft sets / manual questions / quick-add ──────────────

@router.get("/lecturer/courses/{course_id}/quizzes", response_model=list[QuizOut])
async def list_course_quizzes(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """All quizzes (draft, published, closed) for a course the lecturer teaches."""
    lecturer = await _lecturer_for_actor(db, actor)
    if not await _course_accessible(db, lecturer, course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    rows = (await db.execute(
        select(Quiz).where(Quiz.course_id == course_id).order_by(Quiz.created_at.desc())
    )).scalars().all()
    out = []
    for q in rows:
        qcount = await db.scalar(
            select(sa.func.count(QuizQuestion.id)).where(
                QuizQuestion.quiz_id == q.id, QuizQuestion.status != "deleted"
            )
        )
        acount = await db.scalar(
            select(sa.func.count(QuizAttempt.id)).where(QuizAttempt.quiz_id == q.id)
        )
        out.append(QuizOut(
            id=q.id, course_id=q.course_id, title=q.title,
            time_limit_minutes=q.time_limit_minutes, opens_at=q.opens_at,
            closes_at=q.closes_at, attempts_allowed=q.attempts_allowed,
            review_visible=q.review_visible, status=q.status,
            created_by=q.created_by, created_at=q.created_at,
            question_count=qcount or 0, attempt_count=acount or 0,
        ))
    return out


async def _draft_quiz_out(db: AsyncSession, q: Quiz) -> QuizOut:
    qcount = await db.scalar(
        select(sa.func.count(QuizQuestion.id)).where(
            QuizQuestion.quiz_id == q.id, QuizQuestion.status != "deleted"
        )
    )
    return QuizOut(
        id=q.id, course_id=q.course_id, title=q.title,
        time_limit_minutes=q.time_limit_minutes, opens_at=q.opens_at,
        closes_at=q.closes_at, attempts_allowed=q.attempts_allowed,
        review_visible=q.review_visible, status=q.status,
        created_by=q.created_by, created_at=q.created_at,
        question_count=qcount or 0,
    )


@router.post("/lecturer/quizzes/draft", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
async def save_quiz_draft(
    body: SaveQuizDraftRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Save a draft quiz set: links the (draft or approved) questions into one quiz with
    status=draft so it can be reviewed and published later (QuizList "Draft" button)."""
    lecturer = await _lecturer_for_actor(db, actor)
    questions = (await db.execute(
        select(QuizQuestion).where(QuizQuestion.id.in_(body.question_ids))
    )).scalars().all()
    if len(questions) != len(body.question_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more questions not found")
    course_ids = {q.course_id for q in questions}
    if len(course_ids) != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All questions must belong to the same course")
    if not await _course_accessible(db, lecturer, course_ids.pop()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    if any(q.quiz_id is not None for q in questions):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A question is already in a quiz")

    quiz = Quiz(
        course_id=questions[0].course_id,
        title=body.title,
        time_limit_minutes=body.time_limit_minutes,
        opens_at=body.opens_at,
        closes_at=body.closes_at,
        attempts_allowed=body.attempts_allowed,
        review_visible=body.review_visible,
        status="draft",
        created_by=lecturer.id,
    )
    db.add(quiz)
    await db.flush()
    for q in questions:
        q.quiz_id = quiz.id
    await db.commit()
    await db.refresh(quiz)
    return await _draft_quiz_out(db, quiz)


@router.put("/lecturer/quizzes/{quiz_id}", response_model=QuizOut)
async def update_quiz_draft(
    quiz_id: int,
    body: UpdateQuizDraftRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Edit a draft quiz's details (title, window, time limit, attempts, review)."""
    lecturer = await _lecturer_for_actor(db, actor)
    quiz = await db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    if not await _course_accessible(db, lecturer, quiz.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    if quiz.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft quizzes can be edited")
    for field in ("title", "time_limit_minutes", "opens_at", "closes_at",
                  "attempts_allowed", "review_visible"):
        value = getattr(body, field)
        if value is not None:
            setattr(quiz, field, value)
    await db.commit()
    await db.refresh(quiz)
    return await _draft_quiz_out(db, quiz)


@router.post("/lecturer/quizzes/{quiz_id}/publish", response_model=list[QuizOut])
async def publish_draft_quiz(
    quiz_id: int,
    body: PublishDraftQuizRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Publish a draft quiz — to its own course, plus clones of itself to any other
    courses listed in `course_ids` (publish to one or more classes)."""
    lecturer = await _lecturer_for_actor(db, actor)
    quiz = await db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    if not await _course_accessible(db, lecturer, quiz.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    if quiz.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft quizzes can be published")
    questions = (await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.quiz_id == quiz.id, QuizQuestion.status != "deleted"
        )
    )).scalars().all()
    if not questions:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The draft quiz has no questions")

    extra = [c for c in dict.fromkeys(body.course_ids) if c != quiz.course_id]
    for c in extra:
        if not await _course_accessible(db, lecturer, c):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"You do not teach course {c}")

    created = [quiz]
    quiz.status = "published"
    for c in extra:
        copies = []
        for q in questions:
            copies.append(QuizQuestion(
                course_id=c, type=q.type, question=q.question,
                options=q.options, correct_answer=q.correct_answer,
                suggested_answer=q.suggested_answer, level=q.level,
                source_material_id=q.source_material_id, topic=q.topic,
                status="approved",
            ))
        db.add_all(copies)
        await db.flush()
        clone = Quiz(
            course_id=c, title=quiz.title,
            time_limit_minutes=quiz.time_limit_minutes,
            opens_at=quiz.opens_at, closes_at=quiz.closes_at,
            attempts_allowed=quiz.attempts_allowed, review_visible=quiz.review_visible,
            status="published", created_by=lecturer.id,
        )
        db.add(clone)
        await db.flush()
        for copy in copies:
            copy.quiz_id = clone.id
        created.append(clone)

    await db.commit()
    for q in created:
        await db.refresh(q)
        await emit(
            event="quiz.published",
            user_ids=[lecturer.user_id],
            payload={"quiz_id": q.id, "course_id": q.course_id},
            priority="important",
        )
    return [await _draft_quiz_out(db, q) for q in created]


@router.post("/lecturer/quizzes/questions", response_model=QuizQuestionOut,
             status_code=status.HTTP_201_CREATED)
async def create_quiz_question(
    body: CreateQuizQuestionRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Add a question manually (review/edit/add flow, S35)."""
    lecturer = await _lecturer_for_actor(db, actor)
    if not await _course_accessible(db, lecturer, body.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    if body.type == "mcq" and not body.options:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="An MCQ needs options")
    q = QuizQuestion(
        course_id=body.course_id, type=body.type, question=body.question,
        options=body.options, correct_answer=body.correct_answer,
        suggested_answer=body.suggested_answer, level=body.level,
        topic=body.topic, status="draft",
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return QuizQuestionOut.model_validate(q)


@router.post("/lecturer/courses/{course_id}/quizzes/quick-add",
             response_model=QuizOut, status_code=status.HTTP_201_CREATED)
async def quick_add_quiz_endpoint(
    course_id: int,
    body: QuickAddRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """One-sentence quiz builder (S35): the lecturer types e.g. "create 5 mcq, 2 short
    answer, duration 15min, valid two days from now"; the LLM parses it, drafts the
    questions from the selected materials and saves everything as one draft quiz."""
    lecturer = await _lecturer_for_actor(db, actor)
    if not await _course_accessible(db, lecturer, course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    try:
        quiz, _ = await quick_add_quiz(
            db, course_id, body.prompt, body.material_ids, body.level, lecturer.id,
        )
    except ValueError as exc:
        if str(exc) == "no_questions_generated":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Could not draft any questions — check the counts in your instruction")
        raise
    except Exception as exc:
        from app.services.kb.llm import LLMMalformedOutput, LLMUnavailable
        if isinstance(exc, LLMMalformedOutput):
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
        if isinstance(exc, LLMUnavailable):
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
        raise
    return await _draft_quiz_out(db, quiz)


# ── S33: short-answer scoring + AI suggestion (FR-609, FR-610, FR-611) ───────

@router.get("/lecturer/quizzes/{quiz_id}/attempts",
            response_model=list[QuizAttemptSummaryOut])
async def list_quiz_attempts_endpoint(
    quiz_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Attempts for a quiz the lecturer teaches (NFR-04)."""
    lecturer = await _lecturer_for_actor(db, actor)
    rows = await list_quiz_attempts(db, quiz_id, lecturer)
    return [QuizAttemptSummaryOut.model_validate(r) for r in rows]


@router.get("/lecturer/quizzes/attempts/{attempt_id}/answers",
            response_model=list[dict])
async def list_unscored_answers(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Unscored short answers on an attempt (FR-609)."""
    lecturer = await _lecturer_for_actor(db, actor)
    return await list_unscored_short_answers(db, attempt_id, lecturer)


@router.post("/lecturer/quizzes/attempts/{attempt_id}/answers/{answer_id}/score",
             response_model=dict)
async def score_short_answer_endpoint(
    attempt_id: int,
    answer_id: int,
    body: ScoreShortAnswerIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Lecturer scores a short answer (FR-609)."""
    lecturer = await _lecturer_for_actor(db, actor)
    answer = await score_short_answer(db, answer_id, body.score, lecturer)
    return {
        "answer_id": answer.id,
        "question_id": answer.question_id,
        "score": answer.score,
        "auto_graded": answer.auto_graded,
    }


@router.post("/lecturer/quizzes/attempts/{attempt_id}/answers/{answer_id}/suggest-score",
             response_model=SuggestScoreOut)
async def suggest_score_endpoint(
    attempt_id: int,
    answer_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """AI-suggested score for a short answer (FR-610). Malformed LLM output → 502,
    provider unavailable → 503 (S33 spec)."""
    lecturer = await _lecturer_for_actor(db, actor)
    # verify access via the attempt
    await list_unscored_short_answers(db, attempt_id, lecturer)
    try:
        return await suggest_score(db, answer_id)
    except Exception as exc:
        from app.services.kb.llm import LLMMalformedOutput, LLMUnavailable
        if isinstance(exc, LLMMalformedOutput):
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
        if isinstance(exc, LLMUnavailable):
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
        raise


@router.get("/student/quizzes/attempts/{attempt_id}/result",
            response_model=QuizAttemptResultOut)
async def get_quiz_attempt_result(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("student")),
):
    """Student result for an attempt, visible only after grading complete (FR-611)."""
    from app.models.user import Student
    student = (await db.execute(
        select(Student).where(Student.user_id == actor.id)
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    return await get_attempt_result(db, attempt_id, student.id)
