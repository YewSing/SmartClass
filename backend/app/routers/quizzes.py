"""Lecturer quizzes (FR-605, FR-606) — S40; AI drafts (FR-601–FR-603) — S41; draft review (FR-604) — S42;
publishing (FR-606) — S43; short-answer scores (FR-616, FR-617) — S45; results (FR-618, FR-619) — S46.

Lecturers who teach a class of the course only (403 for everyone else and for unknown ids).
"""
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User
from app.schemas.quiz import (
    QuestionApprovalIn,
    QuestionIn,
    QuestionOrderIn,
    QuestionRegenerateIn,
    QuizCreate,
    QuizDetailOut,
    QuizDraftIn,
    QuizListOut,
    QuizRefineIn,
    QuizReleaseIn,
    QuizReleaseOut,
    QuizResultsOut,
    QuizUpdate,
    ScoreIn,
    ShortAnswerListOut,
    ShortAnswerOut,
    ShortAnswerState,
)
from app.services import quiz_grading, quiz_publish, quiz_questions, quiz_release, quiz_results, quiz_store
from app.services.kb.llm import LLMMalformedOutput, LLMUnavailable
from app.services.quiz import draft, refine

log = logging.getLogger(__name__)

router = APIRouter(prefix="/lecturer/quizzes", tags=["quizzes"])

_lecturer = require_role("lecturer")


@contextmanager
def _llm_errors(expected: str) -> Iterator[None]:
    """502 when the AI's reply can't be used, 503 when the AI can't be reached (NFR-55)."""
    try:
        yield
    except LLMMalformedOutput as exc:
        log.warning("quiz AI: unusable LLM reply (%s)", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=f"The AI didn't return {expected}") from exc
    except LLMUnavailable as exc:
        log.warning("quiz AI: LLM unavailable (%s)", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=(
            "AI drafting is unavailable right now. Try again later, or write the questions by hand.")) from exc


