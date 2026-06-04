"""
Face review queue — collects unrecognised faces flagged by the worker so an admin
can manually identify and promote them to enrollment (UC-07 / UC-08 alt flow).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_role
from app.models.face_review import FaceReviewEntry
from app.models.face import FaceEmbedding
from app.models.user import User, Student
from app.services.audit_service import write_log

router = APIRouter(tags=["face-review"])

_admin_only = require_role("admin")

# Cosine similarity threshold for merging into an existing review entry
_GROUP_THRESHOLD = 0.35


async def _verify_internal_key(x_internal_key: str = Header(...)) -> None:
    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal key")


# ── Schemas ───────────────────────────────────────────────────────────────────

class FaceReviewCreate(BaseModel):
    embedding: list[float]
    session_id: Optional[int] = None
    similarity: float = 0.0
    camera_device_id: Optional[str] = None


class FaceReviewOut(BaseModel):
    id: int
    session_id: Optional[int]
    camera_device_id: Optional[str]
    similarity: float
    occurrences: int
    flagged_at: str  # ISO string

    model_config = {"from_attributes": True}


class PromoteRequest(BaseModel):
    student_user_id: int


# ── Internal endpoint (worker → backend) ─────────────────────────────────────

@router.post("/internal/face-review", status_code=status.HTTP_204_NO_CONTENT)
async def report_unrecognised_face(
    body: FaceReviewCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_internal_key),
):
    """
    Called by the face worker when it detects a face that scores below the match
    threshold. Entries with similar embeddings are merged (occurrences++).
    """
    if len(body.embedding) != 512:
        raise HTTPException(status_code=400, detail="Embedding must be 512-dimensional")

    # Try to merge into an existing entry with similar embedding (same unrecognised person)
    merge_result = await db.execute(
        text(
            "SELECT id, similarity FROM face_review_entries "
            "WHERE (1 - (embedding <=> CAST(:vec AS vector))) >= :threshold "
            "ORDER BY embedding <=> CAST(:vec AS vector) "
            "LIMIT 1"
        ),
        {"vec": str(body.embedding), "threshold": _GROUP_THRESHOLD},
    )
    existing_row = merge_result.fetchone()

    if existing_row:
        entry_result = await db.execute(
            select(FaceReviewEntry).where(FaceReviewEntry.id == existing_row.id)
        )
        entry = entry_result.scalar_one()
        entry.occurrences += 1
        if body.similarity > entry.similarity:
            entry.similarity = body.similarity
            entry.embedding = body.embedding
        if body.session_id:
            entry.session_id = body.session_id
    else:
        db.add(FaceReviewEntry(
            embedding=body.embedding,
            session_id=body.session_id,
            camera_device_id=body.camera_device_id,
            similarity=body.similarity,
            occurrences=1,
        ))


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("/admin/face-review", response_model=list[FaceReviewOut])
async def list_review_queue(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    result = await db.execute(
        select(FaceReviewEntry).order_by(FaceReviewEntry.flagged_at.desc())
    )
    entries = result.scalars().all()
    return [
        FaceReviewOut(
            id=e.id,
            session_id=e.session_id,
            camera_device_id=e.camera_device_id,
            similarity=e.similarity,
            occurrences=e.occurrences,
            flagged_at=e.flagged_at.isoformat(),
        )
        for e in entries
    ]


@router.delete("/admin/face-review/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_review_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    result = await db.execute(
        select(FaceReviewEntry).where(FaceReviewEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Review entry not found")
    await db.delete(entry)
    await write_log(db, actor.id, "FACE_REVIEW_DISMISS", "face_review_entry", entry_id)


@router.post("/admin/face-review/{entry_id}/promote", status_code=status.HTTP_204_NO_CONTENT)
async def promote_review_entry(
    entry_id: int,
    body: PromoteRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    """Assign the review entry's embedding to the given student and delete the entry."""
    entry_result = await db.execute(
        select(FaceReviewEntry).where(FaceReviewEntry.id == entry_id)
    )
    entry = entry_result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Review entry not found")

    stu_result = await db.execute(
        select(Student).where(Student.user_id == body.student_user_id)
    )
    student = stu_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Upsert face embedding
    existing_emb = await db.execute(
        select(FaceEmbedding).where(FaceEmbedding.student_id == student.id)
    )
    emb = existing_emb.scalar_one_or_none()
    if emb:
        emb.embedding = entry.embedding
    else:
        db.add(FaceEmbedding(student_id=student.id, embedding=entry.embedding))

    await db.delete(entry)
    await write_log(
        db, actor.id, "FACE_PROMOTE",
        "face_review_entry", entry_id,
        new_val={"student_user_id": body.student_user_id},
    )
