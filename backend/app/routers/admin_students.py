from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, Student
from app.models.face import FaceEmbedding
from app.models.class_ import ClassOccurrence, Enrollment
from app.services import face_service
from app.services.audit_service import write_log

router = APIRouter(prefix="/admin/students", tags=["admin-students"])

_admin_only = require_role("admin")


@router.post("/{student_user_id}/face-enroll", status_code=status.HTTP_204_NO_CONTENT)
async def enroll_face(
    student_user_id: int,
    request: Request,
    images: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    """
    Accept 1–5 face images, extract embeddings, average them, and upsert into
    face_embeddings. Raw image bytes are never written to disk (NFR-01).
    """
    if not 1 <= len(images) <= 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide 1 to 5 face images")

    stu_result = await db.execute(select(Student).where(Student.user_id == student_user_id))
    student = stu_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    face_app = request.app.state.face_app
    if face_app is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Face recognition model not loaded",
        )

    collected = []
    for img_file in images:
        img_bytes = await img_file.read()
        embeddings = face_service.extract_embeddings(face_app, img_bytes)
        if embeddings:
            collected.extend(embeddings)

    if not collected:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No face detected in any of the provided images",
        )

    avg_embedding = face_service.average_embeddings(collected)

    await db.execute(delete(FaceEmbedding).where(FaceEmbedding.student_id == student.id))
    db.add(FaceEmbedding(student_id=student.id, embedding=avg_embedding.tolist()))

    await write_log(db, actor.id, "FACE_ENROLL", "student", student_user_id)


@router.delete("/{student_user_id}/face-data", status_code=status.HTTP_204_NO_CONTENT)
async def remove_face_data(
    student_user_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    stu_result = await db.execute(select(Student).where(Student.user_id == student_user_id))
    student = stu_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    result = await db.execute(select(FaceEmbedding).where(FaceEmbedding.student_id == student.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No face data enrolled for this student")

    await db.execute(delete(FaceEmbedding).where(FaceEmbedding.student_id == student.id))
    await write_log(db, actor.id, "FACE_REMOVE", "student", student_user_id)


@router.post("/{student_user_id}/occurrences/{occurrence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def enroll_in_occurrence(
    student_user_id: int,
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    stu_result = await db.execute(select(Student).where(Student.user_id == student_user_id))
    student = stu_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    occ_result = await db.execute(select(ClassOccurrence).where(ClassOccurrence.id == occurrence_id))
    if not occ_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Occurrence not found")

    existing = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.occurrence_id == occurrence_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already enrolled in this occurrence")

    db.add(Enrollment(student_id=student.id, occurrence_id=occurrence_id))
    await write_log(db, actor.id, "ENROLL_ADD", "student", student_user_id, new_val={"occurrence_id": occurrence_id})


@router.delete("/{student_user_id}/occurrences/{occurrence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_occurrence(
    student_user_id: int,
    occurrence_id: int,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not enrolled in this occurrence")

    await db.delete(enrollment)
    await write_log(db, actor.id, "ENROLL_REMOVE", "student", student_user_id, old_val={"occurrence_id": occurrence_id})
