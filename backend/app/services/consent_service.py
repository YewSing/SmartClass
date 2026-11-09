"""PDPA face-data consent (FR-109, FR-116, NFR-03)."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import FaceConsent


async def active_consent(db: AsyncSession, student_id: int) -> FaceConsent | None:
    """The student's current (not withdrawn) consent, newest first, or None."""
    return (await db.execute(
        select(FaceConsent)
        .where(FaceConsent.student_id == student_id, FaceConsent.withdrawn_at.is_(None))
        .order_by(FaceConsent.accepted_at.desc(), FaceConsent.id.desc())
        .limit(1)
    )).scalar_one_or_none()


async def require_active_consent(db: AsyncSession, student_id: int) -> FaceConsent:
    """NFR-03: no face data may be stored for a student without a recorded consent."""
    consent = await active_consent(db, student_id)
    if consent is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The student has not given consent for face data",
        )
    return consent
