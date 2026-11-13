"""
Legacy face review queue: unrecognised faces the old face_worker reported. Since T46b nothing adds
rows (the camera path is POST /device/faces, and unmatched crops go to the student flag queue, T43);
no app calls the admin endpoints since frontend/admin was retired (T96); see PROGRESS.md Next.
"""
from typing import Optional

from app.core.timezone import now_myt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.database import get_db
from app.core.deps import require_role
from app.models.face_review import FaceReviewEntry
from app.models.face import FaceEmbedding
from app.models.user import User, Student
from app.models.attendance import AttendanceRecord
from app.models.session import AttendanceSession
from app.services import attendance_moodle_sync
from app.services.audit_service import write_log
from app.services.consent_service import require_active_consent

router = APIRouter(tags=["face-review"])

_admin_only = require_role("admin")

# Cosine similarity threshold for merging into an existing review entry
_GROUP_THRESHOLD = 0.35


# ── Schemas ───────────────────────────────────────────────────────────────────

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
    await require_active_consent(db, student.id)  # NFR-03: no embedding without consent

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
        session = await db.get(AttendanceSession, entry.session_id)
        if session:
            attendance_moodle_sync.queue_resync(session, now)  # FR-312
            if session.moodle_sync_status == "pending":
                attendance_moodle_sync.sync_soon(db, session.id)

    await db.delete(entry)
    await write_log(
        db, actor.id, "FACE_PROMOTE",
        "face_review_entry", entry_id,
        new_val={"student_user_id": body.student_user_id, "mark_present": body.mark_present},
    )
