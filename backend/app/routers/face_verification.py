"""Face verification queue (FR-113, FR-117).

Submissions that failed a FR-111 check wait here. Lecturers of any of the student's courses
review them; admins can review any of them as the fallback. Each decision is audited and the
submission's photos, card text and pending embedding are deleted at once (NFR-01).
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.core.timezone import now_myt
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.face import FaceEmbedding
from app.models.face_enrolment import FaceEnrolment, FaceEnrolmentImage
from app.models.user import Lecturer, Student, User
from app.schemas.face_enrolment import PendingEnrolmentOut, RejectIn, ReviewImageOut
from app.services import face_enrolment_service as enrolment_service
from app.services.audit_service import write_log
from app.services.consent_service import require_active_consent

router = APIRouter(prefix="/face-verification", tags=["face-verification"])

_reviewer = require_role("lecturer", "admin")


async def _shared_courses(db: AsyncSession, actor: User, student_id: int) -> list[str]:
    """Codes of the student's courses. For a lecturer, only those they teach any class of."""
    query = (
        select(Course.code).distinct()
        .join(ClassOccurrence, ClassOccurrence.course_id == Course.id)
        .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
        .where(Enrollment.student_id == student_id)
    )
    if actor.role != "admin":
        taught = (
            select(ClassOccurrence.course_id)
            .join(Lecturer, Lecturer.id == ClassOccurrence.lecturer_id)
            .where(Lecturer.user_id == actor.id)
        )
        query = query.where(Course.id.in_(taught))
    return sorted((await db.execute(query)).scalars().all())


async def _load(db: AsyncSession, actor: User, enrolment_id: int) -> tuple[FaceEnrolment, Student, list[str]]:
    """The submission, its student and the shared courses; 404 unknown, 403 not the actor's student."""
    enrolment = await db.get(FaceEnrolment, enrolment_id)
    if enrolment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    student = await db.get(Student, enrolment.student_id)
    courses = await _shared_courses(db, actor, student.id)
    if actor.role != "admin" and not courses:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="This student is not in any of your courses")
    return enrolment, student, courses


def _require_pending(enrolment: FaceEnrolment) -> None:
    if enrolment.status != "pending_review":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This submission has already been decided")


async def _out(db: AsyncSession, enrolment: FaceEnrolment, student: Student, courses: list[str]) -> PendingEnrolmentOut:
    user = await db.get(User, student.user_id)
    images = (await db.execute(
        select(FaceEnrolmentImage.id, FaceEnrolmentImage.kind, FaceEnrolmentImage.position)
        .where(FaceEnrolmentImage.enrolment_id == enrolment.id)
        .order_by(FaceEnrolmentImage.kind.desc(), FaceEnrolmentImage.position)  # selfies, then card
    )).all()
    return PendingEnrolmentOut(
        id=enrolment.id, student_user_id=user.id, student_name=user.name, matric_no=student.matric_no,
        courses=courses, submitted_at=enrolment.submitted_at, submitted_anyway=enrolment.submitted_anyway,
        check_reasons=enrolment.check_reasons or [], face_score=enrolment.face_score,
        ocr_matric=enrolment.ocr_matric, ocr_matric_confidence=enrolment.ocr_matric_confidence,
        name_score=enrolment.name_score, ocr_lines=enrolment.ocr_lines or [],
        quality_scores=enrolment.quality_scores,
        images=[ReviewImageOut(id=i.id, kind=i.kind, position=i.position,
                               url=f"/face-verification/{enrolment.id}/images/{i.id}") for i in images],
    )


@router.get("/pending", response_model=list[PendingEnrolmentOut])
async def list_pending(db: AsyncSession = Depends(get_db), actor: User = Depends(_reviewer)):
    """Submissions waiting for review, oldest first: a lecturer's own students, or all for an admin."""
    pending = (await db.execute(
        select(FaceEnrolment, Student)
        .join(Student, Student.id == FaceEnrolment.student_id)
        .where(FaceEnrolment.status == "pending_review")
        .order_by(FaceEnrolment.submitted_at, FaceEnrolment.id)
    )).all()
    out = []
    for enrolment, student in pending:
        courses = await _shared_courses(db, actor, student.id)
        if actor.role == "admin" or courses:
            out.append(await _out(db, enrolment, student, courses))
    return out


@router.get("/{enrolment_id}/images/{image_id}")
async def get_image(
    enrolment_id: int, image_id: int,
    db: AsyncSession = Depends(get_db), actor: User = Depends(_reviewer),
):
    """One selfie or card photo of a pending submission. Never cached (NFR-01)."""
    await _load(db, actor, enrolment_id)
    image = await db.get(FaceEnrolmentImage, image_id)
    if image is None or image.enrolment_id != enrolment_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return Response(content=image.data, media_type=image.content_type,
                    headers={"Cache-Control": "no-store"})


async def _decide(db: AsyncSession, enrolment: FaceEnrolment, new_status: str, reason: str | None) -> int:
    enrolment.status = new_status
    enrolment.reason = reason
    enrolment.decided_at = now_myt()
    enrolment.embedding = None
    return await enrolment_service.clear_review_data(db, enrolment)


@router.post("/{enrolment_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve(enrolment_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_reviewer)):
    """The selfie matches the card: store the face embedding (status active)."""
    enrolment, student, _ = await _load(db, actor, enrolment_id)
    _require_pending(enrolment)
    await require_active_consent(db, student.id)  # NFR-03
    if enrolment.embedding is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This submission has no face data to approve")

    embedding = list(enrolment.embedding)
    await db.execute(delete(FaceEmbedding).where(FaceEmbedding.student_id == student.id))
    db.add(FaceEmbedding(student_id=student.id, embedding=embedding))
    photos = await _decide(db, enrolment, "active", None)
    await write_log(db, actor.id, "FACE_ENROL_APPROVE", "student", student.user_id,
                    new_val={"enrolment_id": enrolment.id, "photos_deleted": photos})


@router.post("/{enrolment_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject(
    enrolment_id: int, body: RejectIn,
    db: AsyncSession = Depends(get_db), actor: User = Depends(_reviewer),
):
    """Not the student's card or face: the student sees `reason` and may submit again (FR-114)."""
    enrolment, student, _ = await _load(db, actor, enrolment_id)
    _require_pending(enrolment)
    photos = await _decide(db, enrolment, "rejected", body.reason)
    await write_log(db, actor.id, "FACE_ENROL_REJECT", "student", student.user_id,
                    new_val={"enrolment_id": enrolment.id, "reason": body.reason, "photos_deleted": photos})
