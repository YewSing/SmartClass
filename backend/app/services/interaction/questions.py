"""Live questions (FR-503–FR-506) — S31.

Students ask (optionally anonymously) and upvote once each; the lecturer marks a question answered,
pins it or hides it (each hide/unhide audited, NFR-06). Every write goes through
`sessions.require_open`, so nothing changes once the class or the interaction has closed (409).

Anonymity (FR-504, FR-713): the asker's `student_id` is stored for class totals only. `to_out` is
the single place a question becomes a response: an anonymous question has no `author_name` for
anyone, no response carries a student or user id, and `mine` is computed per caller (true only for
the asker). Audit values hold only the changed flag.

Order (FR-505): pinned first, then most upvotes, then oldest first (id breaks ties). Students never
see hidden questions (and can't upvote them: 404); the lecturer sees them flagged `hidden`.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import false, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Question, QuestionVote
from app.models.user import Student, User
from app.schemas.interaction import QuestionModerate, QuestionOut
from app.services.audit_service import write_log
from app.services.interaction import events, live, sessions
from app.services.interaction.sessions import Member

AUDIT_TARGET = "m5_question"


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")


def _students_only(member: Member) -> None:
    if member.role != sessions.ROLE_STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can do this")


def to_out(q: Question, member: Member, *, upvotes: int, upvoted_by_me: bool,
           author_name: str | None) -> QuestionOut:
    """The one place a Question is turned into a response for `member`."""
    return QuestionOut(
        id=q.id, attendance_session_id=q.attendance_session_id, text=q.text, anonymous=q.anonymous,
        author_name=None if q.anonymous else author_name,
        mine=member.student_id is not None and q.student_id == member.student_id,
        upvotes=upvotes, upvoted_by_me=upvoted_by_me,
        answered=q.answered_at is not None, answered_at=q.answered_at,
        pinned=q.pinned, hidden=q.hidden, created_at=q.created_at)


def _vote_counts():
    return (select(QuestionVote.question_id, func.count().label("n"))
            .group_by(QuestionVote.question_id).subquery())


async def _load(db: AsyncSession, member: Member, attendance_session_id: int,
                question_id: int | None = None) -> list[QuestionOut]:
    votes = _vote_counts()
    my_vote = (select(QuestionVote.id).where(QuestionVote.question_id == Question.id,
                                             QuestionVote.student_id == member.student_id)
               .exists() if member.student_id is not None else false())
    upvotes = func.coalesce(votes.c.n, 0)
    stmt = (select(Question, upvotes.label("upvotes"), my_vote.label("mine_vote"), User.name)
            .outerjoin(votes, votes.c.question_id == Question.id)
            .outerjoin(Student, Student.id == Question.student_id)
            .outerjoin(User, User.id == Student.user_id)
            .where(Question.attendance_session_id == attendance_session_id))
    if question_id is not None:
        stmt = stmt.where(Question.id == question_id)
    if member.role != sessions.ROLE_LECTURER:
        stmt = stmt.where(Question.hidden.is_(False))
    stmt = stmt.order_by(Question.pinned.desc(), upvotes.desc(), Question.created_at, Question.id)
    rows = (await db.execute(stmt)).all()
    return [to_out(q, member, upvotes=n, upvoted_by_me=bool(mine), author_name=name)
            for q, n, mine, name in rows]


async def list_questions(db: AsyncSession, member: Member, attendance_session_id: int) -> list[QuestionOut]:
    return await _load(db, member, attendance_session_id)


async def _one(db: AsyncSession, member: Member, attendance_session_id: int, question_id: int) -> QuestionOut:
    found = await _load(db, member, attendance_session_id, question_id)
    if not found:
        raise _not_found()
    return found[0]


async def _locked_question(db: AsyncSession, attendance_session_id: int, question_id: int) -> Question:
    q = (await db.execute(
        select(Question).where(Question.id == question_id,
                               Question.attendance_session_id == attendance_session_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if q is None:
        raise _not_found()
    return q


async def ask(db: AsyncSession, member: Member, attendance_session_id: int,
              text: str, anonymous: bool) -> QuestionOut:
    _students_only(member)
    await sessions.require_open(db, attendance_session_id)
    q = Question(attendance_session_id=attendance_session_id, student_id=member.student_id,
                 text=text, anonymous=anonymous, pinned=False, hidden=False,
                 created_at=sessions.clock())
    db.add(q)
    await db.flush()
    events.record(db, events.QUESTION_ASKED, attendance_session_id, member.student_id, q.created_at,
                  ref_id=q.id, anonymous=anonymous)
    await db.flush()
    live.changed(db, attendance_session_id, live.QUESTIONS)
    return await _one(db, member, attendance_session_id, q.id)


async def upvote(db: AsyncSession, member: Member, attendance_session_id: int, question_id: int) -> QuestionOut:
    """Upvote once (a repeat changes nothing). Not your own question (409), not a hidden one (404)."""
    _students_only(member)
    await sessions.require_open(db, attendance_session_id)
    q = await db.scalar(select(Question).where(Question.id == question_id,
                                               Question.attendance_session_id == attendance_session_id))
    if q is None or q.hidden:
        raise _not_found()
    if q.student_id == member.student_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="You can't upvote your own question")
    now = sessions.clock()
    added = (await db.execute(
        insert(QuestionVote)
        .values(question_id=q.id, student_id=member.student_id, created_at=now)
        .on_conflict_do_nothing(constraint="uq_m5_question_votes_question_student")
        .returning(QuestionVote.id))).scalar_one_or_none()
    if added is not None:                                   # a repeat upvote isn't a new event
        events.record(db, events.QUESTION_UPVOTED, attendance_session_id, member.student_id, now,
                      ref_id=q.id)
        await db.flush()
        live.changed(db, attendance_session_id, live.QUESTIONS)
    return await _one(db, member, attendance_session_id, q.id)


async def moderate(db: AsyncSession, actor: User, member: Member, attendance_session_id: int,
                   question_id: int, change: QuestionModerate) -> QuestionOut:
    """Lecturer marks answered / pins / hides (FR-506). Each hide or unhide is audited."""
    sessions.require_lecturer(member)
    await sessions.require_open(db, attendance_session_id)
    q = await _locked_question(db, attendance_session_id, question_id)
    if change.answered is not None and change.answered != (q.answered_at is not None):
        q.answered_at = sessions.clock() if change.answered else None
    if change.pinned is not None:
        q.pinned = change.pinned
    if change.hidden is not None and change.hidden != q.hidden:
        await write_log(db, actor.id, "INTERACTION_QUESTION_HIDDEN" if change.hidden
                        else "INTERACTION_QUESTION_UNHIDDEN", AUDIT_TARGET, q.id,
                        {"hidden": q.hidden}, {"hidden": change.hidden})
        q.hidden = change.hidden
    await db.flush()
    live.changed(db, attendance_session_id, live.QUESTIONS)
    return await _one(db, member, attendance_session_id, q.id)
