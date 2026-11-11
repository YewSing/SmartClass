"""Face self-enrolment state (FR-110–FR-115, NFR-01).

The status a student sees is derived, so it stays right however face data changed:
embeddings exist → active (also for admin enrolment); otherwise the latest decided or
pending submission says pending_review / rejected; anything else is not_enrolled.
"""
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timezone import now_myt
from app.models.face import FaceEmbedding
from app.models.face_enrolment import FaceEnrolment, FaceEnrolmentImage
from app.schemas.face_enrolment import FaceEnrolmentOut

NO_SELFIE_FACE_MESSAGE = "We couldn't see your face in the selfies. Face the camera in good light and retake."
NOT_AN_IMAGE_MESSAGE = "One of the photos couldn't be opened. Please retake it."


async def latest_submission(db: AsyncSession, student_id: int) -> FaceEnrolment | None:
    """The newest submission that wasn't blocked by the quality check."""
    return (await db.execute(
        select(FaceEnrolment)
        .where(FaceEnrolment.student_id == student_id, FaceEnrolment.status != "blocked")
        .order_by(FaceEnrolment.id.desc())
        .limit(1)
    )).scalar_one_or_none()


async def blocked_attempts(db: AsyncSession, student_id: int) -> int:
    """Blocked card photos since the last real submission (the "submit anyway" counter)."""
    last = await latest_submission(db, student_id)
    query = select(func.count()).select_from(FaceEnrolment).where(
        FaceEnrolment.student_id == student_id, FaceEnrolment.status == "blocked")
    if last is not None:
        query = query.where(FaceEnrolment.id > last.id)
    return await db.scalar(query)


async def has_embeddings(db: AsyncSession, student_id: int) -> bool:
    return bool(await db.scalar(
        select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.student_id == student_id)))


async def enrolment_status(db: AsyncSession, student_id: int) -> FaceEnrolmentOut:
    blocked = await blocked_attempts(db, student_id)
    can_anyway = blocked >= settings.FACE_ENROL_BLOCKS_BEFORE_SUBMIT_ANYWAY
    last = await latest_submission(db, student_id)
    times = {"submitted_at": last.submitted_at, "decided_at": last.decided_at} if last else {}

    if await has_embeddings(db, student_id):
        if last is None or last.status != "active":
            times = {}  # enrolled another way (admin), not through a submission
        return FaceEnrolmentOut(status="active", **times)
    if last is not None and last.status in ("pending_review", "rejected"):
        return FaceEnrolmentOut(status=last.status, reason=last.reason, blocked_attempts=blocked,
                                can_submit_anyway=can_anyway, **times)
    return FaceEnrolmentOut(status="not_enrolled", blocked_attempts=blocked, can_submit_anyway=can_anyway)


async def clear_review_data(db: AsyncSession, enrolment: FaceEnrolment) -> int:
    """Delete a submission's photos and card text once it is decided (NFR-01). Returns photos deleted.
    The matric number read from the card goes too: on a mismatched card it is someone else's."""
    result = await db.execute(delete(FaceEnrolmentImage).where(FaceEnrolmentImage.enrolment_id == enrolment.id))
    enrolment.ocr_lines = None
    enrolment.ocr_matric = None
    return result.rowcount


async def close_pending(db: AsyncSession, student_id: int, new_status: str) -> int:
    """Pending submissions lose their photos and embedding and get `new_status`.
    Used when consent is withdrawn (FR-116, "withdrawn") and on an admin reset (FR-117, "reset")."""
    pending = (await db.execute(
        select(FaceEnrolment).where(FaceEnrolment.student_id == student_id,
                                    FaceEnrolment.status == "pending_review")
    )).scalars().all()
    for enrolment in pending:
        await clear_review_data(db, enrolment)
        enrolment.status = new_status
        enrolment.decided_at = now_myt()
        enrolment.embedding = None
    return len(pending)


async def withdraw_pending(db: AsyncSession, student_id: int) -> int:
    """Consent withdrawn (FR-116): pending submissions lose their photos and embedding."""
    return await close_pending(db, student_id, "withdrawn")
