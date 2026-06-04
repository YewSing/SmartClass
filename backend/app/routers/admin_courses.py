from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, Student, Lecturer
from app.models.class_ import Course, ClassOccurrence, Enrollment
from app.models.face import FaceEmbedding
from app.schemas.class_ import CourseListOut, OccurrenceOut, OccurrenceStudentOut
from app.services.audit_service import write_log

router = APIRouter(prefix="/admin", tags=["admin-courses"])

_admin_only = require_role("admin")


@router.get("/courses", response_model=list[CourseListOut])
async def list_courses(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_only),
):
    courses_result = await db.execute(
        select(Course).options(selectinload(Course.occurrences)).order_by(Course.code)
    )
    courses = courses_result.scalars().all()

    out = []
    for course in courses:
        occurrence_ids = [o.id for o in course.occurrences]
        enrolled_count = 0
        if occurrence_ids:
            enrolled_result = await db.execute(
                select(func.count(Enrollment.id)).where(
                    Enrollment.occurrence_id.in_(occurrence_ids)
                )
            )
            enrolled_count = enrolled_result.scalar_one()

        out.append(CourseListOut(
            id=course.id,
            code=course.code,
            name=course.name,
            occurrence_count=len(course.occurrences),
            enrolled_count=enrolled_count,
        ))

    return out


@router.get("/courses/{course_id}/occurrences", response_model=list[OccurrenceOut])
async def list_course_occurrences(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_only),
):
    course_result = await db.execute(select(Course).where(Course.id == course_id))
    if not course_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    result = await db.execute(
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.course),
            selectinload(ClassOccurrence.lecturer).selectinload(Lecturer.user),
            selectinload(ClassOccurrence.enrollments),
        )
        .where(ClassOccurrence.course_id == course_id)
        .order_by(ClassOccurrence.type, ClassOccurrence.label)
    )
    occurrences = result.scalars().all()

    return [
        OccurrenceOut(
            id=o.id,
            course_id=o.course_id,
            course_code=o.course.code,
            course_name=o.course.name,
            type=o.type,
            day_of_week=o.day_of_week,
            start_time=o.start_time,
            end_time=o.end_time,
            room=o.room,
            lecturer_id=o.lecturer_id,
            lecturer_name=o.lecturer.user.name,
            label=o.label,
            enrolled_count=len(o.enrollments),
        )
        for o in occurrences
    ]


@router.get("/occurrences/{occurrence_id}/students", response_model=list[OccurrenceStudentOut])
async def list_occurrence_students(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_only),
):
    occ_result = await db.execute(select(ClassOccurrence).where(ClassOccurrence.id == occurrence_id))
    if not occ_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Occurrence not found")

    result = await db.execute(
        select(Student)
        .options(selectinload(Student.user), selectinload(Student.face_embeddings))
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.occurrence_id == occurrence_id)
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


@router.post("/occurrences/{occurrence_id}/students/{student_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def enroll_student_in_occurrence(
    occurrence_id: int,
    student_user_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    occ_result = await db.execute(select(ClassOccurrence).where(ClassOccurrence.id == occurrence_id))
    if not occ_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Occurrence not found")

    stu_result = await db.execute(select(Student).where(Student.user_id == student_user_id))
    student = stu_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    existing = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.occurrence_id == occurrence_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already enrolled")

    db.add(Enrollment(student_id=student.id, occurrence_id=occurrence_id))
    await write_log(db, actor.id, "ENROLL_ADD", "student", student_user_id, new_val={"occurrence_id": occurrence_id})


@router.delete("/occurrences/{occurrence_id}/students/{student_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unenroll_student_from_occurrence(
    occurrence_id: int,
    student_user_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    stu_result = await db.execute(select(Student).where(Student.user_id == student_user_id))
    student = stu_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    enroll_result = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.occurrence_id == occurrence_id,
        )
    )
    enrollment = enroll_result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not enrolled")

    await db.delete(enrollment)
    await write_log(db, actor.id, "ENROLL_REMOVE", "student", student_user_id, old_val={"occurrence_id": occurrence_id})
