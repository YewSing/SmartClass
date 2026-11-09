"""Student face-data consent (FR-109, FR-116, NFR-03) and face self-enrolment (FR-110–FR-115)."""
import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_role
from app.core.timezone import now_myt
from app.models.consent import FaceConsent
from app.models.face import FaceEmbedding
from app.models.face_enrolment import FaceEnrolment, FaceEnrolmentImage
from app.models.user import Student, User
from app.schemas.consent import FaceConsentIn, FaceConsentOut
from app.schemas.face_enrolment import FaceEnrolmentOut
from app.services import face_enrolment_service as enrolment_service
from app.services import face_verification
from app.services.audit_service import write_log
from app.services.consent_service import active_consent, require_current_consent

router = APIRouter(prefix="/student/me", tags=["student-face"])

MIN_SELFIE_FACES = 3  # FR-110: fewer selfies with a face than this is a retake

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
    withdrawn = await enrolment_service.withdraw_pending(db, student.id)
    await write_log(
        db, user.id, "FACE_CONSENT_WITHDRAW", "student", user.id,
        old_val={"version": current.version},
        new_val={"embeddings_deleted": deleted.rowcount, "pending_submissions_withdrawn": withdrawn},
    )


# ── face self-enrolment (FR-110–FR-115) ──────────────────────────────────────

@router.get("/face-enrolment", response_model=FaceEnrolmentOut)
async def get_face_enrolment(db: AsyncSession = Depends(get_db), user: User = Depends(_student_only)):
    """The student's enrolment status and any rejection reason (FR-115)."""
    student = await _student(db, user)
    return await enrolment_service.enrolment_status(db, student.id)


def _retake(reasons: list[str], message: str, blocked: int = 0) -> JSONResponse:
    can_anyway = blocked >= settings.FACE_ENROL_BLOCKS_BEFORE_SUBMIT_ANYWAY
    # Returned, not raised, so a recorded blocked attempt is still committed.
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": {
        "reasons": reasons, "message": message,
        "blocked_attempts": blocked, "can_submit_anyway": can_anyway,
    }})


async def _read(upload: UploadFile) -> bytes:
    data = await upload.read(settings.FACE_ENROL_MAX_IMAGE_BYTES + 1)
    if len(data) > settings.FACE_ENROL_MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="A photo is too large. Each photo must be under "
                                   f"{settings.FACE_ENROL_MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    return data


def _verify(face_app, selfies: list[bytes], card: bytes, matric: str, name: str):
    """FR-111 checks, or None when a photo isn't an image. CPU-heavy, so run in a thread."""
    if any(face_verification.decode_image(b) is None for b in [card, *selfies]):
        return None
    return face_verification.verify_card(face_app, selfies, card, matric, name)


def _check_reasons(v: face_verification.CardVerification) -> list[str]:
    """Why a submission wasn't auto-approved, for the lecturer's review (FR-113)."""
    reasons = []
    if not v.face.passed:
        reasons.append(v.face.reason or "face_mismatch")
    if v.face.selfie_faces < v.face.selfie_count:
        reasons.append("selfie_without_face")
    elif not v.face.selfies_consistent:
        reasons.append("selfies_inconsistent")
    if not v.card.matric_match:
        reasons.append("matric_unreadable" if v.card.matric is None else "matric_mismatch")
    if not v.card.name_match:
        reasons.append("name_mismatch")
    if not v.card.um_card:
        reasons.append("not_um_card")
    return reasons + [r for r in v.quality.reasons if r not in reasons]


