"""Attendance rate and history (FR-307–FR-309). One formula for every reader (M3 screens, T33 reports, T37's read interface for M7)."""
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.session import AttendanceSession
from app.models.user import Student

HISTORY_SESSION_STATUSES = ("open", "closed")  # scheduled / cancelled / needs_confirmation are not shown
REPORT_SESSION_STATUSES = ("closed",)  # only finalised sessions go into a report (same rule as the rate)


@dataclass
class StatusCounts:
    present: int = 0
    late: int = 0
    excused: int = 0
    absent: int = 0

    def add(self, status: str) -> None:
        setattr(self, status, getattr(self, status) + 1)

    @property
    def closed_sessions(self) -> int:
        return self.present + self.late + self.excused + self.absent

    @property
    def attended(self) -> int:
        return self.present + self.late

    @property
    def counted_sessions(self) -> int:
        return self.closed_sessions - self.excused   # Excused is left out (FR-308, decision T00d)

    @property
    def rate(self) -> float | None:
        """(present + late) ÷ (closed − excused) as a percentage, 1 decimal; None when nothing counts."""
        if self.counted_sessions == 0:
            return None
        return round(self.attended / self.counted_sessions * 100, 1)


def session_date(sess: AttendanceSession) -> date | None:
    """The MYT date of the class: class_date, else opened_at's date, else starts_at's date."""
    if sess.class_date:
        return sess.class_date
    when = sess.opened_at or sess.starts_at
    return when.date() if when else None


def session_label(sess: AttendanceSession) -> str:
    """'YYYY-MM-DD HH:MM' (MYT) of the class; date only when no start time is stored."""
    d = session_date(sess)
    start = sess.starts_at or sess.opened_at
    day = d.isoformat() if d else ""
    return f"{day} {start.strftime('%H:%M')}".strip() if start else day


def resolve_date_range(
    from_: date | None, to: date | None, from_date: date | None = None, to_date: date | None = None,
) -> tuple[date | None, date | None]:
    """`from`/`to` (FR-310), with the older `from_date`/`to_date` names still accepted.
    Raises ValueError when from is after to."""
    start = from_ or from_date
    end = to or to_date
    if start and end and start > end:
        raise ValueError("'from' must be on or before 'to'")
    return start, end


async def student_course_history(db: AsyncSession, student_id: int) -> list[dict]:
    """Per-course counts, rate and session history for one student (FR-309)."""
    occurrences = (await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
        .where(Enrollment.student_id == student_id)
    )).scalars().all()
    if not occurrences:
        return []

    sessions = (await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.occurrence_id.in_([occ.id for occ in occurrences]),
            AttendanceSession.status.in_(HISTORY_SESSION_STATUSES),
        )
    )).scalars().all()

    records: dict[int, AttendanceRecord] = {}
    if sessions:
        rows = (await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.session_id.in_([sess.id for sess in sessions]),
            )
        )).scalars().all()
        records = {rec.session_id: rec for rec in rows}

    occurrences_by_id = {occ.id: occ for occ in occurrences}
    sessions_by_course: dict[int, list[AttendanceSession]] = {}
    for sess in sessions:
        occ = occurrences_by_id.get(sess.occurrence_id)
        if occ is None:
            continue
        sessions_by_course.setdefault(occ.course_id, []).append(sess)

    out: list[dict] = []
    for course_id, course_occurrences in sorted(
        _group_by_course(occurrences).items(), key=lambda item: item[1][0].course.code
    ):
        counts = StatusCounts()
        history: list[dict] = []
        for sess in sessions_by_course.get(course_id, []):
            occ = occurrences_by_id[sess.occurrence_id]
            rec = records.get(sess.id)
            if sess.status == "closed":
                status = rec.status if rec else "absent"
                counts.add(status)
            else:  # open: shown, never counted
                status = rec.status if rec else "not_recorded"
            history.append({
                "session_id": sess.id,
                "occurrence_id": occ.id,
                "class_type": occ.type,
                "class_label": occ.label,
                "date": session_date(sess),
                "starts_at": sess.starts_at or sess.opened_at,
                "session_status": sess.status,
                "status": status,
                "detected_at": rec.detected_at if rec else None,
                "overridden": bool(rec and rec.override_by),
            })

        history.sort(
            key=lambda item: (item["date"] or date.min, item["starts_at"] or datetime.min),
            reverse=True,
        )
        course = course_occurrences[0].course
        out.append({
            "course_id": course.id,
            "course_code": course.code,
            "course_name": course.name,
            "counts": counts,
            "sessions": history,
        })
    return out


