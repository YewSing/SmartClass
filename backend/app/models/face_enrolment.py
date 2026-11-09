from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FaceEnrolment(Base):
    """One face self-enrolment submission by a student (FR-110–FR-115).

    status:
      blocked         the card photo failed the quality check (422); only the reasons are kept
      pending_review  a FR-111 check failed; waits for a lecturer (FR-113), photos kept until then
      active          both checks passed; the embedding went to face_embeddings (FR-112)
      rejected        a lecturer/admin rejected it (`reason` says why)
      withdrawn       the student withdrew consent before a decision (FR-116)
      reset           an admin reset the student's face data before a decision (FR-117)
    """
    __tablename__ = "face_enrolments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    decided_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text)  # rejection reason shown to the student
    # Why it wasn't auto-approved: failed checks and quality reason codes.
    check_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    submitted_anyway: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    face_score: Mapped[Optional[float]] = mapped_column(Float)
    ocr_matric: Mapped[Optional[str]] = mapped_column(String(50))
    ocr_matric_confidence: Mapped[Optional[float]] = mapped_column(Float)
    name_score: Mapped[Optional[float]] = mapped_column(Float)
    quality_scores: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    # Kept only while pending, cleared with the photos once decided (NFR-01).
    ocr_lines: Mapped[Optional[list[str]]] = mapped_column(JSON)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(512))


class FaceEnrolmentImage(Base):
    """A selfie or card photo of a pending submission. Deleted once it is decided (NFR-01)."""
    __tablename__ = "face_enrolment_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    enrolment_id: Mapped[int] = mapped_column(
        ForeignKey("face_enrolments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # selfie | card
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
