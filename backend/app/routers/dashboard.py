"""M2 role-scoped dashboard read contracts."""
from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_role
from app.core.timezone import now_myt
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.dashboard_cache import DashboardCache
from app.models.attendance import AttendanceRecord
from app.models.notification import Notification
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.schemas.notification import NotificationOut
from app.services.attendance_read import student_rates
from app.services.attendance_stats import session_date
from app.services.session_service import get_session_counts

router = APIRouter(tags=["dashboard"])


async def dashboard(db, user):
    today = now_myt().date()
    query = select(ClassOccurrence).options(selectinload(ClassOccurrence.course))
    student = None
    if user.role == "student":
        student = await db.scalar(select(Student).where(Student.user_id == user.id))
        query = query.join(Enrollment).where(Enrollment.student_id == (student.id if student else -1))
    else:
        lecturer = await db.scalar(select(Lecturer).where(Lecturer.user_id == user.id))
        query = query.where(ClassOccurrence.lecturer_id == (lecturer.id if lecturer else -1))
    occurrences = (await db.scalars(query)).unique().all()
    cache = await db.get(DashboardCache, user.id)
    moodle_ids = {o.course.moodle_course_id: o.course for o in occurrences if o.course.moodle_course_id}
    moodle = {"available": cache is not None, "refreshed_at": cache.refreshed_at if cache else None}
    for kind in ("announcements", "deadlines"):
        moodle[kind] = [{**item, "course_id": moodle_ids[item["course_id"]].id,
                        "course_code": moodle_ids[item["course_id"]].code}
                       for item in (cache.data.get(kind, []) if cache else []) if item["course_id"] in moodle_ids]
    ids = [o.id for o in occurrences]
    sessions = (await db.scalars(select(AttendanceSession).where(AttendanceSession.occurrence_id.in_(ids))
                               .order_by(AttendanceSession.id.desc()))).all()
    current = next((s for s in sessions if s.status == "open"), None)
    latest = current or next((s for s in sessions if s.status == "closed"), None)
    records = {}
    if student:
        records = {r.session_id: r.status for r in (await db.scalars(
            select(AttendanceRecord).where(AttendanceRecord.student_id == student.id,
                                            AttendanceRecord.session_id.in_([s.id for s in sessions]))
        )).all()}

    def own_status(session):
        if not student or session is None:
            return None
        return records.get(session.id, "absent" if session.status == "closed" else "not_recorded")

    def today_session(occurrence_id):
        return next((s for s in sessions if s.occurrence_id == occurrence_id and
                     session_date(s) == today
                     and s.status in ("open", "closed")), None)
    notes = (await db.scalars(select(Notification).where(Notification.user_id == user.id,
                            Notification.read_at.is_(None), Notification.priority.in_(["urgent", "important"]))
                            .order_by(Notification.id.desc()).limit(50))).all()
    return {
        "date": today,
        "today_classes": [{"occurrence_id": o.id, "course_id": o.course_id, "course_code": o.course.code,
                           "course_name": o.course.name, "start_time": o.start_time, "end_time": o.end_time,
                           "room": o.room, "attendance_status": own_status(today_session(o.id))}
                          for o in occurrences if o.day_of_week == today.strftime("%a") or today_session(o.id)],
        "session": ({"id": latest.id, "occurrence_id": latest.occurrence_id, "status": latest.status,
                     "starts_at": latest.starts_at, "ends_at": latest.ends_at,
                     "attendance_status": own_status(latest),
                     "counts": await get_session_counts(latest.id, db) if user.role == "lecturer" else None}
                    if latest else None),
        "attendance_rates": [asdict(rate) for rate in await student_rates(db, student.id)] if student else [],
        "notifications": [NotificationOut.model_validate(n) for n in notes],
        "participation": None, "quizzes": None, "at_risk": None,
        "moodle": moodle,
    }


@router.get("/student/me/dashboard")
async def student_dashboard(db: AsyncSession = Depends(get_db), user: User = Depends(require_role("student"))):
    return await dashboard(db, user)


@router.get("/lecturer/dashboard")
async def lecturer_dashboard(db: AsyncSession = Depends(get_db), user: User = Depends(require_role("lecturer"))):
    return await dashboard(db, user)
