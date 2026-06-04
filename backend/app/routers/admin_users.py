from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_role
from app.core.security import hash_password
from app.models.user import User, Student, Lecturer
from app.models.face import FaceEmbedding
from app.models.class_ import ClassOccurrence, Enrollment
from app.schemas.user import (
    UserDetailOut, UserCreateRequest, UserUpdateRequest,
    AdminPasswordResetRequest, UserListOut, OccurrenceEnrollmentOut,
)
from app.services.audit_service import write_log

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

_admin_only = require_role("admin")


async def _build_user_detail(user: User, db: AsyncSession) -> UserDetailOut:
    face_enrolled = False
    face_enrolled_at = None
    enrolled_classes = []

    if user.role == "student" and user.student:
        fe_result = await db.execute(
            select(FaceEmbedding)
            .where(FaceEmbedding.student_id == user.student.id)
            .order_by(FaceEmbedding.created_at.desc())
            .limit(1)
        )
        fe = fe_result.scalar_one_or_none()
        if fe:
            face_enrolled = True
            face_enrolled_at = fe.created_at

        occ_result = await db.execute(
            select(ClassOccurrence)
            .options(selectinload(ClassOccurrence.course))
            .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
            .where(Enrollment.student_id == user.student.id)
            .order_by(ClassOccurrence.id)
        )
        raw_occs = occ_result.scalars().all()
        enrolled_classes = [
            OccurrenceEnrollmentOut(
                id=o.id,
                course_code=o.course.code,
                course_name=o.course.name,
                type=o.type,
                label=o.label,
                day_of_week=o.day_of_week,
                start_time=o.start_time,
                end_time=o.end_time,
            )
            for o in raw_occs
        ]

    elif user.role == "lecturer" and user.lecturer:
        occ_result = await db.execute(
            select(ClassOccurrence)
            .options(selectinload(ClassOccurrence.course))
            .where(ClassOccurrence.lecturer_id == user.lecturer.id)
            .order_by(ClassOccurrence.id)
        )
        raw_occs = occ_result.scalars().all()
        enrolled_classes = [
            OccurrenceEnrollmentOut(
                id=o.id,
                course_code=o.course.code,
                course_name=o.course.name,
                type=o.type,
                label=o.label,
                day_of_week=o.day_of_week,
                start_time=o.start_time,
                end_time=o.end_time,
            )
            for o in raw_occs
        ]

    return UserDetailOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        phone=user.phone,
        status=user.status,
        created_at=user.created_at,
        face_enrolled=face_enrolled,
        face_enrolled_at=face_enrolled_at,
        student=user.student,
        lecturer=user.lecturer,
        enrolled_classes=enrolled_classes,
    )


@router.get("", response_model=UserListOut)
async def list_users(
    role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_only),
):
    q = select(User).options(selectinload(User.student), selectinload(User.lecturer))
    if role:
        q = q.where(User.role == role)
    q = q.order_by(User.created_at.desc())

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    q = q.offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    users = result.scalars().all()

    items = [await _build_user_detail(u, db) for u in users]
    return UserListOut(items=items, total=total, page=page, limit=limit)


@router.post("", response_model=UserDetailOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if body.role not in ("admin", "lecturer", "student"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    if body.role == "student" and not body.matric_no:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="matric_no required for student")
    if body.role == "lecturer" and not body.staff_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="staff_id required for lecturer")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        name=body.name,
        phone=body.phone,
        status="active",
    )
    db.add(user)
    await db.flush()  # get user.id before inserting profile rows

    if body.role == "student":
        db.add(Student(
            user_id=user.id,
            matric_no=body.matric_no,
            programme=body.programme,
            faculty=body.faculty,
            year_sem=body.year_sem,
        ))
    elif body.role == "lecturer":
        db.add(Lecturer(
            user_id=user.id,
            staff_id=body.staff_id,
            dept=body.dept,
        ))

    await write_log(db, actor.id, "USER_CREATE", "user", user.id, new_val={"email": user.email, "role": user.role})
    await db.flush()

    # Reload with relationships
    result = await db.execute(
        select(User).options(selectinload(User.student), selectinload(User.lecturer)).where(User.id == user.id)
    )
    user = result.scalar_one()
    return await _build_user_detail(user, db)


@router.get("/{user_id}", response_model=UserDetailOut)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_only),
):
    result = await db.execute(
        select(User).options(selectinload(User.student), selectinload(User.lecturer)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return await _build_user_detail(user, db)


@router.put("/{user_id}", response_model=UserDetailOut)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    result = await db.execute(
        select(User).options(selectinload(User.student), selectinload(User.lecturer)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old = {"name": user.name, "phone": user.phone, "status": user.status}

    if body.name is not None:
        user.name = body.name
    if body.phone is not None:
        user.phone = body.phone
    if body.status is not None:
        user.status = body.status

    if user.student:
        if body.programme is not None:
            user.student.programme = body.programme
        if body.faculty is not None:
            user.student.faculty = body.faculty
        if body.year_sem is not None:
            user.student.year_sem = body.year_sem
    if user.lecturer:
        if body.dept is not None:
            user.lecturer.dept = body.dept

    await write_log(db, actor.id, "USER_UPDATE", "user", user_id, old_val=old, new_val=body.model_dump(exclude_none=True))
    return await _build_user_detail(user, db)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == actor.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    user.status = "inactive"
    await write_log(db, actor.id, "USER_DEACTIVATE", "user", user_id, old_val={"status": "active"}, new_val={"status": "inactive"})


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def admin_reset_password(
    user_id: int,
    body: AdminPasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = hash_password(body.new_password)
    await write_log(db, actor.id, "PASSWORD_RESET", "user", user_id)