# Magic bytes of the formats a phone camera produces; anything else is served as plain bytes.
_IMAGE_SIGNATURES = [(b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png")]


def _image_content_type(data: bytes) -> str:
    """The stored photo's type comes from its bytes, never from what the client claimed."""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return next((t for sig, t in _IMAGE_SIGNATURES if data.startswith(sig)), "application/octet-stream")


@router.post("/face-enrolment", response_model=FaceEnrolmentOut, status_code=status.HTTP_201_CREATED)
async def submit_face_enrolment(
    request: Request,
    selfies: list[UploadFile] = File(...),
    card: UploadFile = File(...),
    submit_anyway: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_student_only),
):
    """3–5 selfies + a matric card photo (FR-110). Both FR-111 checks pass → embeddings stored and
    status active (FR-112), with no photo kept. Otherwise → pending_review for a lecturer (FR-113),
    keeping the photos only until that decision (NFR-01).

    A card photo that fails the quality check is refused with 422 and the reasons, and nothing but
    the attempt is recorded. After FACE_ENROL_BLOCKS_BEFORE_SUBMIT_ANYWAY such refusals the student
    may send `submit_anyway=true`, which goes to review instead of being refused again.
    """
    student = await _student(db, user)
    await require_current_consent(db, student.id)  # NFR-03, and to the notice as it reads now
    if await enrolment_service.has_embeddings(db, student.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Your face is already enrolled.")
    last = await enrolment_service.latest_submission(db, student.id)
    if last is not None and last.status == "pending_review":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Your enrolment is already waiting for a lecturer's review.")
    if not 3 <= len(selfies) <= 5:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Take 3 to 5 selfies.")

    face_app = request.app.state.face_app
    if face_app is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Face recognition model not loaded")

    selfie_bytes = [await _read(s) for s in selfies]
    card_bytes = await _read(card)
    verification = await asyncio.to_thread(
        _verify, face_app, selfie_bytes, card_bytes, student.matric_no, user.name)
    if verification is None:
        return _retake(["not_an_image"], enrolment_service.NOT_AN_IMAGE_MESSAGE)
    selfie_emb = verification.face.selfie_embedding
    if selfie_emb is None or verification.face.selfie_faces < MIN_SELFIE_FACES:
        return _retake(["no_face_in_selfies"], enrolment_service.NO_SELFIE_FACE_MESSAGE)

    blocked = await enrolment_service.blocked_attempts(db, student.id)
    allow_anyway = submit_anyway and blocked >= settings.FACE_ENROL_BLOCKS_BEFORE_SUBMIT_ANYWAY
    if verification.quality.blocking and not allow_anyway:
        db.add(FaceEnrolment(student_id=student.id, status="blocked", submitted_at=now_myt(),
                             check_reasons=verification.quality.reasons,
                             quality_scores=verification.quality.scores))
        return _retake(verification.quality.reasons, verification.quality.message, blocked + 1)

    now = now_myt()
    enrolment = FaceEnrolment(
        student_id=student.id, submitted_at=now,
        submitted_anyway=verification.quality.blocking,
        face_score=verification.face.score,
        ocr_matric=verification.card.matric,
        ocr_matric_confidence=verification.card.matric_confidence,
        name_score=verification.card.name_score,
        quality_scores=verification.quality.scores,
    )
    if verification.passed:
        enrolment.status, enrolment.decided_at, enrolment.check_reasons = "active", now, []
        db.add(enrolment)
        await db.execute(delete(FaceEmbedding).where(FaceEmbedding.student_id == student.id))
        db.add(FaceEmbedding(student_id=student.id, embedding=selfie_emb.tolist()))
        await db.flush()
        await write_log(db, user.id, "FACE_ENROL_AUTO_APPROVE", "student", user.id,
                        new_val={"enrolment_id": enrolment.id, "face_score": verification.face.score})
    else:
        enrolment.status = "pending_review"
        enrolment.check_reasons = _check_reasons(verification)
        if enrolment.submitted_anyway:
            enrolment.check_reasons.append("submitted_anyway")
        enrolment.ocr_lines = verification.card.lines
        enrolment.embedding = selfie_emb.tolist()
        db.add(enrolment)
        await db.flush()
        uploads = [("selfie", i, b) for i, b in enumerate(selfie_bytes)]
        uploads.append(("card", 0, card_bytes))
        for kind, position, data in uploads:
            db.add(FaceEnrolmentImage(enrolment_id=enrolment.id, kind=kind, position=position,
                                      content_type=_image_content_type(data), data=data))
        await write_log(db, user.id, "FACE_ENROL_SUBMIT", "student", user.id,
                        new_val={"enrolment_id": enrolment.id, "reasons": enrolment.check_reasons})
    await db.flush()
    return await enrolment_service.enrolment_status(db, student.id)
