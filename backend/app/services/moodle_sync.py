"""Courses, enrolments and lecturer assignments from Moodle (SPeCTRUM) (FR-104, UC-M1 sync).

Mapping (T11):
- A Moodle course is a SmartClass `Course`, matched by `moodle_course_id`, else by
  `code == shortname` (the id is then filled in); unknown Moodle courses are created.
- The timetable (`ClassOccurrence`) stays SmartClass data: Moodle has none. A Moodle student
  is enrolled in every LECTURE occurrence, and in the tutorial when the course has only one;
  with several tutorial groups the admin picks the group.
- Only Moodle-linked accounts (`users.moodle_user_id`) are managed. Local accounts (seed data,
  admins) are never enrolled, removed or unassigned by a sync. Moodle users with no SmartClass
  account yet are counted as `unlinked`; their first login creates the account and syncs them.
- Everything is read from Moodle before the database is touched, so a Moodle failure changes
  nothing. Running a sync twice changes nothing the second time.
"""
import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.user import Lecturer, Student, User
from app.services.kb.moodle_client import MoodleClient

log = logging.getLogger(__name__)

TEACHER_ROLES = {"editingteacher", "teacher"}
STUDENT_ROLE = "student"
_CODE_MAX = Course.__table__.c.code.type.length

_full_sync_lock = asyncio.Lock()
last_sync: dict | None = None  # result of the last full sync, for the admin status view


@dataclass
class MoodleCourse:
    id: int
    shortname: str
    fullname: str
    students: set[int] = field(default_factory=set)   # Moodle user ids
    teachers: set[int] = field(default_factory=set)


@dataclass
class SyncReport:
    courses_created: int = 0
    courses_updated: int = 0
    enrolments_added: int = 0
    enrolments_removed: int = 0
    lecturers_assigned: int = 0
    lecturers_unassigned: int = 0
    unlinked_users: int = 0
    skipped: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any((self.courses_created, self.courses_updated, self.enrolments_added,
                    self.enrolments_removed, self.lecturers_assigned, self.lecturers_unassigned))


def course_from_enrolled(course: dict, enrolled: list[dict]) -> MoodleCourse:
    mc = MoodleCourse(id=int(course["id"]), shortname=(course.get("shortname") or "").strip(),
                      fullname=(course.get("fullname") or "").strip())
    for u in enrolled:
        roles = {r.get("shortname") for r in u.get("roles", [])}
        if roles & TEACHER_ROLES:
            mc.teachers.add(int(u["id"]))
        elif STUDENT_ROLE in roles:
            mc.students.add(int(u["id"]))
    return mc


async def fetch_all(client: MoodleClient) -> list[MoodleCourse]:
    """Every Moodle course with its students and teachers (service token)."""
    body = await client.call("core_course_get_courses_by_field")
    courses = []
    for c in body.get("courses", []):
        if c.get("format") == "site" or int(c["id"]) == 1:
            continue  # the front page, not a course
        enrolled = await client.call("core_enrol_get_enrolled_users", courseid=c["id"])
        courses.append(course_from_enrolled(c, enrolled))
    return courses


async def _linked_profiles(db: AsyncSession, moodle_user_id: int | None) -> tuple[dict, dict, dict]:
    """Moodle user id -> students.id / lecturers.id / users.role, for Moodle-linked accounts
    (all of them, or only `moodle_user_id`)."""
    q_stu = select(User.moodle_user_id, Student.id).join(Student, Student.user_id == User.id)
    q_lec = select(User.moodle_user_id, Lecturer.id).join(Lecturer, Lecturer.user_id == User.id)
    q_role = select(User.moodle_user_id, User.role, User.status)
    if moodle_user_id is None:
        q_stu, q_lec, q_role = (q.where(User.moodle_user_id.is_not(None)) for q in (q_stu, q_lec, q_role))
    else:
        q_stu, q_lec, q_role = (q.where(User.moodle_user_id == moodle_user_id) for q in (q_stu, q_lec, q_role))
    students = dict((await db.execute(q_stu)).all())
    lecturers = dict((await db.execute(q_lec)).all())
    roles = {m: role for m, role, st in (await db.execute(q_role)).all() if st == "active"}
    return students, lecturers, roles


async def _resolve_course(db: AsyncSession, mc: MoodleCourse, create: bool, report: SyncReport) -> Course | None:
    course = (await db.execute(select(Course).where(Course.moodle_course_id == mc.id))).scalar_one_or_none()
    if course is None and mc.shortname:
        course = (await db.execute(
            select(Course).where(Course.code == mc.shortname, Course.moodle_course_id.is_(None))
        )).scalar_one_or_none()
        if course is not None:
            course.moodle_course_id = mc.id
            report.courses_updated += 1
    if course is None:
        if not create:
            return None
        if not mc.shortname or len(mc.shortname) > _CODE_MAX:
            report.skipped.append(f"Moodle course {mc.id}: shortname {mc.shortname!r} can't be a course code")
            return None
        # ON CONFLICT: a login sync may create the same course at the same moment
        await db.execute(insert(Course).values(code=mc.shortname, name=mc.fullname or mc.shortname,
                                               moodle_course_id=mc.id).on_conflict_do_nothing())
        course = (await db.execute(select(Course).where(Course.code == mc.shortname))).scalar_one()
        if course.moodle_course_id != mc.id:
            report.skipped.append(f"Moodle course {mc.id}: code {mc.shortname} belongs to another Moodle course")
            return None
        report.courses_created += 1
    elif mc.fullname and course.name != mc.fullname:
        course.name = mc.fullname
        report.courses_updated += 1
    return course


