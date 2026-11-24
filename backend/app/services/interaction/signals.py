"""Reactions and "I don't understand" (FR-511, FR-512, FR-514, FR-515) — S33, on/off since S38g.

They work like the reactions of an online meeting: a signal is *on* until the student takes it back,
the lecturer clears it, or the class ends. Each row is one stretch of a signal (`created_at` to
`ended_at`, null while on), so nothing is lost for the after-class timeline and Module 7. A student
has at most one reaction and one "I don't understand" on at a time.

- `react` turns a reaction on (another kind replaces it), `cancel_reaction` takes it back. `press` and
  `cancel_press` do the same for "I don't understand", which may carry a topic.
- Turning a signal on is never refused, but within its cooldown
  (`INTERACTION_REACTION_COOLDOWN_SECONDS`, `INTERACTION_CONFUSION_COOLDOWN_SECONDS`, counted from the
  last start) it continues the student's last row instead of adding one, so tapping on and off counts
  once (FR-511, FR-512, FR-517).
- The lecturer sees how many are on now (`active`) and, as history, the presses of the whole class.
  `clear_reactions` / `clear_confusion` lower everyone's. Confusion is aggregates only: never who
  pressed (FR-515).
- Spike rule, after each press (FR-514): when the distinct students whose press in the last
  `INTERACTION_CONFUSION_WINDOW_SECONDS` is still on reach `INTERACTION_CONFUSION_SPIKE_SHARE` of the
  active enrolled students, a spike starts and `confusion.spike` (urgent) goes to the class session's
  lecturer after the commit. While the share stays at or above the threshold the same spike carries
  on (no second notification); a new spike needs a whole window without a press at/above it.

Every write goes through `sessions.require_open` (409 once closed) and runs under a transaction
advisory lock per student (reactions) or per class session (confusion: it also serialises the spike
rule, so two presses can't both start a spike). Nothing is graded (FR-513).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import after_commit
from app.models.class_ import ClassOccurrence, Course
from app.models.interaction import REACTION_KINDS, ConfusionPress, ConfusionSpike, Reaction
from app.models.session import AttendanceSession
from app.models.user import Lecturer
from app.schemas.interaction import (
    ConfusionAck,
    ConfusionBucket,
    ConfusionOut,
    ConfusionTopicCount,
    MySignalsOut,
    ReactionAck,
    ReactionBucket,
    ReactionCountsOut,
)
from app.services import notify
from app.services.interaction import events, live, sessions
from app.services.interaction.sessions import Member
from app.services.notifications import announcements

EVENT_SPIKE = "confusion.spike"
REACTION_BUCKET_SECONDS = 300       # the after-class reaction timeline


def _students_only(member: Member, what: str) -> None:
    if member.role != sessions.ROLE_STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Only students can {what}")


async def _lock(db: AsyncSession, key: str) -> None:
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))


async def _class_open(db: AsyncSession, attendance_session_id: int) -> bool:
    return await db.scalar(select(AttendanceSession.status).where(
        AttendanceSession.id == attendance_session_id)) == "open"


async def _last(db: AsyncSession, model, attendance_session_id: int, student_id: int | None):
    """The student's newest row (the active one, if any, is always the newest)."""
    return (await db.execute(
        select(model).where(model.attendance_session_id == attendance_session_id, model.student_id == student_id)
        .order_by(model.ended_at.is_(None).desc(), model.created_at.desc(), model.id.desc()).limit(1)
        .execution_options(populate_existing=True))).scalar_one_or_none()


def _within(row, now: datetime, seconds: int) -> bool:
    return row is not None and (now - row.created_at).total_seconds() < seconds


async def _end_all(db: AsyncSession, model, attendance_session_id: int) -> int:
    result = await db.execute(
        update(model).where(model.attendance_session_id == attendance_session_id, model.ended_at.is_(None))
        .values(ended_at=sessions.clock()).execution_options(synchronize_session=False))
    return result.rowcount


async def _cancel(db: AsyncSession, member: Member, attendance_session_id: int, model, topic: str) -> None:
    """Take back the student's own signal (nothing on: nothing happens)."""
    result = await db.execute(
        update(model).where(model.attendance_session_id == attendance_session_id,
                            model.student_id == member.student_id, model.ended_at.is_(None))
        .values(ended_at=sessions.clock()).execution_options(synchronize_session=False))
    if result.rowcount:
        live.changed(db, attendance_session_id, topic)


