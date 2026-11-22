"""Read interface for Module 7 over Module 5's interaction event log (FR-517, FR-702, FR-713) — S34.
Documented in docs/interfaces.md ("Interaction read interface for Module 7").

Rules:
- Counts come from `m5_events` (one row per student action). Repeats are folded the way a person
  would count them: a poll counts once per student however often they changed their vote, a quick
  question once per student however often they replaced their answer.
- Anonymous questions (FR-504, FR-713) never appear in a per-student figure: `questions` counts only
  the student's named questions. They are counted in the class totals (`questions`, with
  `anonymous_questions` as a separate count) without any identity.
- Sessions of any status count (interaction only happens while a class runs). A course joins all
  its classes (lecture and tutorials). Dates are the MYT date of the class; ranges are inclusive.
- Read only, never commits. No permission checks: the caller (an M7 endpoint) checks the user may
  see the course (NFR-04) first. Nothing is a grade or score (FR-513).
Returned objects are frozen dataclasses; fields may be added later but are never renamed or removed.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.interaction import InteractionEvent, Poll
from app.models.session import AttendanceSession
from app.models.user import Student, User
from app.services.interaction import events as ev

__all__ = [
    "StudentInteractionCounts",
    "SessionInteractionTotals",
    "course_student_counts",
    "student_counts",
    "session_student_counts",
    "course_session_totals",
    "session_totals",
]


@dataclass(frozen=True)
class StudentInteractionCounts:
    """One student's interaction counts in one course (or one session, see `session_student_counts`)."""
    student_id: int            # students.id
    matric_no: str
    name: str
    course_id: int
    course_code: str
    sessions_active: int       # sessions with at least one event of this student (anonymous ones excluded)
    polls_answered: int        # distinct polls voted on
    questions: int             # named questions asked (anonymous ones never counted here, FR-713)
    upvotes: int               # questions upvoted
    quick_answers: int         # distinct quick questions answered
    reactions: int
    confusion: int             # "I don't understand" presses


@dataclass(frozen=True)
class SessionInteractionTotals:
    """Class totals for one class session, without any student identity."""
    session_id: int            # attendance session id
    occurrence_id: int | None
    course_id: int | None
    course_code: str | None
    date: date | None          # MYT date of the class
    polls_run: int             # polls started (open or closed) in the session
    poll_answers: int          # distinct (poll, student) pairs
    questions: int             # all questions asked, anonymous ones included
    anonymous_questions: int   # how many of `questions` were anonymous
    upvotes: int
    quick_answers: int         # distinct (quick question, student) pairs
    reactions: int
    confusion: int
    participants: int          # distinct students with any event (anonymous questions included)


def _date(sess: AttendanceSession) -> date | None:
    if sess.class_date:
        return sess.class_date
    when = sess.opened_at or sess.starts_at
    return when.date() if when else None


def _check_range(from_date: date | None, to_date: date | None) -> None:
    if from_date and to_date and from_date > to_date:
        raise ValueError("from_date must be on or before to_date")


def _in_range(d: date | None, from_date: date | None, to_date: date | None) -> bool:
    if from_date is None and to_date is None:
        return True
    if d is None:
        return False
    return (from_date is None or d >= from_date) and (to_date is None or d <= to_date)


@dataclass
class _Session:
    id: int
    occurrence_id: int | None
    course_id: int | None
    course_code: str | None
    date: date | None


async def _sessions(db: AsyncSession, *, course_id: int | None = None, session_id: int | None = None,
                    session_ids: set[int] | None = None, from_date: date | None = None,
                    to_date: date | None = None) -> dict[int, _Session]:
    stmt = (select(AttendanceSession, ClassOccurrence.course_id, Course.code)
            .outerjoin(ClassOccurrence, ClassOccurrence.id == AttendanceSession.occurrence_id)
            .outerjoin(Course, Course.id == ClassOccurrence.course_id))
    if course_id is not None:
        stmt = stmt.where(ClassOccurrence.course_id == course_id)
    if session_id is not None:
        stmt = stmt.where(AttendanceSession.id == session_id)
    if session_ids is not None:
        if not session_ids:
            return {}
        stmt = stmt.where(AttendanceSession.id.in_(session_ids))
    out: dict[int, _Session] = {}
    for sess, cid, code in (await db.execute(stmt)).all():
        d = _date(sess)
        if _in_range(d, from_date, to_date):
            out[sess.id] = _Session(sess.id, sess.occurrence_id, cid, code, d)
    return out


