"""Read interface for Module 7, Learning Analytics (FR-313). Documented in docs/interfaces.md.

Rules (same as the student app and lecturer reports, FR-308):
- Only closed sessions count. Open, scheduled, cancelled and needs_confirmation sessions are left out.
- A student enrolled in a class with no record in one of its closed sessions is absent.
- Late counts as attended; Excused is left out of the rate.
- No permission checks here: the caller (an M7 endpoint) must check the user may see the course (NFR-04).
Returned objects are frozen dataclasses; fields may be added later but are never renamed or removed.
"""
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance import ATTENDED_STATUSES, AttendanceRecord
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.session import AttendanceSession
from app.models.user import Student
from app.services.attendance_stats import REPORT_SESSION_STATUSES, StatusCounts, session_date

__all__ = [
    "AttendanceRow",
    "AttendanceRate",
    "AbsenceStreak",
    "course_records",
    "student_records",
    "course_rates",
    "student_rates",
    "consecutive_absences",
    "absence_streak",
]


@dataclass(frozen=True)
class AttendanceRow:
    """One student's status in one closed session."""
    session_id: int
    occurrence_id: int
    class_type: str            # LECTURE | TUTORIAL
    class_label: str | None
    course_id: int
    course_code: str
    student_id: int            # students.id
    matric_no: str
    name: str
    date: date | None          # MYT date of the class (session_date)
    starts_at: datetime | None  # sess.starts_at or sess.opened_at
    status: str                # present | late | excused | absent
    detected_at: datetime | None
    overridden: bool           # a lecturer changed it (override_by set)


@dataclass(frozen=True)
class AttendanceRate:
    """One student's counts and rate for one course (all its classes together)."""
    student_id: int
    matric_no: str
    name: str
    course_id: int
    course_code: str
    course_name: str
    present: int
    late: int
    excused: int
    absent: int
    closed_sessions: int
    counted_sessions: int      # closed_sessions - excused
    rate: float | None         # percentage 0-100, 1 decimal; None when counted_sessions == 0


@dataclass(frozen=True)
class AbsenceStreak:
    """Consecutive absences of one student in one course."""
    student_id: int
    matric_no: str
    name: str
    course_id: int
    course_code: str
    current: int               # absences in a row up to the latest closed session (0 if they last attended)
    longest: int               # longest run of absences so far
    last_attended: date | None  # date of the latest present/late session; None if never


def absence_streak(statuses: list[str]) -> tuple[int, int]:
    """(current, longest) absence run over statuses ordered oldest first.
    absent adds 1; present/late reset the current run to 0; excused is skipped (neither breaks nor extends a run)."""
    current = 0
    longest = 0
    for s in statuses:
        if s == "absent":
            current += 1
            longest = max(longest, current)
        elif s in ATTENDED_STATUSES:
            current = 0
    return current, longest


@dataclass
class _Loaded:
    students: dict[int, Student]                 # students.id → Student (user loaded)
    occurrences: dict[int, ClassOccurrence]      # occurrence id → occurrence (course loaded)
    enrolled: set[tuple[int, int]]               # (student_id, course_id) pairs
    rows: list[AttendanceRow]


