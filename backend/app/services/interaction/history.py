"""The lecturer's Interaction tab: their class sessions that have interaction data — S38d.

`list_sessions` lists the class sessions the lecturer teaches (the lecturer assigned to the class,
or for a session without a timetable class the lecturer who ran it — the same rule as
`sessions.authorize`) that have at least one question, poll that ran (drafts don't count, as in the
S36 summary), quick question, reaction or confusion press. Newest first by the class's start
(`opened_at`, else `starts_at`), then id; paged with `limit`/`offset`.

Counts only: no student identity, nothing graded (FR-513). Read only.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import ClassOccurrence, Course
from app.models.interaction import ConfusionPress, InteractionSession, Poll, Question, QuickQuestion, Reaction
from app.models.session import AttendanceSession
from app.models.user import Lecturer
from app.schemas.interaction import InteractionHistoryCounts, InteractionHistoryItem, InteractionHistoryOut
from app.services.interaction import sessions
from app.services.interaction.summary import class_date

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _count(model, *extra):
    return (select(func.count()).select_from(model)
            .where(model.attendance_session_id == AttendanceSession.id, *extra)
            .correlate(AttendanceSession).scalar_subquery())


def _people(model):
    """Different students with a row in the session."""
    return (select(func.count(func.distinct(model.student_id)))
            .where(model.attendance_session_id == AttendanceSession.id)
            .correlate(AttendanceSession).scalar_subquery())


async def list_sessions(db: AsyncSession, lecturer_user_id: int, *, limit: int = DEFAULT_LIMIT,
                        offset: int = 0) -> InteractionHistoryOut:
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    lecturer_id = await db.scalar(select(Lecturer.id).where(Lecturer.user_id == lecturer_user_id))
    if lecturer_id is None:
        return InteractionHistoryOut(sessions=[], total=0, next_offset=None)

    n_questions = _count(Question)
    n_polls = _count(Poll, Poll.status != "draft")
    n_quick = _count(QuickQuestion)
    n_reactions = _count(Reaction)
    n_confusion = _count(ConfusionPress)
    has_data = (n_questions + n_polls + n_quick + n_reactions + n_confusion) > 0
    teaches = or_(ClassOccurrence.lecturer_id == lecturer_id,
                  and_(AttendanceSession.occurrence_id.is_(None), AttendanceSession.lecturer_id == lecturer_id))
    started = func.coalesce(AttendanceSession.opened_at, AttendanceSession.starts_at)

    base = (select(AttendanceSession.id)
            .outerjoin(ClassOccurrence, ClassOccurrence.id == AttendanceSession.occurrence_id)
            .where(teaches, has_data))
    total = await db.scalar(select(func.count()).select_from(base.subquery()))

    stmt = (select(AttendanceSession, ClassOccurrence.type, ClassOccurrence.label, Course.code, Course.name,
                   InteractionSession, n_questions, n_polls, n_quick, _people(Reaction),
                   _people(ConfusionPress))
            .outerjoin(ClassOccurrence, ClassOccurrence.id == AttendanceSession.occurrence_id)
            .outerjoin(Course, Course.id == ClassOccurrence.course_id)
            .outerjoin(InteractionSession, InteractionSession.attendance_session_id == AttendanceSession.id)
            .where(teaches, has_data)
            .order_by(desc(started).nulls_last(), AttendanceSession.id.desc())
            .limit(limit).offset(offset))
    rows = (await db.execute(stmt)).all()

    items = []
    for sess, ctype, label, code, name, row, nq, np, nqq, nr, nc in rows:
        st, _reason = sessions.effective(sess, row)
        d = class_date(sess)
        items.append(InteractionHistoryItem(
            attendance_session_id=sess.id, occurrence_id=sess.occurrence_id, course_code=code,
            course_name=name, class_type=ctype, class_label=label,
            class_date=d.isoformat() if d else None, starts_at=_start(sess), ends_at=_end(sess),
            class_status=sess.status, status=st,
            counts=InteractionHistoryCounts(questions=nq, polls=np, quick_questions=nqq,
                                            reactions=nr, confusion=nc)))
    more = offset + len(items) < (total or 0)
    return InteractionHistoryOut(sessions=items, total=total or 0,
                                 next_offset=offset + len(items) if more and items else None)


def _start(sess: AttendanceSession) -> datetime | None:
    return sess.opened_at or sess.starts_at


def _end(sess: AttendanceSession) -> datetime | None:
    return (sess.closed_at or sess.ends_at) if sess.status != "open" else sess.ends_at