async def _events(db: AsyncSession, session_ids, *, student_id: int | None = None) -> list[InteractionEvent]:
    if not session_ids:
        return []
    stmt = select(InteractionEvent).where(InteractionEvent.attendance_session_id.in_(list(session_ids)))
    if student_id is not None:
        stmt = stmt.where(InteractionEvent.student_id == student_id)
    return list((await db.execute(stmt.order_by(InteractionEvent.id))).scalars())


class _Tally:
    def __init__(self) -> None:
        self.sessions: set[int] = set()
        self.polls: set[int] = set()
        self.quick: set[int] = set()
        self.questions = self.upvotes = self.reactions = self.confusion = 0

    def add(self, e: InteractionEvent) -> None:
        """Add one event to a per-student tally. Anonymous questions are skipped entirely."""
        if e.anonymous:
            return
        self.sessions.add(e.attendance_session_id)
        if e.type == ev.POLL_VOTED:
            self.polls.add(e.ref_id)
        elif e.type == ev.QUICK_ANSWERED:
            self.quick.add(e.ref_id)
        elif e.type == ev.QUESTION_ASKED:
            self.questions += 1
        elif e.type == ev.QUESTION_UPVOTED:
            self.upvotes += 1
        elif e.type == ev.REACTION:
            self.reactions += 1
        elif e.type == ev.CONFUSION:
            self.confusion += 1


def _counts(student: tuple[int, str, str], course: tuple[int, str], t: _Tally) -> StudentInteractionCounts:
    sid, matric, name = student
    cid, code = course
    return StudentInteractionCounts(
        student_id=sid, matric_no=matric, name=name, course_id=cid, course_code=code,
        sessions_active=len(t.sessions), polls_answered=len(t.polls), questions=t.questions,
        upvotes=t.upvotes, quick_answers=len(t.quick), reactions=t.reactions, confusion=t.confusion)


async def _student_info(db: AsyncSession, student_ids) -> dict[int, tuple[int, str, str]]:
    if not student_ids:
        return {}
    rows = (await db.execute(select(Student.id, Student.matric_no, User.name)
                             .join(User, User.id == Student.user_id)
                             .where(Student.id.in_(list(student_ids))))).all()
    return {sid: (sid, matric, name) for sid, matric, name in rows}


async def course_student_counts(db: AsyncSession, course_id: int, from_date: date | None = None,
                                to_date: date | None = None) -> list[StudentInteractionCounts]:
    """One row per student enrolled in any class of the course (zeros included), by matric no."""
    _check_range(from_date, to_date)
    code = await db.scalar(select(Course.code).where(Course.id == course_id))
    if code is None:
        return []
    enrolled = set((await db.execute(
        select(Enrollment.student_id).join(ClassOccurrence, ClassOccurrence.id == Enrollment.occurrence_id)
        .where(ClassOccurrence.course_id == course_id))).scalars())
    sess = await _sessions(db, course_id=course_id, from_date=from_date, to_date=to_date)
    tallies: dict[int, _Tally] = defaultdict(_Tally)
    for e in await _events(db, sess.keys()):
        if e.student_id in enrolled:
            tallies[e.student_id].add(e)
    info = await _student_info(db, enrolled)
    rows = [_counts(info[sid], (course_id, code), tallies[sid]) for sid in enrolled if sid in info]
    return sorted(rows, key=lambda r: (r.matric_no, r.student_id))


