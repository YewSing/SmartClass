"""Reactions and "I don't understand" (FR-511, FR-512, FR-514, FR-515) — S33.

Reactions: a student sends one of `REACTION_KINDS`, at most one every
`INTERACTION_REACTION_COOLDOWN_SECONDS` (429 with `Retry-After` otherwise). The lecturer sees
running counts per kind.

Confusion: a press may carry a topic tag; one press per student every
`INTERACTION_CONFUSION_COOLDOWN_SECONDS` (default 2 min, 429 otherwise). The lecturer sees only
aggregates: the count, the recent count, a per-bucket timeline and topic counts, never who pressed
(FR-515). After each press the spike rule runs (FR-514): when the distinct students pressing in
the last `INTERACTION_CONFUSION_WINDOW_SECONDS` reach `INTERACTION_CONFUSION_SPIKE_SHARE` of the
active enrolled students, a spike starts and `confusion.spike` (urgent) goes to the class session's
lecturer after the commit. While the share stays at or above the threshold the same spike carries
on (no second notification); a new spike needs a whole window without a press at/above it.

Both writes go through `sessions.require_open` (409 once closed). Cooldowns are checked under a
transaction advisory lock per student (reactions) or per class session (confusion: it also
serialises the spike rule, so two presses can't both start a spike). Nothing is graded (FR-513).
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
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
    ReactionAck,
    ReactionCountsOut,
)
from app.services import notify
from app.services.interaction import events, live, sessions
from app.services.interaction.sessions import Member
from app.services.notifications import announcements

EVENT_SPIKE = "confusion.spike"


def _students_only(member: Member, what: str) -> None:
    if member.role != sessions.ROLE_STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Only students can {what}")


async def _lock(db: AsyncSession, key: str) -> None:
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))


def _cooldown(last: datetime | None, now: datetime, seconds: int, what: str) -> None:
    """429 with Retry-After while `last` is less than `seconds` ago."""
    if last is None or seconds <= 0:
        return
    remaining = (last + timedelta(seconds=seconds) - now).total_seconds()
    if remaining > 0:
        wait = math.ceil(remaining)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Please wait {wait} s before the next {what}",
                            headers={"Retry-After": str(wait)})


# ── reactions (FR-511) ───────────────────────────────────────────────────────

async def react(db: AsyncSession, member: Member, attendance_session_id: int, kind: str) -> ReactionAck:
    _students_only(member, "react")
    await sessions.require_open(db, attendance_session_id)
    await _lock(db, f"m5_reaction:{attendance_session_id}:{member.student_id}")
    now = sessions.clock()
    last = await db.scalar(select(func.max(Reaction.created_at)).where(
        Reaction.attendance_session_id == attendance_session_id, Reaction.student_id == member.student_id))
    cooldown = settings.INTERACTION_REACTION_COOLDOWN_SECONDS
    _cooldown(last, now, cooldown, "reaction")
    db.add(Reaction(attendance_session_id=attendance_session_id, student_id=member.student_id,
                    kind=kind, created_at=now))
    events.record(db, events.REACTION, attendance_session_id, member.student_id, now)
    await db.flush()
    live.changed(db, attendance_session_id, live.REACTIONS)
    return ReactionAck(kind=kind, created_at=now, next_allowed_at=now + timedelta(seconds=max(cooldown, 0)))


async def reaction_counts(db: AsyncSession, member: Member, attendance_session_id: int,
                          interaction_status: str) -> ReactionCountsOut:
    sessions.require_lecturer(member)
    found = dict((await db.execute(
        select(Reaction.kind, func.count()).where(Reaction.attendance_session_id == attendance_session_id)
        .group_by(Reaction.kind))).all())
    counts = {k: int(found.get(k, 0)) for k in REACTION_KINDS}
    return ReactionCountsOut(attendance_session_id=attendance_session_id, status=interaction_status,
                             counts=counts, total=sum(counts.values()))


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
    return int(await db.scalar(
        select(func.count(func.distinct(ConfusionPress.student_id)))
        .where(ConfusionPress.attendance_session_id == attendance_session_id,
               ConfusionPress.created_at > now - _window(), ConfusionPress.created_at <= now)) or 0)


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
    last = await db.scalar(select(func.max(ConfusionPress.created_at)).where(
        ConfusionPress.attendance_session_id == attendance_session_id,
        ConfusionPress.student_id == member.student_id))
    cooldown = settings.INTERACTION_CONFUSION_COOLDOWN_SECONDS
    _cooldown(last, now, cooldown, "\"I don't understand\"")
    db.add(ConfusionPress(attendance_session_id=attendance_session_id, student_id=member.student_id,
                          topic=topic, created_at=now))
    events.record(db, events.CONFUSION, attendance_session_id, member.student_id, now)
    await db.flush()
    session = await db.get(AttendanceSession, attendance_session_id)
    await _check_spike(db, session, now)
    live.changed(db, attendance_session_id, live.CONFUSION)
    return ConfusionAck(created_at=now, next_allowed_at=now + timedelta(seconds=max(cooldown, 0)))


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
    return ConfusionOut(
        attendance_session_id=session.id, status=interaction_status, total=len(rows),
        recent=sum(1 for t, _ in rows if since < t <= now),
        recent_students=await _recent_students(db, session.id, now),
        class_size=await _class_size(db, session),
        window_seconds=int(_window().total_seconds()),
        spike_active=interaction_status == "open" and _ongoing(latest, now), spikes=spikes,
        timeline=[ConfusionBucket(start=k, count=v) for k, v in sorted(timeline.items())],
        topics=[ConfusionTopicCount(topic=k, count=v)
                for k, v in sorted(topics.items(), key=lambda kv: (-kv[1], kv[0].casefold()))])
