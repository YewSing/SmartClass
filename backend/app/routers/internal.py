"""
Endpoints consumed only by the camera device (face recognition worker).
Each device authenticates with its own X-Device-Key (FR-408, NFR-07).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.session import AttendanceSession
from app.models.attendance import AttendanceRecord, ATTENDED_STATUSES
from app.models.camera import Camera
from app.models.class_ import Enrollment
from app.models.user import Student
from app.schemas.session import FaceMatchRequest, FaceMatchResponse
from app.services import session_schedule
from app.services.attendance_service import mark_present, broadcast_attendance_update
from app.services.device_service import require_device

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/active-session")
async def get_active_session(
    db: AsyncSession = Depends(get_db),
    camera: Camera = Depends(require_device),
):
    """Returns the open session assigned to the calling device's camera (its room)."""
    q = (select(AttendanceSession)
         .where(AttendanceSession.status == "open", AttendanceSession.camera_id == camera.id)
         .limit(1))
    result = await db.execute(q)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active session")

    return {
        "session_id": session.id,
        "occurrence_id": session.occurrence_id,
        "class_id": session.occurrence_id,
        "camera_id": session.camera_id,
        "opened_at": session.opened_at,
    }


@router.post("/face-match", response_model=FaceMatchResponse)
async def face_match(
    body: FaceMatchRequest,
    db: AsyncSession = Depends(get_db),
    camera: Camera = Depends(require_device),
):
    """
    Query pgvector for the nearest face embedding using cosine similarity (FR-002, FR-003).
    If dry_run=True, returns the result without writing an attendance record (used by worker
    vote counter for FR-004 multi-frame aggregation).
    A device may only record into a session of its own room; a session whose room has no
    camera accepts any registered device (backup webcam, FR-409).
    """
    if len(body.embedding) != 512:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Embedding must be 512-dimensional")

    # Verify session exists and is open
    session_result = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.id == body.session_id,
            AttendanceSession.status == "open",
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or closed")
    if session.camera_id is not None and session.camera_id != camera.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session belongs to another room's device")

    # pgvector cosine similarity: (1 - cosine_distance) = cosine_similarity
    # <=> is the cosine distance operator; lower = more similar
    similarity_result = await db.execute(
        text(
            "SELECT fe.student_id, (1 - (fe.embedding <=> CAST(:vec AS vector))) AS similarity "
            "FROM face_embeddings fe "
            "ORDER BY fe.embedding <=> CAST(:vec AS vector) "
            "LIMIT 1"
        ),
        {"vec": str(body.embedding)},
    )
    row = similarity_result.fetchone()

    if not row:
        return FaceMatchResponse(matched=False)

    candidate_student_id, similarity = row.student_id, float(row.similarity)

    if similarity < settings.FACE_MATCH_THRESHOLD:
        return FaceMatchResponse(matched=False, similarity=similarity)

    # Verify the matched student is enrolled in this session's occurrence
    enrolled = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == candidate_student_id,
            Enrollment.occurrence_id == session.occurrence_id,
        )
    )
    if not enrolled.scalar_one_or_none():
        return FaceMatchResponse(matched=False, similarity=similarity, reason="not_enrolled")

    # Get student name for response and broadcast
    stu_result = await db.execute(
        select(Student)
        .options(selectinload(Student.user))
        .where(Student.id == candidate_student_id)
    )
    student = stu_result.scalar_one()

    if body.dry_run:
        # Check whether already present to inform the worker's vote logic
        existing = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id == body.session_id,
                AttendanceRecord.student_id == candidate_student_id,
            )
        )
        already = existing.scalar_one_or_none()
        return FaceMatchResponse(
            matched=True,
            student_id=candidate_student_id,
            student_name=student.user.name,
            similarity=similarity,
            already_present=bool(already and already.status in ATTENDED_STATUSES),
        )

    # Commit the match — write attendance record
    record, was_new = await mark_present(
        body.session_id, candidate_student_id, db, now=session_schedule.clock()
    )

    if was_new:
        await broadcast_attendance_update(
            body.session_id, record, student.user.name, student.matric_no, db
        )

    return FaceMatchResponse(
        matched=True,
        student_id=candidate_student_id,
        student_name=student.user.name,
        similarity=similarity,
        already_present=not was_new,
    )