async def student_counts(db: AsyncSession, student_id: int, course_id: int | None = None,
                         from_date: date | None = None, to_date: date | None = None
                         ) -> list[StudentInteractionCounts]:
    """One row per course the student is enrolled in (zeros included), by course code."""
    _check_range(from_date, to_date)
    info = (await _student_info(db, [student_id])).get(student_id)
    if info is None:
        return []
    stmt = (select(Course.id, Course.code).join(ClassOccurrence, ClassOccurrence.course_id == Course.id)
            .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
            .where(Enrollment.student_id == student_id).distinct())
    if course_id is not None:
        stmt = stmt.where(Course.id == course_id)
    courses = dict((await db.execute(stmt)).all())
    out = []
    for cid, code in courses.items():
        sess = await _sessions(db, course_id=cid, from_date=from_date, to_date=to_date)
        t = _Tally()
        for e in await _events(db, sess.keys(), student_id=student_id):
            t.add(e)
        out.append(_counts(info, (cid, code), t))
    return sorted(out, key=lambda r: (r.course_code, r.course_id))


async def session_student_counts(db: AsyncSession, attendance_session_id: int
                                 ) -> list[StudentInteractionCounts]:
    """One row per student enrolled in the session's class (zeros included), by matric no.
    `sessions_active` is 1 or 0. An unknown session, or one without a class, returns []."""
    sess = (await _sessions(db, session_id=attendance_session_id)).get(attendance_session_id)
    if sess is None or sess.occurrence_id is None:
        return []
    enrolled = set((await db.execute(
        select(Enrollment.student_id).where(Enrollment.occurrence_id == sess.occurrence_id))).scalars())
    tallies: dict[int, _Tally] = defaultdict(_Tally)
    for e in await _events(db, [sess.id]):
        if e.student_id in enrolled:
            tallies[e.student_id].add(e)
    info = await _student_info(db, enrolled)
    rows = [_counts(info[sid], (sess.course_id, sess.course_code), tallies[sid])
            for sid in enrolled if sid in info]
    return sorted(rows, key=lambda r: (r.matric_no, r.student_id))


async def _totals(db: AsyncSession, sessions_: dict[int, _Session]) -> list[SessionInteractionTotals]:
    if not sessions_:
        return []
    by_session: dict[int, list[InteractionEvent]] = defaultdict(list)
    for e in await _events(db, sessions_.keys()):
        by_session[e.attendance_session_id].append(e)
    run: dict[int, int] = defaultdict(int, (await db.execute(
        select(Poll.attendance_session_id, func.count()).where(
            Poll.attendance_session_id.in_(list(sessions_)), Poll.status != "draft")
        .group_by(Poll.attendance_session_id))).all())
    out = []
    for s in sorted(sessions_.values(), key=lambda s: (s.date or date.min, s.id)):
        evs = by_session[s.id]
        kinds = defaultdict(int)
        for e in evs:
            kinds[e.type] += 1
        out.append(SessionInteractionTotals(
            session_id=s.id, occurrence_id=s.occurrence_id, course_id=s.course_id,
            course_code=s.course_code, date=s.date, polls_run=run[s.id],
            poll_answers=len({(e.ref_id, e.student_id) for e in evs if e.type == ev.POLL_VOTED}),
            questions=kinds[ev.QUESTION_ASKED],
            anonymous_questions=sum(1 for e in evs if e.type == ev.QUESTION_ASKED and e.anonymous),
            upvotes=kinds[ev.QUESTION_UPVOTED],
            quick_answers=len({(e.ref_id, e.student_id) for e in evs if e.type == ev.QUICK_ANSWERED}),
            reactions=kinds[ev.REACTION], confusion=kinds[ev.CONFUSION],
            participants=len({e.student_id for e in evs if e.student_id is not None})))
    return out


async def course_session_totals(db: AsyncSession, course_id: int, from_date: date | None = None,
                                to_date: date | None = None) -> list[SessionInteractionTotals]:
    """Class totals for every session of the course (all its classes), oldest first."""
    _check_range(from_date, to_date)
    return await _totals(db, await _sessions(db, course_id=course_id, from_date=from_date, to_date=to_date))


async def session_totals(db: AsyncSession, attendance_session_id: int) -> SessionInteractionTotals | None:
    """Class totals for one session, or None for an unknown id."""
    found = await _totals(db, await _sessions(db, session_id=attendance_session_id))
    return found[0] if found else None