async def my_signals(db: AsyncSession, member: Member, attendance_session_id: int) -> MySignalsOut:
    """What the calling student has on right now."""
    _students_only(member, "read their signals")
    reaction = press_ = None
    if await _class_open(db, attendance_session_id):
        reaction = await _last(db, Reaction, attendance_session_id, member.student_id)
        press_ = await _last(db, ConfusionPress, attendance_session_id, member.student_id)
    confused = press_ is not None and press_.ended_at is None
    return MySignalsOut(
        attendance_session_id=attendance_session_id,
        reaction=reaction.kind if reaction is not None and reaction.ended_at is None else None,
        confused=confused, topic=press_.topic if confused else None)


# ── reactions (FR-511) ───────────────────────────────────────────────────────

async def react(db: AsyncSession, member: Member, attendance_session_id: int, kind: str) -> ReactionAck:
    _students_only(member, "react")
    await sessions.require_open(db, attendance_session_id)
    await _lock(db, f"m5_reaction:{attendance_session_id}:{member.student_id}")
    now = sessions.clock()
    row = await _last(db, Reaction, attendance_session_id, member.student_id)
    on = row is not None and row.ended_at is None
    if on and row.kind == kind:
        return ReactionAck(kind=kind, created_at=row.created_at)        # already on
    if _within(row, now, settings.INTERACTION_REACTION_COOLDOWN_SECONDS):
        row.kind, row.ended_at = kind, None                             # a change of mind, not a new one
    else:
        if on:
            row.ended_at = now
            await db.flush()
        row = Reaction(attendance_session_id=attendance_session_id, student_id=member.student_id,
                       kind=kind, created_at=now)
        db.add(row)
        events.record(db, events.REACTION, attendance_session_id, member.student_id, now)
    await db.flush()
    live.changed(db, attendance_session_id, live.REACTIONS)
    return ReactionAck(kind=kind, created_at=row.created_at)


async def cancel_reaction(db: AsyncSession, member: Member, attendance_session_id: int) -> None:
    _students_only(member, "react")
    await sessions.require_open(db, attendance_session_id)
    await _lock(db, f"m5_reaction:{attendance_session_id}:{member.student_id}")
    await _cancel(db, member, attendance_session_id, Reaction, live.REACTIONS)


async def clear_reactions(db: AsyncSession, member: Member, attendance_session_id: int) -> None:
    """The lecturer lowers every reaction that is on."""
    sessions.require_lecturer(member)
    await sessions.require_open(db, attendance_session_id)
    if await _end_all(db, Reaction, attendance_session_id):
        live.changed(db, attendance_session_id, live.REACTIONS)
        live.changed(db, attendance_session_id, live.SIGNALS)


async def reaction_counts(db: AsyncSession, member: Member, attendance_session_id: int,
                          interaction_status: str) -> ReactionCountsOut:
    sessions.require_lecturer(member)
    of_class = Reaction.attendance_session_id == attendance_session_id
    found = dict((await db.execute(
        select(Reaction.kind, func.count()).where(of_class).group_by(Reaction.kind))).all())
    on = {}
    if await _class_open(db, attendance_session_id):
        on = dict((await db.execute(
            select(Reaction.kind, func.count()).where(of_class, Reaction.ended_at.is_(None))
            .group_by(Reaction.kind))).all())
    counts = {k: int(found.get(k, 0)) for k in REACTION_KINDS}
    active = {k: int(on.get(k, 0)) for k in REACTION_KINDS}
    return ReactionCountsOut(attendance_session_id=attendance_session_id, status=interaction_status,
                             active=active, active_total=sum(active.values()),
                             counts=counts, total=sum(counts.values()))


async def reaction_people(db: AsyncSession, attendance_session_id: int) -> tuple[dict[str, int], int]:
    """How many different students used each reaction, and how many used any."""
    of_class = Reaction.attendance_session_id == attendance_session_id
    who = func.count(func.distinct(Reaction.student_id))
    found = dict((await db.execute(select(Reaction.kind, who).where(of_class).group_by(Reaction.kind))).all())
    anyone = int(await db.scalar(select(who).where(of_class)) or 0)
    return {k: int(found.get(k, 0)) for k in REACTION_KINDS}, anyone