async def _apply_course(db: AsyncSession, course: Course, mc: MoodleCourse,
                        students: dict, lecturers: dict, roles: dict, report: SyncReport) -> None:
    occs = (await db.execute(
        select(ClassOccurrence).where(ClassOccurrence.course_id == course.id).order_by(ClassOccurrence.id)
    )).scalars().all()
    if not occs:
        return
    occ_ids = [o.id for o in occs]
    tutorials = [o for o in occs if o.type == "TUTORIAL"]
    default_occ_ids = [o.id for o in occs if o.type != "TUTORIAL"] + ([tutorials[0].id] if len(tutorials) == 1 else [])

    # Students
    managed = set(students.values())
    wanted = {students[m] for m in mc.students if m in students and roles.get(m) == "student"}
    if managed:
        current = (await db.execute(
            select(Enrollment.id, Enrollment.student_id, Enrollment.occurrence_id)
            .where(Enrollment.occurrence_id.in_(occ_ids), Enrollment.student_id.in_(managed))
        )).all()
        drop = [eid for eid, sid, _ in current if sid not in wanted]
        if drop:
            await db.execute(delete(Enrollment).where(Enrollment.id.in_(drop)))
            report.enrolments_removed += len(drop)
        have = {(sid, oid) for _, sid, oid in current}
        add = [{"student_id": sid, "occurrence_id": oid}
               for sid in sorted(wanted) for oid in default_occ_ids if (sid, oid) not in have]
        if add:
            await db.execute(insert(Enrollment).values(add).on_conflict_do_nothing())
            report.enrolments_added += len(add)

    # Lecturers: unassign Moodle-linked lecturers who no longer teach it, fill empty occurrences
    managed_lec = set(lecturers.values())
    teaching = [lecturers[m] for m in sorted(mc.teachers) if m in lecturers and roles.get(m) == "lecturer"]
    for occ in occs:
        if occ.lecturer_id in managed_lec and occ.lecturer_id not in teaching:
            occ.lecturer_id = None
            report.lecturers_unassigned += 1
        if occ.lecturer_id is None and teaching:
            occ.lecturer_id = teaching[0]
            report.lecturers_assigned += 1


async def apply(db: AsyncSession, moodle_courses: list[MoodleCourse], moodle_user_id: int | None = None) -> SyncReport:
    """Make SmartClass match `moodle_courses`. With `moodle_user_id`, only that user's
    enrolments/assignments change, and `moodle_courses` is that user's course list.
    Flushes but does not commit."""
    report = SyncReport()
    students, lecturers, roles = await _linked_profiles(db, moodle_user_id)
    if moodle_user_id is None:
        known = set(students) | set(lecturers)
        report.unlinked_users = len({m for mc in moodle_courses for m in mc.students | mc.teachers} - known)

    seen_course_ids = set()
    for mc in moodle_courses:
        course = await _resolve_course(db, mc, create=True, report=report)
        if course is None:
            continue
        seen_course_ids.add(course.id)
        await _apply_course(db, course, mc, students, lecturers, roles, report)

    # Mapped courses missing from the list: deleted in Moodle, or no longer the user's
    gone = (await db.execute(
        select(Course).where(Course.moodle_course_id.is_not(None), Course.id.not_in(seen_course_ids or {0}))
    )).scalars().all()
    for course in gone:
        empty = MoodleCourse(id=course.moodle_course_id, shortname=course.code, fullname="")
        await _apply_course(db, course, empty, students, lecturers, roles, report)
    await db.flush()
    return report


async def sync_user(db: AsyncSession, user: User, moodle_courses: list[MoodleCourse]) -> SyncReport:
    """Login sync: the user's own courses, read with their own Moodle token."""
    report = await apply(db, moodle_courses, moodle_user_id=user.moodle_user_id)
    if report.changed:
        log.info("Moodle login sync user %s: %s", user.id, asdict(report))
    return report


async def sync_all(db: AsyncSession, client: MoodleClient | None = None) -> SyncReport:
    """Full sync with the service token. Raises (with the database untouched) if Moodle fails;
    the caller commits."""
    global last_sync
    async with _full_sync_lock:
        try:
            if client is None:
                async with MoodleClient(timeout=30.0) as own:
                    moodle_courses = await fetch_all(own)
            else:
                moodle_courses = await fetch_all(client)
            report = await apply(db, moodle_courses)
        except Exception as exc:
            last_sync = {"ok": False, "finished_at": _now(), "error": exc.__class__.__name__}
            raise
        last_sync = {"ok": True, "finished_at": _now(), **asdict(report)}
        return report


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def moodle_sync_loop() -> None:
    """Background task started in main.py; disabled without a Moodle token."""
    if not settings.MOODLE_TOKEN or settings.MOODLE_SYNC_INTERVAL_SECONDS <= 0:
        return
    while True:
        try:
            async with AsyncSessionLocal() as db:
                try:
                    report = await sync_all(db)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
            if report.changed:
                log.info("Moodle sync: %s", asdict(report))
        except Exception as exc:
            log.warning("Moodle sync failed: %s", exc.__class__.__name__)
        await asyncio.sleep(settings.MOODLE_SYNC_INTERVAL_SECONDS)
