"""Live quick questions with short text answers (FR-510) — S33.

The lecturer asks a quick question (it is open at once) with an answer length limit
(`max_chars`, default `INTERACTION_QUICK_ANSWER_DEFAULT_CHARS`, at most 500) and closes it when
done. Each student has one answer per quick question and may replace it while it is open. The
lecturer sees every answer as a list with no names; students see only their own answer, never the
others' (anonymous to the class). Every write goes through `sessions.require_open` (409 once the
class or the interaction closed). Not graded (FR-513).
"""
from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.interaction import QUICK_ANSWER_MAX_CHARS, QuickAnswer, QuickQuestion
from app.models.user import User
from app.schemas.interaction import QuickAnswerOut, QuickQuestionCreate, QuickQuestionOut
from app.services.interaction import sessions
from app.services.interaction.sessions import Member


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quick question not found")


async def _load(db: AsyncSession, member: Member, attendance_session_id: int, *,
                interaction_open: bool, qid: int | None = None) -> list[QuickQuestionOut]:
    stmt = select(QuickQuestion).where(QuickQuestion.attendance_session_id == attendance_session_id)
    if qid is not None:
        stmt = stmt.where(QuickQuestion.id == qid)
    rows = list((await db.execute(
        stmt.order_by(QuickQuestion.created_at.desc(), QuickQuestion.id.desc())
        .execution_options(populate_existing=True))).scalars())
    if not rows:
        return []
    ids = [q.id for q in rows]
    lecturer = member.role == sessions.ROLE_LECTURER
    answers: dict[int, list[QuickAnswerOut]] = defaultdict(list)
    mine: dict[int, str] = {}
    if lecturer:
        for a in (await db.execute(
                select(QuickAnswer).where(QuickAnswer.quick_question_id.in_(ids))
                .order_by(QuickAnswer.created_at, QuickAnswer.id)
                .execution_options(populate_existing=True))).scalars():
            answers[a.quick_question_id].append(QuickAnswerOut(id=a.id, text=a.text, created_at=a.created_at))
    elif member.student_id is not None:
        mine = dict((await db.execute(
            select(QuickAnswer.quick_question_id, QuickAnswer.text)
            .where(QuickAnswer.quick_question_id.in_(ids),
                   QuickAnswer.student_id == member.student_id))).all())
    out = []
    for q in rows:
        st = "closed" if q.status == "closed" or not interaction_open else "open"
        out.append(QuickQuestionOut(
            id=q.id, attendance_session_id=q.attendance_session_id, prompt=q.prompt,
            max_chars=q.max_chars, status=st,
            answer_count=len(answers[q.id]) if lecturer else None,
            answers=answers[q.id] if lecturer else None,
            my_answer=mine.get(q.id), created_at=q.created_at, closed_at=q.closed_at))
    return out


async def list_quick(db: AsyncSession, member: Member, attendance_session_id: int, *,
                     interaction_open: bool) -> list[QuickQuestionOut]:
    """Newest first."""
    return await _load(db, member, attendance_session_id, interaction_open=interaction_open)


async def _one(db: AsyncSession, member: Member, attendance_session_id: int, qid: int) -> QuickQuestionOut:
    found = await _load(db, member, attendance_session_id, interaction_open=True, qid=qid)
    if not found:
        raise _not_found()
    return found[0]


async def _locked(db: AsyncSession, attendance_session_id: int, qid: int, *, share: bool) -> QuickQuestion:
    q = (await db.execute(
        select(QuickQuestion).where(QuickQuestion.id == qid,
                                    QuickQuestion.attendance_session_id == attendance_session_id)
        .with_for_update(read=share).execution_options(populate_existing=True))).scalar_one_or_none()
    if q is None:
        raise _not_found()
    return q


async def ask(db: AsyncSession, actor: User, member: Member, attendance_session_id: int,
              body: QuickQuestionCreate) -> QuickQuestionOut:
    sessions.require_lecturer(member)
    await sessions.require_open(db, attendance_session_id)
    limit = body.max_chars or settings.INTERACTION_QUICK_ANSWER_DEFAULT_CHARS
    limit = max(1, min(limit, QUICK_ANSWER_MAX_CHARS))
    q = QuickQuestion(attendance_session_id=attendance_session_id, prompt=body.prompt, max_chars=limit,
                      status="open", created_by_user_id=actor.id, created_at=sessions.clock())
    db.add(q)
    await db.flush()
    return await _one(db, member, attendance_session_id, q.id)


async def close(db: AsyncSession, member: Member, attendance_session_id: int, qid: int) -> QuickQuestionOut:
    """Stop taking answers (idempotent)."""
    sessions.require_lecturer(member)
    await sessions.require_open(db, attendance_session_id)
    q = await _locked(db, attendance_session_id, qid, share=False)
    if q.status == "open":
        q.status, q.closed_at = "closed", sessions.clock()
        await db.flush()
    return await _one(db, member, attendance_session_id, q.id)


async def answer(db: AsyncSession, member: Member, attendance_session_id: int, qid: int,
                 text: str) -> QuickQuestionOut:
    """The student's answer; replaces their earlier one while the quick question is open."""
    if member.role != sessions.ROLE_STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can answer")
    await sessions.require_open(db, attendance_session_id)
    q = await _locked(db, attendance_session_id, qid, share=True)   # close waits for us
    if q.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This quick question is closed")
    if len(text) > q.max_chars:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"An answer can be at most {q.max_chars} characters")
    now = sessions.clock()
    await db.execute(
        insert(QuickAnswer)
        .values(quick_question_id=q.id, student_id=member.student_id, text=text, created_at=now)
        .on_conflict_do_update(constraint="uq_m5_quick_answers_question_student",
                               set_={"text": text, "created_at": now}))
    await db.flush()
    return await _one(db, member, attendance_session_id, q.id)
