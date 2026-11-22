"""Student and lecturer dashboard reads (FR-201, FR-202) — S18.

Read only; never commits. Callers pass the signed-in user (NFR-04): a student only ever sees
their own classes, status, rates, snapshot and notifications; a lecturer only the classes they
are assigned to (`ClassOccurrence.lecturer_id`, the same rule as `ensure_teaches_occurrence`).

Where the data comes from:
- attendance rates and closed-session counts: `app.services.attendance_read` (FR-313 interface);
- the student's status in a session that is still open: M3's `attendance_stats.student_course_history`
  (what `/student/me/attendance/courses` shows; `attendance_read` leaves open sessions out);
- the current open session's counts: M3's `session_service.get_session_counts` (the counts the
  lecturer's live roster shows);
- Moodle announcements/deadlines: the S16 snapshot; notifications: the S11 feed.
"today" is the MYT date of `clock()`.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.timezone import now_myt
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.services import attendance_read, session_service
from app.services.attendance_stats import StatusCounts, session_date, student_course_history
from app.services.dashboard.moodle_snapshot import get_snapshot
from app.services.notifications import feed
from app.services.session_schedule import scheduled_times

DAY_SESSION_STATUSES = ("open", "closed", "needs_confirmation")   # a class that ran (or runs) today


def clock() -> datetime:
    """Current naive MYT time. Tests monkeypatch this (controlled clock)."""
    return now_myt()


def _hhmm(value: datetime | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def _started(sess: AttendanceSession) -> datetime:
    return sess.starts_at or sess.opened_at or datetime.min


async def _today_sessions(db: AsyncSession, occ_ids: list[int], today: date) -> dict[int, AttendanceSession]:
    """Per class, today's session: the open one if any, else the latest one that started."""
    if not occ_ids:
        return {}
    day_start = datetime.combine(today, time.min)
    rows = (await db.scalars(select(AttendanceSession).where(
        AttendanceSession.occurrence_id.in_(occ_ids),
        AttendanceSession.status.in_(DAY_SESSION_STATUSES),
        or_(AttendanceSession.class_date == today,
            and_(AttendanceSession.class_date.is_(None),
                 AttendanceSession.opened_at >= day_start,
                 AttendanceSession.opened_at < day_start + timedelta(days=1))),
    ))).all()
    best: dict[int, AttendanceSession] = {}
    for sess in rows:
        cur = best.get(sess.occurrence_id)
        key = (sess.status == "open", _started(sess), sess.id)
        if cur is None or key > (cur.status == "open", _started(cur), cur.id):
            best[sess.occurrence_id] = sess
    return best


def _today_classes(occurrences: list[ClassOccurrence], sessions: dict[int, AttendanceSession],
                   today: date) -> list[dict]:
    """Classes with a weekly slot today or a session today, earliest first."""
    out = []
    for occ in occurrences:
        sess = sessions.get(occ.id)
        slot = scheduled_times(occ, today)
        if sess is None and slot is None:
            continue
        start = sess.starts_at if sess and sess.starts_at else (slot[0] if slot else None)
        end = sess.ends_at if sess and sess.ends_at else (slot[1] if slot else None)
        out.append({
            "occurrence_id": occ.id, "course_id": occ.course_id, "course_code": occ.course.code,
            "course_name": occ.course.name, "class_type": occ.type, "class_label": occ.label,
            "room": occ.room, "start_time": _hhmm(start), "end_time": _hhmm(end),
            "session_id": sess.id if sess else None, "session_status": sess.status if sess else None,
        })
    out.sort(key=lambda c: (c["start_time"] is None, c["start_time"] or "", c["course_code"],
                            c["occurrence_id"]))
    return out


async def _notifications(db: AsyncSession, user_id: int) -> dict:
    return {
        "priority_notifications": [feed.out(n) for n in await feed.pinned(db, user_id)],
        "unread_count": await feed.unread_count(db, user_id),
    }


# ── student (FR-201) ───────────────────────────────────────────────────────────

