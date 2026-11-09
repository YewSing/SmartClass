"""Student face-data consent (FR-109, FR-116, NFR-03)."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_role
from app.core.timezone import now_myt
from app.models.consent import FaceConsent
from app.models.face import FaceEmbedding
from app.models.user import Student, User
from app.schemas.consent import FaceConsentIn, FaceConsentOut
from app.services.audit_service import write_log
from app.services.consent_service import active_consent

router = APIRouter(prefix="/student/me", tags=["student-face"])

_student_only = require_role("student")


async def _student(db: AsyncSession, user: User) -> Student:
    student = (await db.execute(select(Student).where(Student.user_id == user.id))).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    return student


def _out(consent: FaceConsent | None) -> FaceConsentOut:
    return FaceConsentOut(
        active=consent is not None,
        version=consent.version if consent else None,
        accepted_at=consent.accepted_at if consent else None,
        current_version=settings.FACE_CONSENT_VERSION,
    )


@router.get("/face-consent", response_model=FaceConsentOut)
async def get_face_consent(db: AsyncSession = Depends(get_db), user: User = Depends(_student_only)):
    student = await _student(db, user)
    return _out(await active_consent(db, student.id))


@router.post("/face-consent", response_model=FaceConsentOut)
async def give_face_consent(
    body: FaceConsentIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_student_only),
):
    """Record that the student accepted the current PDPA notice (FR-109). Re-accepting the same
    version is a no-op (200); a new acceptance is 201."""
    if body.version != settings.FACE_CONSENT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This consent notice is out of date. Please read the current notice and accept again.",
        )
    student = await _student(db, user)
    current = await active_consent(db, student.id)
    if current is not None and current.version == body.version:
        response.status_code = status.HTTP_200_OK
        return _out(current)

    now = now_myt()
    if current is not None:  # accepting a newer notice replaces the old consent
        current.withdrawn_at = now
    consent = FaceConsent(student_id=student.id, version=body.version, accepted_at=now)
    db.add(consent)
    await db.flush()
    await write_log(db, user.id, "FACE_CONSENT_GIVE", "student", user.id, new_val={"version": body.version})
    response.status_code = status.HTTP_201_CREATED
    return _out(consent)


@router.delete("/face-consent", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_face_consent(db: AsyncSession = Depends(get_db), user: User = Depends(_student_only)):
    """Withdraw consent and delete the student's face embeddings at once (FR-116, NFR-03)."""
    student = await _student(db, user)
    current = await active_consent(db, student.id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active face-data consent")

    current.withdrawn_at = now_myt()
    deleted = await db.execute(delete(FaceEmbedding).where(FaceEmbedding.student_id == student.id))
    await write_log(
        db, user.id, "FACE_CONSENT_WITHDRAW", "student", user.id,
        old_val={"version": current.version}, new_val={"embeddings_deleted": deleted.rowcount},
    )
