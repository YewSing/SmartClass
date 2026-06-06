"""
Face review queue — collects unrecognised faces flagged by the worker so an admin
can manually identify and promote them to enrollment (UC-07 / UC-08 alt flow).
"""
from typing import Optional

from app.core.timezone import now_myt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_role
from app.models.face_review import FaceReviewEntry
from app.models.face import FaceEmbedding
from app.models.user import User, Student
from app.models.attendance import AttendanceRecord
from app.services.audit_service import write_log
from app.services.session_service import get_session_counts
from app.websocket.manager import manager

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
    closest_match_student_id: Optional[int] = None
    closest_match_name: Optional[str] = None
    closest_match_confidence: Optional[float] = None
    class_name: Optional[str] = None
    session_date: Optional[str] = None  # ISO string of session opened_at

    model_config = {"from_attributes": True}


class PromoteRequest(BaseModel):
    student_user_id: int
    mark_present: bool = False


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _find_closest_enrolled(db: AsyncSession, embedding: list[float]) -> tuple[Optional[int], Optional[float]]:
    """
    Returns (user_id, confidence) of the enrolled student whose face embedding
    is nearest to the given embedding, or (None, None) if no enrolled faces exist.
    """
    result = await db.execute(
        text("""
            SELECT s.user_id, (1 - (fe.embedding <=> CAST(:vec AS vector))) AS score
            FROM face_embeddings fe
            JOIN students s ON s.id = fe.student_id
            ORDER BY fe.embedding <=> CAST(:vec AS vector)
            LIMIT 1
        """),
        {"vec": str(embedding)},
    )
    row = result.fetchone()
    if row is None:
        return None, None
    return int(row.user_id), float(row.score)


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

    closest_user_id, closest_conf = await _find_closest_enrolled(db, body.embedding)

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

    should_broadcast = not existing_row  # always broadcast for brand-new entries

    if existing_row:
        entry_result = await db.execute(
            select(FaceReviewEntry).where(FaceReviewEntry.id == existing_row.id)
        )
        entry = entry_result.scalar_one()
        entry.occurrences += 1
        if body.similarity > entry.similarity:
            entry.similarity = body.similarity
            entry.embedding = body.embedding
            # Better embedding means a better closest-match reading
            entry.closest_match_student_id = closest_user_id
            entry.closest_match_confidence = closest_conf
        elif entry.closest_match_student_id is None and closest_user_id is not None:
            entry.closest_match_student_id = closest_user_id
            entry.closest_match_confidence = closest_conf
        if body.session_id and entry.session_id != body.session_id:
            # Entry is being reassigned to the current session — count changes
            should_broadcast = True
            entry.session_id = body.session_id
    else:
        db.add(FaceReviewEntry(
            embedding=body.embedding,
            session_id=body.session_id,
            camera_device_id=body.camera_device_id,
            similarity=body.similarity,
            occurrences=1,
            closest_match_student_id=closest_user_id,
            closest_match_confidence=closest_conf,
        ))

    if should_broadcast and body.session_id:
        await db.flush()
        counts = await get_session_counts(body.session_id, db)
        await manager.broadcast(body.session_id, {
            "event": "attendance_update",
            "session_id": body.session_id,
            "counts": counts,
        })


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("/admin/face-review", response_model=list[FaceReviewOut])
async def list_review_queue(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_admin_only),
):
    result = await db.execute(
        text("""
            SELECT
                fr.id,
                fr.session_id,
                fr.camera_device_id,
                fr.similarity,
                fr.occurrences,
                fr.flagged_at,
                fr.closest_match_student_id,
                fr.closest_match_confidence,
                u.name  AS closest_match_name,
                c.name  AS class_name,
                asess.opened_at AS session_opened_at
            FROM face_review_entries fr
            LEFT JOIN users u      ON u.id      = fr.closest_match_student_id
            LEFT JOIN attendance_sessions asess ON asess.id = fr.session_id
            LEFT JOIN class_occurrences co      ON co.id    = asess.occurrence_id
            LEFT JOIN courses c                 ON c.id     = co.course_id
            ORDER BY fr.flagged_at DESC
        """)
    )
    rows = result.fetchall()
    return [
        FaceReviewOut(
            id=row.id,
            session_id=row.session_id,
            camera_device_id=row.camera_device_id,
            similarity=row.similarity,
            occurrences=row.occurrences,
            flagged_at=row.flagged_at.isoformat(),
            closest_match_student_id=row.closest_match_student_id,
            closest_match_name=row.closest_match_name,
            closest_match_confidence=row.closest_match_confidence,
            class_name=row.class_name,
            session_date=row.session_opened_at.isoformat() if row.session_opened_at else None,
        )
        for row in rows
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

    # Upsert face embedding (replaces existing data for re-enrollment)
    existing_emb = await db.execute(
        select(FaceEmbedding).where(FaceEmbedding.student_id == student.id)
    )
    emb = existing_emb.scalar_one_or_none()
    if emb:
        emb.embedding = entry.embedding
    else:
        db.add(FaceEmbedding(student_id=student.id, embedding=entry.embedding))

    if body.mark_present and entry.session_id:
        att_result = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id == entry.session_id,
                AttendanceRecord.student_id == student.id,
            )
        )
        att = att_result.scalar_one_or_none()
        now = now_myt()
        if att:
            att.status = "present"
            att.override_by = actor.id
            att.override_at = now
        else:
            db.add(AttendanceRecord(
                session_id=entry.session_id,
                student_id=student.id,
                status="present",
                override_by=actor.id,
                override_at=now,
            ))

    await db.delete(entry)
    await write_log(
        db, actor.id, "FACE_PROMOTE",
        "face_review_entry", entry_id,
        new_val={"student_user_id": body.student_user_id, "mark_present": body.mark_present},
    )
