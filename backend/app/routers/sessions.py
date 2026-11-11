from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import ensure_teaches_occurrence, require_role
from app.models.user import User, Lecturer
from app.models.class_ import ClassOccurrence
from app.models.session import AttendanceSession
from app.schemas.session import (
    ConfirmRequest,
    ExtendRequest,
    OpenSessionRequest,
    SessionOut,
)
from app.services import session_schedule, session_service
from app.services.audit_service import write_log
from app.websocket.manager import manager

router = APIRouter(prefix="/lecturer/sessions", tags=["sessions"])

_lecturer_or_admin = require_role("lecturer", "admin")  # listing only; running a session is lecturer-only
_lecturer = require_role("lecturer")


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
        camera_id=session.camera_id,
        class_code=occ.course.code if occ else "",
        class_name=_occ_display_name(occ) if occ else "",
        lecturer_id=session.lecturer_id,
        opened_at=session.opened_at,
        closed_at=session.closed_at,
        status=session.status,
        class_date=session.class_date,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        source=session.source,
        **counts,
    )


_session_opts = [
    selectinload(AttendanceSession.occurrence).selectinload(ClassOccurrence.course),
]


async def _get_taught_session(db: AsyncSession, actor: User, session_id: int) -> AttendanceSession:
    """The session, or 404 if unknown and 403 if the actor doesn't teach its class."""
    session = (await db.execute(
        select(AttendanceSession).options(*_session_opts).where(AttendanceSession.id == session_id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await ensure_teaches_occurrence(db, actor, session.occurrence_id)
    return session


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer_or_admin),
):
    q = (
        select(AttendanceSession)
        .options(*_session_opts)
        .where(AttendanceSession.opened_at.is_not(None))  # scheduled/cancelled-ahead rows never opened
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
    actor: User = Depends(_lecturer),
):
    """Start the class now (FR-316)."""
    occ_result = await db.execute(
        select(ClassOccurrence)
        .options(selectinload(ClassOccurrence.course))
        .where(ClassOccurrence.id == body.occurrence_id)
    )
    occ = occ_result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Occurrence not found")

    lec = await ensure_teaches_occurrence(db, actor, occ.id)
    session = await session_schedule.start_now(
        db, occ, lec, session_schedule.clock(), body.duration_minutes
    )

    result = await db.execute(
        select(AttendanceSession)
        .options(*_session_opts)
        .where(AttendanceSession.id == session.id)
    )
    return await _session_to_out(result.scalar_one(), db)


@router.put("/{session_id}/close", response_model=SessionOut)
async def close_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """End the class early (FR-315)."""
    session = await _get_taught_session(db, actor, session_id)
    if session.status == "closed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session already closed")
    if session.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not open")

    now = session_schedule.clock()
    old_ends_at = session.ends_at
    session = await session_service.close_session(session_id, db, now)
    session.ends_at = now
    await write_log(db, actor.id, "SESSION_ENDED", "attendance_session", session.id,
                    {"status": "open", "ends_at": old_ends_at.isoformat() if old_ends_at else None},
                    {"status": "closed", "ends_at": now.isoformat()})
    await db.flush()

    counts = await session_service.get_session_counts(session_id, db)

    await manager.broadcast(session_id, {
        "event": "session_closed",
        "counts": counts,
        "final": True,
    })

    result = await db.execute(
        select(AttendanceSession)
        .options(*_session_opts)
        .where(AttendanceSession.id == session_id)
    )
    return await _session_to_out(result.scalar_one(), db)


@router.post("/{session_id}/extend", response_model=SessionOut)
async def extend_session(
    session_id: int,
    body: ExtendRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Push the class's end out by a few minutes (FR-315)."""
    session = await _get_taught_session(db, actor, session_id)
    await session_schedule.extend(db, session, body.minutes, session_schedule.clock(), actor.id)
    return await _session_to_out(session, db)


@router.post("/{session_id}/confirm", response_model=SessionOut)
async def confirm_session(
    session_id: int,
    body: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Confirm a class the job could not tell was held (FR-317)."""
    session = await _get_taught_session(db, actor, session_id)
    await session_schedule.confirm(db, session, body.held, session_schedule.clock(), actor.id)
    return await _session_to_out(session, db)