async def _load(
    db: AsyncSession,
    *,
    course_id: int | None = None,
    student_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> _Loaded:
    if from_date and to_date and from_date > to_date:
        raise ValueError("from_date must be on or before to_date")

    enrolment_query = (
        select(Enrollment.student_id, Enrollment.occurrence_id)
        .join(ClassOccurrence, ClassOccurrence.id == Enrollment.occurrence_id)
    )
    if course_id is not None:
        enrolment_query = enrolment_query.where(ClassOccurrence.course_id == course_id)
    if student_id is not None:
        enrolment_query = enrolment_query.where(Enrollment.student_id == student_id)

    enrolment_rows = (await db.execute(enrolment_query)).all()
    enrolled_by_occ: dict[int, list[int]] = {}
    for enrol_student_id, occurrence_id in enrolment_rows:
        enrolled_by_occ.setdefault(occurrence_id, []).append(enrol_student_id)

    if not enrolled_by_occ:
        return _Loaded({}, {}, set(), [])

    occurrences = (await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .where(ClassOccurrence.id.in_(enrolled_by_occ))
    )).scalars().all()
    occurrences_by_id = {occ.id: occ for occ in occurrences}

    all_student_ids = {sid for sids in enrolled_by_occ.values() for sid in sids}
    students = (await db.execute(
        select(Student)
        .options(selectinload(Student.user))
        .where(Student.id.in_(all_student_ids))
    )).scalars().all()
    students_by_id = {stu.id: stu for stu in students}

    enrolled = {
        (sid, occurrences_by_id[occ_id].course_id)
        for occ_id, sids in enrolled_by_occ.items()
        for sid in sids
    }

    sessions = (await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.occurrence_id.in_(list(enrolled_by_occ)),
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

    lookup: dict[tuple[int, int], AttendanceRecord] = {}
    if kept:
        record_query = select(AttendanceRecord).where(
            AttendanceRecord.session_id.in_([sess.id for sess in kept])
        )
        if student_id is not None:
            record_query = record_query.where(AttendanceRecord.student_id == student_id)
        records = (await db.execute(record_query)).scalars().all()
        lookup = {(rec.session_id, rec.student_id): rec for rec in records}

    rows: list[AttendanceRow] = []
    for sess in kept:
        occ = occurrences_by_id[sess.occurrence_id]
        for sid in enrolled_by_occ[sess.occurrence_id]:
            rec = lookup.get((sess.id, sid))
            student = students_by_id[sid]
            rows.append(AttendanceRow(
                session_id=sess.id,
                occurrence_id=occ.id,
                class_type=occ.type,
                class_label=occ.label,
                course_id=occ.course_id,
                course_code=occ.course.code,
                student_id=sid,
                matric_no=student.matric_no,
                name=student.user.name,
                date=session_date(sess),
                starts_at=sess.starts_at or sess.opened_at,
                status=rec.status if rec else "absent",
                detected_at=rec.detected_at if rec else None,
                overridden=bool(rec and rec.override_by),
            ))

    rows.sort(key=lambda r: (
        r.date or date.min, r.starts_at or datetime.min, r.session_id, r.matric_no,
    ))
    return _Loaded(students_by_id, occurrences_by_id, enrolled, rows)


def _rates(loaded: _Loaded) -> list[AttendanceRate]:
    counts: dict[tuple[int, int], StatusCounts] = {
        pair: StatusCounts() for pair in loaded.enrolled
    }
    for row in loaded.rows:
        counts[(row.student_id, row.course_id)].add(row.status)

    courses = {occ.course_id: occ.course for occ in loaded.occurrences.values()}
    out: list[AttendanceRate] = []
    for (student_id, course_id), c in counts.items():
        student = loaded.students[student_id]
        course = courses[course_id]
        out.append(AttendanceRate(
            student_id=student_id,
            matric_no=student.matric_no,
            name=student.user.name,
            course_id=course_id,
            course_code=course.code,
            course_name=course.name,
            present=c.present,
            late=c.late,
            excused=c.excused,
            absent=c.absent,
            closed_sessions=c.closed_sessions,
            counted_sessions=c.counted_sessions,
            rate=c.rate,
        ))
    return out


async def course_records(
    db: AsyncSession,
    course_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[AttendanceRow]:
    """Every enrolled student's status in every closed session of the course (all its classes),
    oldest session first, then by matric no. Dates are inclusive. ValueError if from_date > to_date."""
    return (
        await _load(db, course_id=course_id, from_date=from_date, to_date=to_date)
    ).rows


async def student_records(
    db: AsyncSession,
    student_id: int,
    course_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[AttendanceRow]:
    """One student's status in every closed session of the classes they are enrolled in,
    optionally for one course; oldest first."""
    return (
        await _load(
            db,
            student_id=student_id,
            course_id=course_id,
            from_date=from_date,
            to_date=to_date,
        )
    ).rows


async def course_rates(
    db: AsyncSession,
    course_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[AttendanceRate]:
    """Counts and rate per enrolled student for one course, ordered by matric no.
    Students with no closed sessions are included with rate None."""
    loaded = await _load(db, course_id=course_id, from_date=from_date, to_date=to_date)
    return sorted(_rates(loaded), key=lambda r: r.matric_no)


async def student_rates(
    db: AsyncSession,
    student_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[AttendanceRate]:
    """Counts and rate per course for one student, ordered by course code (courses with no
    closed sessions included, rate None)."""
    loaded = await _load(db, student_id=student_id, from_date=from_date, to_date=to_date)
    return sorted(_rates(loaded), key=lambda r: r.course_code)


async def consecutive_absences(
    db: AsyncSession,
    course_id: int,
    min_current: int = 0,
) -> list[AbsenceStreak]:
    """Absence streaks of every enrolled student in one course, keeping those with current >= min_current,
    ordered by current (highest first), then matric no."""
    loaded = await _load(db, course_id=course_id)
    courses = {occ.course_id: occ.course for occ in loaded.occurrences.values()}

    statuses: dict[int, list[str]] = {
        sid: [] for sid, cid in loaded.enrolled if cid == course_id
    }
    last_attended: dict[int, date | None] = {sid: None for sid in statuses}
    for row in loaded.rows:
        if row.student_id not in statuses:
            continue
        statuses[row.student_id].append(row.status)
        if row.status in ATTENDED_STATUSES:
            last_attended[row.student_id] = row.date

    out: list[AbsenceStreak] = []
    for sid, student_statuses in statuses.items():
        current, longest = absence_streak(student_statuses)
        if current < min_current:
            continue
        student = loaded.students[sid]
        out.append(AbsenceStreak(
            student_id=sid,
            matric_no=student.matric_no,
            name=student.user.name,
            course_id=course_id,
            course_code=courses[course_id].code,
            current=current,
            longest=longest,
            last_attended=last_attended[sid],
        ))
    out.sort(key=lambda s: (-s.current, s.matric_no))
    return out