async def reaction_timeline(db: AsyncSession, session: AttendanceSession) -> list[ReactionBucket]:
    """Per 5 minutes, how many students had each reaction on (a reaction that stayed on is in every
    bucket it spans). Oldest first, empty buckets left out."""
    rows = (await db.execute(
        select(Reaction.id, Reaction.student_id, Reaction.kind, Reaction.created_at, Reaction.ended_at)
        .where(Reaction.attendance_session_id == session.id))).all()
    until = sessions.clock() if session.status == "open" else session.closed_at
    buckets: dict[datetime, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    step = timedelta(seconds=REACTION_BUCKET_SECONDS)
    for rid, sid, kind, start, end in rows:
        t = _bucket_start(start, REACTION_BUCKET_SECONDS)
        last = max(end or until or start, start)
        while t <= last:
            buckets[t][kind].add(("s", sid) if sid is not None else ("r", rid))
            t += step
    return [ReactionBucket(start=t, counts={k: len(kinds[k]) for k in REACTION_KINDS})
            for t, kinds in sorted(buckets.items())]


# ── confusion (FR-512, FR-514, FR-515) ───────────────────────────────────────

def _window() -> timedelta:
    return timedelta(seconds=max(settings.INTERACTION_CONFUSION_WINDOW_SECONDS, 1))


def spike_reached(students: int, class_size: int) -> bool:
    """True when `students` out of `class_size` reach the configured share (at least one)."""
    if class_size <= 0 or students <= 0:
        return False
    return students >= math.ceil(settings.INTERACTION_CONFUSION_SPIKE_SHARE * class_size - 1e-9)


async def _class_size(db: AsyncSession, session: AttendanceSession) -> int:
    if session.occurrence_id is None:
        return 0
    return len(await announcements.recipients(db, session.occurrence_id))


async def _recent_students(db: AsyncSession, attendance_session_id: int, now: datetime) -> int:
    """Distinct students who pressed within the window and haven't taken it back."""
    return int(await db.scalar(
        select(func.count(func.distinct(ConfusionPress.student_id)))
        .where(ConfusionPress.attendance_session_id == attendance_session_id, ConfusionPress.ended_at.is_(None),
               ConfusionPress.created_at > now - _window(), ConfusionPress.created_at <= now)) or 0)


async def _active_students(db: AsyncSession, attendance_session_id: int) -> int:
    return int(await db.scalar(
        select(func.count()).select_from(ConfusionPress)
        .where(ConfusionPress.attendance_session_id == attendance_session_id,
               ConfusionPress.ended_at.is_(None))) or 0)


async def confusion_people(db: AsyncSession, attendance_session_id: int) -> int:
    """How many different students pressed at least once."""
    return int(await db.scalar(
        select(func.count(func.distinct(ConfusionPress.student_id)))
        .where(ConfusionPress.attendance_session_id == attendance_session_id)) or 0)


async def _latest_spike(db: AsyncSession, attendance_session_id: int) -> ConfusionSpike | None:
    return (await db.execute(
        select(ConfusionSpike).where(ConfusionSpike.attendance_session_id == attendance_session_id)
        .order_by(ConfusionSpike.started_at.desc(), ConfusionSpike.id.desc()).limit(1)
        .execution_options(populate_existing=True))).scalar_one_or_none()


def _ongoing(spike: ConfusionSpike | None, now: datetime) -> bool:
    return spike is not None and spike.last_at > now - _window()


async def _notify_spike(db: AsyncSession, session: AttendanceSession, spike_id: int) -> None:
    lecturer_user_id = await db.scalar(select(Lecturer.user_id).where(Lecturer.id == session.lecturer_id))
    if lecturer_user_id is None:
        return
    course_code = None
    if session.occurrence_id is not None:
        course_code = await db.scalar(
            select(Course.code).join(ClassOccurrence, ClassOccurrence.course_id == Course.id)
            .where(ClassOccurrence.id == session.occurrence_id))
    payload = {"attendance_session_id": session.id, "spike_id": spike_id, "course_code": course_code}

    async def _after() -> None:
        await notify.emit(EVENT_SPIKE, [lecturer_user_id], payload)

    after_commit(db, _after)


async def _check_spike(db: AsyncSession, session: AttendanceSession, now: datetime) -> None:
    size = await _class_size(db, session)
    students = await _recent_students(db, session.id, now)
    if not spike_reached(students, size):
        return
    latest = await _latest_spike(db, session.id)
    if _ongoing(latest, now):
        latest.last_at = now
        latest.peak_students = max(latest.peak_students, students)
        await db.flush()
        return
    spike = ConfusionSpike(attendance_session_id=session.id, started_at=now, last_at=now,
                           peak_students=students, class_size=size)
    db.add(spike)
    await db.flush()
    await _notify_spike(db, session, spike.id)


async def press(db: AsyncSession, member: Member, attendance_session_id: int,
                topic: str | None) -> ConfusionAck:
    _students_only(member, "press \"I don't understand\"")
    await sessions.require_open(db, attendance_session_id)
    await _lock(db, f"m5_confusion:{attendance_session_id}")
    now = sessions.clock()
    row = await _last(db, ConfusionPress, attendance_session_id, member.student_id)
    on = row is not None and row.ended_at is None
    if _within(row, now, settings.INTERACTION_CONFUSION_COOLDOWN_SECONDS):
        if on and topic in (None, row.topic):
            return ConfusionAck(topic=row.topic, created_at=row.created_at)     # already on
        row.ended_at = None                                                     # back on: the same press
        row.topic = topic or row.topic
    else:
        if on:
            row.ended_at = now
            await db.flush()
        row = ConfusionPress(attendance_session_id=attendance_session_id, student_id=member.student_id,
                             topic=topic, created_at=now)
        db.add(row)
        events.record(db, events.CONFUSION, attendance_session_id, member.student_id, now)
    await db.flush()
    session = await db.get(AttendanceSession, attendance_session_id)
    await _check_spike(db, session, now)
    live.changed(db, attendance_session_id, live.CONFUSION)
    return ConfusionAck(topic=row.topic, created_at=row.created_at)


async def cancel_press(db: AsyncSession, member: Member, attendance_session_id: int) -> None:
    _students_only(member, "press \"I don't understand\"")
    await sessions.require_open(db, attendance_session_id)
    await _lock(db, f"m5_confusion:{attendance_session_id}")
    await _cancel(db, member, attendance_session_id, ConfusionPress, live.CONFUSION)


async def clear_confusion(db: AsyncSession, member: Member, attendance_session_id: int) -> None:
    """The lecturer lowers every "I don't understand" that is on."""
    sessions.require_lecturer(member)
    await sessions.require_open(db, attendance_session_id)
    await _lock(db, f"m5_confusion:{attendance_session_id}")
    if await _end_all(db, ConfusionPress, attendance_session_id):
        live.changed(db, attendance_session_id, live.CONFUSION)
        live.changed(db, attendance_session_id, live.SIGNALS)


def _bucket_start(t: datetime, seconds: int) -> datetime:
    midnight = t.replace(hour=0, minute=0, second=0, microsecond=0)
    offset = int((t - midnight).total_seconds()) // seconds * seconds
    return midnight + timedelta(seconds=offset)


async def confusion_view(db: AsyncSession, member: Member, session: AttendanceSession,
                         interaction_status: str) -> ConfusionOut:
    """Aggregates only (FR-515): no student id or name in any field."""
    sessions.require_lecturer(member)
    now = sessions.clock()
    rows = (await db.execute(
        select(ConfusionPress.created_at, ConfusionPress.topic)
        .where(ConfusionPress.attendance_session_id == session.id)
        .order_by(ConfusionPress.created_at))).all()
    bucket = max(settings.INTERACTION_CONFUSION_BUCKET_SECONDS, 1)
    timeline = Counter(_bucket_start(t, bucket) for t, _ in rows)
    topics = Counter(tp for _, tp in rows if tp)
    since = now - _window()
    latest = await _latest_spike(db, session.id)
    spikes = int(await db.scalar(select(func.count()).where(
        ConfusionSpike.attendance_session_id == session.id)) or 0)
    active = await _active_students(db, session.id) if session.status == "open" else 0
    size = await _class_size(db, session)
    return ConfusionOut(
        attendance_session_id=session.id, status=interaction_status, active=active, total=len(rows),
        recent=sum(1 for t, _ in rows if since < t <= now),
        recent_students=await _recent_students(db, session.id, now),
        class_size=size, window_seconds=int(_window().total_seconds()),
        # over as soon as enough students take it back, or after a quiet window
        spike_active=interaction_status == "open" and _ongoing(latest, now) and spike_reached(active, size),
        spikes=spikes,
        timeline=[ConfusionBucket(start=k, count=v) for k, v in sorted(timeline.items())],
        topics=[ConfusionTopicCount(topic=k, count=v)
                for k, v in sorted(topics.items(), key=lambda kv: (-kv[1], kv[0].casefold()))])