async def student_dashboard(db: AsyncSession, user: User) -> dict:
    today = clock().date()
    student = await db.scalar(select(Student).where(Student.user_id == user.id))
    classes: list[dict] = []
    rates: list[dict] = []
    if student is not None:
        occurrences = list((await db.scalars(
            select(ClassOccurrence).options(selectinload(ClassOccurrence.course))
            .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
            .where(Enrollment.student_id == student.id)
        )).all())
        sessions = await _today_sessions(db, [o.id for o in occurrences], today)
        classes = _today_classes(occurrences, sessions, today)
        if any(c["session_id"] for c in classes):
            history = await student_course_history(db, student.id)
            status_of = {s["session_id"]: s["status"] for course in history for s in course["sessions"]}
        else:
            status_of = {}
        for c in classes:
            # needs_confirmation sessions aren't in the history: no status until the lecturer confirms
            c["attendance_status"] = status_of.get(c["session_id"]) if c["session_id"] else None
        rates = [{
            "course_id": r.course_id, "course_code": r.course_code, "course_name": r.course_name,
            "present": r.present, "late": r.late, "excused": r.excused, "absent": r.absent,
            "closed_sessions": r.closed_sessions, "rate": r.rate,
        } for r in await attendance_read.student_rates(db, student.id)]

    snap = await get_snapshot(db, user.id)
    moodle = snap or {"announcements": [], "deadlines": [], "refreshed_at": None}
    return {
        "date": today, "today_classes": classes, "attendance_rates": rates, "moodle": moodle,
        **await _notifications(db, user.id), "live_activity": None,
    }


# ── lecturer (FR-202) ──────────────────────────────────────────────────────────

async def _overview_session(db: AsyncSession, occ_ids: list[int]) -> AttendanceSession | None:
    """The current open session of the lecturer's classes (latest opened), else the latest closed one."""
    if not occ_ids:
        return None
    started = func.coalesce(AttendanceSession.starts_at, AttendanceSession.opened_at)
    for st in ("open", "closed"):
        sess = await db.scalar(
            select(AttendanceSession)
            .where(AttendanceSession.occurrence_id.in_(occ_ids), AttendanceSession.status == st)
            .order_by(started.desc().nulls_last(), AttendanceSession.id.desc())
            .limit(1)
        )
        if sess is not None:
            return sess
    return None


async def _overview(db: AsyncSession, sess: AttendanceSession, occ: ClassOccurrence) -> dict:
    d = session_date(sess)
    if sess.status == "open":
        c = await session_service.get_session_counts(sess.id, db)
        present, late, excused, not_recorded = c["present"], c["late"], c["excused"], c["not_recorded"]
        absent = max(0, c["absent"] - not_recorded)        # marked absent; the rest are "not yet"
        enrolled = present + late + excused + c["absent"]
        rate = None
    else:
        records = await attendance_read.course_records(db, occ.course_id, d, d)
        rows = [r for r in records if r.session_id == sess.id]
        counts = StatusCounts()
        for r in rows:
            counts.add(r.status)
        present, late, excused, absent = counts.present, counts.late, counts.excused, counts.absent
        not_recorded = 0
        enrolled = len(rows)
        rate = counts.rate
    return {
        "session_id": sess.id, "occurrence_id": occ.id, "course_id": occ.course_id,
        "course_code": occ.course.code, "course_name": occ.course.name, "class_type": occ.type,
        "class_label": occ.label, "session_status": sess.status, "date": d,
        "starts_at": sess.starts_at or sess.opened_at, "enrolled": enrolled, "present": present,
        "late": late, "excused": excused, "absent": absent, "not_recorded": not_recorded, "rate": rate,
    }


async def lecturer_dashboard(db: AsyncSession, user: User) -> dict:
    today = clock().date()
    lecturer = await db.scalar(select(Lecturer).where(Lecturer.user_id == user.id))
    classes: list[dict] = []
    overview = None
    if lecturer is not None:
        occurrences = list((await db.scalars(
            select(ClassOccurrence).options(selectinload(ClassOccurrence.course))
            .where(ClassOccurrence.lecturer_id == lecturer.id)
        )).all())
        by_id = {o.id: o for o in occurrences}
        sessions = await _today_sessions(db, list(by_id), today)
        classes = _today_classes(occurrences, sessions, today)
        sess = await _overview_session(db, list(by_id))
        if sess is not None:
            overview = await _overview(db, sess, by_id[sess.occurrence_id])
    return {
        "date": today, "today_classes": classes, "attendance_overview": overview,
        **await _notifications(db, user.id),
        "participation": None, "quizzes": None, "at_risk_alerts": None,
    }
