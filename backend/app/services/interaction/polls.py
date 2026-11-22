"""Live polls (FR-507–FR-509) — S32.

The lecturer creates a poll (2–6 options, single or multiple choice) as a `draft`, starts it
(`open`, students get a `poll.started` notification after the commit) and closes it. While it is
open each student has one vote, a set of options (exactly one for single choice), which they may
replace until the poll closes. Every write goes through `sessions.require_open` (409 once the class
or the interaction has closed). A poll that is still `open` in the table while the interaction is
closed is reported as `closed` (nobody can vote then).

Results (FR-509): the lecturer always sees the counts live. Students see counts only while the
lecturer has `show_results` on; otherwise `votes`/`total_voters` are null. Students never see
drafts (404). No response says who voted for what; `my_option_ids` is the caller's own vote only.
Not graded or scored (FR-513).

Concurrency: a vote share-locks the poll row (the lecturer's close takes an update lock, so a vote
can't land after the close) and takes a transaction advisory lock per (poll, student), so two
requests from one student can't leave two options on a single-choice poll.
"""
from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import after_commit
from app.models.class_ import ClassOccurrence, Course
from app.models.interaction import Poll, PollOption, PollVote
from app.models.session import AttendanceSession
from app.models.user import User
from app.schemas.interaction import PollCreate, PollOptionOut, PollOut
from app.services import notify
from app.services.interaction import events, sessions
from app.services.interaction.sessions import Member
from app.services.notifications import announcements

EVENT_STARTED = "poll.started"


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poll not found")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _effective_status(poll: Poll, interaction_open: bool) -> str:
    if poll.status == "open" and not interaction_open:
        return "closed"
    return poll.status


async def _load(db: AsyncSession, member: Member, attendance_session_id: int, *,
                interaction_open: bool, poll_id: int | None = None) -> list[PollOut]:
    stmt = select(Poll).where(Poll.attendance_session_id == attendance_session_id)
    if poll_id is not None:
        stmt = stmt.where(Poll.id == poll_id)
    if member.role != sessions.ROLE_LECTURER:
        stmt = stmt.where(Poll.status != "draft")
    polls = list((await db.execute(
        stmt.order_by(Poll.created_at.desc(), Poll.id.desc())
        .execution_options(populate_existing=True))).scalars())
    if not polls:
        return []
    ids = [p.id for p in polls]
    options: dict[int, list[PollOption]] = defaultdict(list)
    for o in (await db.execute(select(PollOption).where(PollOption.poll_id.in_(ids))
                               .order_by(PollOption.poll_id, PollOption.position))).scalars():
        options[o.poll_id].append(o)
    counts = dict((await db.execute(
        select(PollVote.option_id, func.count()).where(PollVote.poll_id.in_(ids))
        .group_by(PollVote.option_id))).all())
    voters = dict((await db.execute(
        select(PollVote.poll_id, func.count(func.distinct(PollVote.student_id)))
        .where(PollVote.poll_id.in_(ids)).group_by(PollVote.poll_id))).all())
    mine: dict[int, list[int]] = defaultdict(list)
    if member.student_id is not None:
        for pid, oid in (await db.execute(
                select(PollVote.poll_id, PollVote.option_id)
                .where(PollVote.poll_id.in_(ids), PollVote.student_id == member.student_id))).all():
            mine[pid].append(oid)

    out = []
    for p in polls:
        visible = member.role == sessions.ROLE_LECTURER or p.show_results
        opts = options[p.id]
        order = {o.id: o.position for o in opts}
        out.append(PollOut(
            id=p.id, attendance_session_id=p.attendance_session_id, question=p.question,
            multiple=p.multiple, status=_effective_status(p, interaction_open),
            show_results=p.show_results,
            options=[PollOptionOut(id=o.id, text=o.text, votes=counts.get(o.id, 0) if visible else None)
                     for o in opts],
            total_voters=voters.get(p.id, 0) if visible else None,
            my_option_ids=sorted(mine[p.id], key=lambda oid: order.get(oid, 0)),
            created_at=p.created_at, started_at=p.started_at, closed_at=p.closed_at))
    return out


async def list_polls(db: AsyncSession, member: Member, attendance_session_id: int, *,
                     interaction_open: bool) -> list[PollOut]:
    return await _load(db, member, attendance_session_id, interaction_open=interaction_open)


async def _one(db: AsyncSession, member: Member, attendance_session_id: int, poll_id: int,
               *, interaction_open: bool = True) -> PollOut:
    found = await _load(db, member, attendance_session_id, interaction_open=interaction_open,
                        poll_id=poll_id)
    if not found:
        raise _not_found()
    return found[0]


async def _locked_poll(db: AsyncSession, attendance_session_id: int, poll_id: int, *,
                       share: bool = False) -> Poll:
    poll = (await db.execute(
        select(Poll).where(Poll.id == poll_id, Poll.attendance_session_id == attendance_session_id)
        .with_for_update(read=share).execution_options(populate_existing=True))).scalar_one_or_none()
    if poll is None:
        raise _not_found()
    return poll