@router.get("", response_model=QuizListOut)
async def list_quizzes(
    course_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """The quizzes of the lecturer's courses, newest first, without their questions."""
    return QuizListOut(quizzes=await quiz_store.list_quizzes(db, actor, course_id))


@router.post("", response_model=QuizDetailOut, status_code=status.HTTP_201_CREATED)
async def create_quiz(body: QuizCreate, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """A new, empty draft. A game quiz always gets a per-question timer."""
    return await quiz_store.create(db, actor, body)


@router.post("/draft", response_model=QuizDetailOut, status_code=status.HTTP_201_CREATED)
async def draft_quiz(body: QuizDraftIn, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """A draft quiz written by the AI from the lecturer's prompt and the course materials, with the
    settings read from the prompt. Every question is unapproved. Nothing is saved when it fails:
    502 the AI's reply can't be used, 503 the AI can't be reached (NFR-55: the lecturer can still
    write questions by hand)."""
    with _llm_errors("a usable quiz. Try again, ask for fewer questions, or write them by hand."):
        return await draft.create_draft(db, actor, body)


@router.get("/{quiz_id}", response_model=QuizDetailOut)
async def read_quiz(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """The quiz with its questions, answers included."""
    return await quiz_store.detail(db, await quiz_store.get_quiz(db, actor, quiz_id))


@router.patch("/{quiz_id}", response_model=QuizDetailOut)
async def update_quiz(quiz_id: int, body: QuizUpdate, db: AsyncSession = Depends(get_db),
                      actor: User = Depends(_lecturer)):
    """Change a draft's settings (409 once published, closed or attempted)."""
    return await quiz_store.update(db, actor, quiz_id, body)


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """Delete a draft and its questions (409 once published, closed or attempted)."""
    await quiz_store.delete(db, actor, quiz_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── publishing (FR-606) — S43 ────────────────────────────────────────────────

@router.post("/{quiz_id}/publish", response_model=QuizDetailOut)
async def publish_quiz(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """Publish a draft (409 otherwise) with its approved questions and notify the course's students.
    422 when no question is approved or the closing time has passed."""
    return await quiz_publish.publish(db, actor, quiz_id)


@router.post("/{quiz_id}/unpublish", response_model=QuizDetailOut)
async def unpublish_quiz(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """Turn a published or closed quiz back into a draft (409 for a draft, or once it has attempts)."""
    return await quiz_publish.unpublish(db, actor, quiz_id)


@router.post("/{quiz_id}/close", response_model=QuizDetailOut)
async def close_quiz(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """Close a published quiz now (409 otherwise)."""
    return await quiz_publish.close(db, actor, quiz_id)


# ── draft review (FR-604) — S42. Drafts without attempts only (409) ──────────

@router.post("/{quiz_id}/questions", response_model=QuizDetailOut, status_code=status.HTTP_201_CREATED)
async def add_question(quiz_id: int, body: QuestionIn, db: AsyncSession = Depends(get_db),
                       actor: User = Depends(_lecturer)):
    """Add a question at the end, unapproved."""
    return await quiz_questions.add(db, actor, quiz_id, body)


# "order" and "approval" come before "{question_id}", which would take them as an id
@router.put("/{quiz_id}/questions/order", response_model=QuizDetailOut)
async def reorder_questions(quiz_id: int, body: QuestionOrderIn, db: AsyncSession = Depends(get_db),
                            actor: User = Depends(_lecturer)):
    """Put every question of the quiz in a new order (409 when they aren't the quiz's questions any more)."""
    return await quiz_questions.reorder(db, actor, quiz_id, body.question_ids)


@router.put("/{quiz_id}/questions/approval", response_model=QuizDetailOut)
async def approve_questions(quiz_id: int, body: QuestionApprovalIn, db: AsyncSession = Depends(get_db),
                            actor: User = Depends(_lecturer)):
    """Approve or unapprove the questions named. Only approved questions can be published."""
    return await quiz_questions.set_approval(db, actor, quiz_id, body.question_ids, body.approved)


@router.put("/{quiz_id}/questions/{question_id}", response_model=QuizDetailOut)
async def edit_question(quiz_id: int, question_id: int, body: QuestionIn, db: AsyncSession = Depends(get_db),
                        actor: User = Depends(_lecturer)):
    """Replace a question's whole content. A changed question is unapproved again."""
    return await quiz_questions.edit(db, actor, quiz_id, question_id, body)


@router.delete("/{quiz_id}/questions/{question_id}", response_model=QuizDetailOut)
async def delete_question(quiz_id: int, question_id: int, db: AsyncSession = Depends(get_db),
                          actor: User = Depends(_lecturer)):
    """Delete a question; the others close the gap."""
    return await quiz_questions.delete(db, actor, quiz_id, question_id)


@router.post("/{quiz_id}/questions/{question_id}/regenerate", response_model=QuizDetailOut)
async def regenerate_question(quiz_id: int, question_id: int, body: QuestionRegenerateIn,
                              db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """The AI writes another question of the same type in its place, unapproved. Errors as for a draft,
    and 409 when the question was changed meanwhile."""
    with _llm_errors("a usable question. Try again, or edit it by hand."):
        return await refine.regenerate(db, actor, quiz_id, question_id, body)


@router.post("/{quiz_id}/refine", response_model=QuizDetailOut)
async def refine_quiz(quiz_id: int, body: QuizRefineIn, db: AsyncSession = Depends(get_db),
                      actor: User = Depends(_lecturer)):
    """The AI changes, adds or removes questions as the prompt asks; the others stay as they are. What it
    writes is unapproved. Errors as for a draft, and 409 when the draft was changed meanwhile."""
    with _llm_errors("usable changes. Try again, ask for fewer changes, or edit the questions by hand."):
        return await refine.refine(db, actor, quiz_id, body)


# ── short-answer scores (FR-616, FR-617) — S45. Graded quizzes only (409) ────

@router.get("/{quiz_id}/short-answers", response_model=ShortAnswerListOut)
async def list_short_answers(quiz_id: int, state: Optional[ShortAnswerState] = None,
                             db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """The submitted short answers with their scores: all, or those still pending, flagged (the AI wasn't
    confident) or graded."""
    return await quiz_grading.list_short_answers(db, actor, quiz_id, state)


@router.put("/{quiz_id}/short-answers/{answer_id}/score", response_model=ShortAnswerOut)
async def change_short_answer_score(quiz_id: int, answer_id: int, body: ScoreIn, db: AsyncSession = Depends(get_db),
                                    actor: User = Depends(_lecturer)):
    """Change a short answer's score, with feedback. The score stands: the AI doesn't grade it again."""
    return await quiz_grading.change_score(db, actor, quiz_id, answer_id, body)


# ── results (FR-618, FR-619) — S46. Graded quizzes only (409) ────────────────

@router.get("/{quiz_id}/results", response_model=QuizResultsOut)
async def read_results(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """Submissions, score distribution, average, and per question how the class did."""
    return await quiz_results.lecturer_results(db, actor, quiz_id)


@router.put("/{quiz_id}/release", response_model=QuizReleaseOut)
async def release_results(quiz_id: int, body: QuizReleaseIn, db: AsyncSession = Depends(get_db),
                          actor: User = Depends(_lecturer)):
    """Choose what students see: marks, answers, both or neither. 409 for a draft, and while the quiz can
    still be taken (except neither)."""
    return await quiz_release.set_release(db, actor, quiz_id, body)
