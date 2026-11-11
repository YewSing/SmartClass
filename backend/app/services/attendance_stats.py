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


async def class_student_rates(db: AsyncSession, occurrence_id: int) -> tuple[int, list[dict]]:
    """Per-student counts and rate for one class, ordered by matric no. Returns (closed session count, rows)."""
    students = (await db.execute(
        select(Student)
        .options(selectinload(Student.user))
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.occurrence_id == occurrence_id)
        .order_by(Student.matric_no)
    )).scalars().all()

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