async def _class_students(db: AsyncSession, occurrence_id: int) -> list[Student]:
    """Enrolled students of one class, ordered by matric no."""
    return (await db.execute(
        select(Student)
        .options(selectinload(Student.user))
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.occurrence_id == occurrence_id)
        .order_by(Student.matric_no)
    )).scalars().all()


async def class_student_rates(db: AsyncSession, occurrence_id: int) -> tuple[int, list[dict]]:
    """Per-student counts and rate for one class, ordered by matric no. Returns (closed session count, rows)."""
    students = await _class_students(db, occurrence_id)

    closed_ids = (await db.execute(
        select(AttendanceSession.id).where(
            AttendanceSession.occurrence_id == occurrence_id,
            AttendanceSession.status == "closed",
        )
    )).scalars().all()

    lookup: dict[tuple[int, int], str] = {}
    if closed_ids:
        rows = (await db.execute(
            select(AttendanceRecord.session_id, AttendanceRecord.student_id, AttendanceRecord.status)
            .where(AttendanceRecord.session_id.in_(closed_ids))
        )).all()
        lookup = {(session_id, student_id): status for session_id, student_id, status in rows}

    out: list[dict] = []
    for stu in students:
        counts = StatusCounts()
        for session_id in closed_ids:
            counts.add(lookup.get((session_id, stu.id), "absent"))
        out.append({
            "student_id": stu.id,
            "matric_no": stu.matric_no,
            "name": stu.user.name,
            "counts": counts,
        })
    return len(closed_ids), out


async def class_report(
    db: AsyncSession, occurrence_id: int, from_date: date | None = None, to_date: date | None = None,
) -> tuple[list[AttendanceSession], list[dict]]:
    """Closed sessions of one class between from_date and to_date (inclusive, by session_date),
    oldest first, and one row per enrolled student (ordered by matric no):
    {"student_id", "matric_no", "name", "statuses": [status per session, same order], "counts": StatusCounts}.
    A missing record in a closed session is absent."""
    students = await _class_students(db, occurrence_id)

    sessions = (await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.occurrence_id == occurrence_id,
            AttendanceSession.status.in_(REPORT_SESSION_STATUSES),
        )
    )).scalars().all()

    kept: list[AttendanceSession] = []
    for sess in sessions:
        d = session_date(sess)
        if from_date and (d is None or d < from_date):
            continue
        if to_date and (d is None or d > to_date):
            continue
        kept.append(sess)
    kept.sort(key=lambda s: (
        session_date(s) or date.min, s.starts_at or s.opened_at or datetime.min, s.id,
    ))

    lookup: dict[tuple[int, int], str] = {}
    if kept:
        rows = (await db.execute(
            select(AttendanceRecord.session_id, AttendanceRecord.student_id, AttendanceRecord.status)
            .where(AttendanceRecord.session_id.in_([s.id for s in kept]))
        )).all()
        lookup = {(session_id, student_id): status for session_id, student_id, status in rows}

    out: list[dict] = []
    for stu in students:
        statuses = [lookup.get((sess.id, stu.id), "absent") for sess in kept]
        counts = StatusCounts()
        for status in statuses:
            counts.add(status)
        out.append({
            "student_id": stu.id,
            "matric_no": stu.matric_no,
            "name": stu.user.name,
            "statuses": statuses,
            "counts": counts,
        })
    return kept, out


def counts_out(counts: StatusCounts) -> dict:
    """The seven AttendanceCountsOut fields, so every endpoint builds the same shape."""
    return {
        "present": counts.present,
        "late": counts.late,
        "excused": counts.excused,
        "absent": counts.absent,
        "closed_sessions": counts.closed_sessions,
        "counted_sessions": counts.counted_sessions,
        "rate": counts.rate,
    }


def _group_by_course(occurrences: list[ClassOccurrence]) -> dict[int, list[ClassOccurrence]]:
    grouped: dict[int, list[ClassOccurrence]] = {}
    for occ in occurrences:
        grouped.setdefault(occ.course_id, []).append(occ)
    return grouped