async def create(db: AsyncSession, actor: User, member: Member, attendance_session_id: int,
                 body: PollCreate) -> PollOut:
    sessions.require_lecturer(member)
    await sessions.require_open(db, attendance_session_id)
    poll = Poll(attendance_session_id=attendance_session_id, question=body.question,
                multiple=body.multiple, status="draft", show_results=body.show_results,
                created_by_user_id=actor.id, created_at=sessions.clock())
    db.add(poll)
    await db.flush()
    db.add_all([PollOption(poll_id=poll.id, position=i, text=t) for i, t in enumerate(body.options)])
    await db.flush()
    return await _one(db, member, attendance_session_id, poll.id)


async def _notify_started(db: AsyncSession, attendance_session_id: int, poll_id: int) -> None:
    """Queue `poll.started` to the class's active enrolled students for after the commit."""
    session = await db.get(AttendanceSession, attendance_session_id)
    if session is None or session.occurrence_id is None:
        return
    student_user_ids = await announcements.recipients(db, session.occurrence_id)
    if not student_user_ids:
        return
    course_code = await db.scalar(
        select(Course.code).join(ClassOccurrence, ClassOccurrence.course_id == Course.id)
        .where(ClassOccurrence.id == session.occurrence_id))
    payload = {"attendance_session_id": attendance_session_id, "poll_id": poll_id,
               "course_code": course_code}

    async def _after() -> None:
        await notify.emit(EVENT_STARTED, student_user_ids, payload)

    after_commit(db, _after)


async def start(db: AsyncSession, member: Member, attendance_session_id: int, poll_id: int) -> PollOut:
    """Draft → open (409 from any other state)."""
    sessions.require_lecturer(member)
    await sessions.require_open(db, attendance_session_id)
    poll = await _locked_poll(db, attendance_session_id, poll_id)
    if poll.status != "draft":
        raise _conflict("This poll has already been started")
    poll.status, poll.started_at = "open", sessions.clock()
    await db.flush()
    await _notify_started(db, attendance_session_id, poll.id)
    return await _one(db, member, attendance_session_id, poll.id)


async def close(db: AsyncSession, member: Member, attendance_session_id: int, poll_id: int) -> PollOut:
    """Open → closed (a repeat changes nothing; a draft can't be closed: 409)."""
    sessions.require_lecturer(member)
    await sessions.require_open(db, attendance_session_id)
    poll = await _locked_poll(db, attendance_session_id, poll_id)
    if poll.status == "draft":
        raise _conflict("This poll hasn't been started")
    if poll.status == "open":
        poll.status, poll.closed_at = "closed", sessions.clock()
        await db.flush()
    return await _one(db, member, attendance_session_id, poll.id)


async def set_show_results(db: AsyncSession, member: Member, attendance_session_id: int,
                           poll_id: int, show_results: bool) -> PollOut:
    sessions.require_lecturer(member)
    await sessions.require_open(db, attendance_session_id)
    poll = await _locked_poll(db, attendance_session_id, poll_id)
    poll.show_results = show_results
    await db.flush()
    return await _one(db, member, attendance_session_id, poll.id)


async def vote(db: AsyncSession, member: Member, attendance_session_id: int, poll_id: int,
               option_ids: list[int]) -> PollOut:
    """Replace the student's vote on an open poll (FR-508)."""
    if member.role != sessions.ROLE_STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can vote")
    await sessions.require_open(db, attendance_session_id)
    poll = await _locked_poll(db, attendance_session_id, poll_id, share=True)
    if poll.status == "draft":
        raise _not_found()
    if poll.status != "open":
        raise _conflict("This poll is closed")
    chosen = list(dict.fromkeys(option_ids))
    if len(chosen) != len(option_ids):
        raise _invalid("Choose each option at most once")
    if not poll.multiple and len(chosen) != 1:
        raise _invalid("Choose exactly one option")
    valid = set((await db.execute(select(PollOption.id).where(PollOption.poll_id == poll.id))).scalars())
    if not set(chosen) <= valid:
        raise _invalid("Unknown option for this poll")

    await db.execute(select(func.pg_advisory_xact_lock(
        func.hashtextextended(f"m5_poll_vote:{poll.id}:{member.student_id}", 0))))
    await db.execute(delete(PollVote).where(PollVote.poll_id == poll.id,
                                            PollVote.student_id == member.student_id))
    now = sessions.clock()
    db.add_all([PollVote(poll_id=poll.id, option_id=oid, student_id=member.student_id, created_at=now)
                for oid in chosen])
    events.record(db, events.POLL_VOTED, attendance_session_id, member.student_id, now, ref_id=poll.id)
    await db.flush()
    return await _one(db, member, attendance_session_id, poll.id)
