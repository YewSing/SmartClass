from app.core.timezone import MYT
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, Student, Lecturer
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.face import FaceEmbedding
from app.schemas.class_ import OccurrenceOut, OccurrenceStudentOut

_DAY_MAP = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}

router = APIRouter(prefix="/classes", tags=["classes"])


def _occurrence_to_out(occ: ClassOccurrence, enrolled_count: int = 0) -> OccurrenceOut:
    return OccurrenceOut(
        id=occ.id,
        course_id=occ.course_id,
        course_code=occ.course.code,
        course_name=occ.course.name,
        type=occ.type,
        day_of_week=occ.day_of_week,
        start_time=occ.start_time,
        end_time=occ.end_time,
        room=occ.room,
        lecturer_id=occ.lecturer_id,
        lecturer_name=occ.lecturer.user.name if occ.lecturer else None,
        label=occ.label,
        enrolled_count=enrolled_count,
    )


@router.get("", response_model=list[OccurrenceOut])
async def list_classes(
    full: bool = Query(False, description="Return all occurrences without the time gate (lecturer only)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lecturers see their assigned occurrences. Students see enrolled. Admins see all."""
    opts = [
        selectinload(ClassOccurrence.course),
        selectinload(ClassOccurrence.lecturer).selectinload(Lecturer.user),
        selectinload(ClassOccurrence.enrollments),
    ]

    if current_user.role == "lecturer":
        lec_result = await db.execute(select(Lecturer).where(Lecturer.user_id == current_user.id))
        lec = lec_result.scalar_one_or_none()
        if not lec:
            return []
        result = await db.execute(
            select(ClassOccurrence)
            .options(*opts)
            .where(ClassOccurrence.lecturer_id == lec.id)
        )
        occurrences = result.scalars().all()

        if not full and not settings.DEV_BYPASS_TIME_CHECK:
            now = datetime.now(MYT)
            today = _DAY_MAP[now.weekday()]
            current_time = now.strftime("%H:%M")
            occurrences = [
                o for o in occurrences
                if o.day_of_week == today
                and o.start_time <= current_time <= o.end_time
            ]

        return [_occurrence_to_out(o, len(o.enrollments)) for o in occurrences]

    elif current_user.role == "student":
        stu_result = await db.execute(select(Student).where(Student.user_id == current_user.id))
        stu = stu_result.scalar_one_or_none()
        if not stu:
            return []
        result = await db.execute(
            select(ClassOccurrence)
            .options(*opts)
            .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
            .where(Enrollment.student_id == stu.id)
        )
    else:
        result = await db.execute(select(ClassOccurrence).options(*opts))

    occurrences = result.scalars().all()
    return [_occurrence_to_out(o, len(o.enrollments)) for o in occurrences]


@router.get("/{class_id}/students", response_model=list[OccurrenceStudentOut])
async def list_class_students(
    class_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    occ_result = await db.execute(select(ClassOccurrence).where(ClassOccurrence.id == class_id))
    if not occ_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    result = await db.execute(
        select(Student)
        .options(selectinload(Student.user), selectinload(Student.face_embeddings))
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.occurrence_id == class_id)
        .order_by(Student.matric_no)
    )
    students = result.scalars().all()

    out = []
    for stu in students:
        fe = sorted(stu.face_embeddings, key=lambda e: e.created_at, reverse=True)
        out.append(OccurrenceStudentOut(
            id=stu.id,
            user_id=stu.user_id,
            matric_no=stu.matric_no,
            name=stu.user.name,
            face_enrolled=len(fe) > 0,
            face_enrolled_at=fe[0].created_at if fe else None,
        ))

    return out
