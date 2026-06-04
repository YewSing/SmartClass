from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, Lecturer
from app.models.class_ import ClassOccurrence
from app.models.camera import Camera
from app.models.session import AttendanceSession
from app.schemas.session import SessionOut, OpenSessionRequest
from app.services import session_service
from app.websocket.manager import manager

router = APIRouter(prefix="/lecturer/sessions", tags=["sessions"])

_lecturer_or_admin = require_role("lecturer", "admin")


def _occ_display_name(occ: ClassOccurrence) -> str:
    """Build a display name for an occurrence: 'CourseName — Label' or just 'CourseName'."""
    base = occ.course.name
    if occ.label:
        return f"{base} — {occ.label}"
    return base


async def _session_to_out(session: AttendanceSession, db: AsyncSession) -> SessionOut:
    counts = await session_service.get_session_counts(session.id, db)
    occ = session.occurrence
    return SessionOut(
        id=session.id,
        occurrence_id=session.occurrence_id,
        class_id=session.occurrence_id,  # compat alias
        class_code=occ.course.code if occ else "",
        class_name=_occ_display_name(occ) if occ else "",
        lecturer_id=session.lecturer_id,
        opened_at=session.opened_at,
        closed_at=session.closed_at,
        status=session.status,
        **counts,
    )


_session_opts = [
    selectinload(AttendanceSession.occurrence).selectinload(ClassOccurrence.course),
]


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    q = (
        select(AttendanceSession)
        .options(*_session_opts)
        .order_by(AttendanceSession.opened_at.desc())
    )
    if actor.role == "lecturer":
        lec_result = await db.execute(select(Lecturer).where(Lecturer.user_id == actor.id))
        lec = lec_result.scalar_one_or_none()
        if not lec:
            return []
        q = q.where(AttendanceSession.lecturer_id == lec.id)

    result = await db.execute(q)
    sessions = result.scalars().all()
    return [await _session_to_out(s, db) for s in sessions]


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def open_session(
    body: OpenSessionRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    occ_result = await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .where(ClassOccurrence.id == body.occurrence_id)
    )
    occ = occ_result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Occurrence not found")

    lec_result = await db.execute(select(Lecturer).where(Lecturer.user_id == actor.id))
    lec = lec_result.scalar_one_or_none()
    if not lec and actor.role == "lecturer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lecturer profile not found")

    existing = await db.execute(
        select(AttendanceSession).where(
            and_(
                AttendanceSession.occurrence_id == body.occurrence_id,
                AttendanceSession.status == "open",
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session is already open for this occurrence",
        )

    # Auto-assign camera registered to this occurrence's room
    camera_id = None
    if occ.room:
        cam_result = await db.execute(select(Camera).where(Camera.room == occ.room))
        cam = cam_result.scalar_one_or_none()
        if cam:
            camera_id = cam.id

    session = AttendanceSession(
        occurrence_id=body.occurrence_id,
        lecturer_id=lec.id if lec else 0,
        camera_id=camera_id,
        status="open",
    )
    db.add(session)
    await db.flush()

    result = await db.execute(
        select(AttendanceSession)
        .options(*_session_opts)
        .where(AttendanceSession.id == session.id)
    )
    session = result.scalar_one()
    return await _session_to_out(session, db)


@router.put("/{session_id}/close", response_model=SessionOut)
async def close_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    result = await db.execute(
        select(AttendanceSession)
        .options(*_session_opts)
        .where(AttendanceSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.status == "closed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session already closed")

    session = await session_service.close_session(session_id, db)

    result = await db.execute(
        select(AttendanceSession)
        .options(*_session_opts)
        .where(AttendanceSession.id == session_id)
    )
    session = result.scalar_one()
    counts = await session_service.get_session_counts(session_id, db)

    await manager.broadcast(session_id, {
        "event": "session_closed",
        "counts": counts,
        "final": True,
    })

    occ = session.occurrence
    return SessionOut(
        id=session.id,
        occurrence_id=session.occurrence_id,
        class_id=session.occurrence_id,
        class_code=occ.course.code if occ else "",
        class_name=_occ_display_name(occ) if occ else "",
        lecturer_id=session.lecturer_id,
        opened_at=session.opened_at,
        closed_at=session.closed_at,
        status=session.status,
        **counts,
    )
