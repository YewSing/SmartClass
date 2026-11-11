from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import ensure_teaches_occurrence, require_role
from app.models.attendance import ATTENDANCE_STATUSES, AttendanceRecord
from app.models.user import User, Lecturer, Student
from app.models.class_ import ClassOccurrence
from app.models.session import AttendanceSession
from app.schemas.session import (
    ConfirmRequest,
    ExtendRequest,
    MoodleConflictOut,
    OpenSessionRequest,
    ResolveConflictRequest,
    SessionOut,
)
from app.services import attendance_moodle_sync, session_schedule, session_service
from app.services.kb.moodle_client import MoodleError
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
        moodle_sync_status=session.moodle_sync_status,
        moodle_synced_at=session.moodle_synced_at,
        moodle_sync_next_at=session.moodle_sync_next_at,
        moodle_sync_error=session.moodle_sync_error,
        moodle_conflicts=await _moodle_conflicts(session, db),
        **counts,
    )


async def _moodle_conflicts(session: AttendanceSession, db: AsyncSession) -> list[MoodleConflictOut]:
    if session.moodle_sync_status in (None, "synced"):   # a synced session has no conflicts left
        return []
    rows = (await db.execute(
        select(AttendanceRecord, Student.matric_no, User.name)
        .join(Student, Student.id == AttendanceRecord.student_id)
        .join(User, User.id == Student.user_id)
        .where(AttendanceRecord.session_id == session.id, AttendanceRecord.moodle_status_found.is_not(None))
        .order_by(Student.matric_no)
    )).all()
    return [MoodleConflictOut(record_id=rec.id, student_id=rec.student_id, matric_no=matric_no, name=name,
                              smartclass_status=rec.status, moodle_status=rec.moodle_status_found,
                              keep_smartclass=rec.moodle_overwrite_ok)
            for rec, matric_no, name in rows]


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


@router.post("/{session_id}/moodle-sync", response_model=SessionOut)
async def retry_moodle_sync(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Send the session to Moodle now instead of waiting for the next try (FR-312, NFR-20)."""
    session = await _get_taught_session(db, actor, session_id)
    if session.moodle_sync_status is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Only a closed class session is sent to Moodle")
    try:
        await attendance_moodle_sync.sync_now(db, session_id, attendance_moodle_sync.clock())
    except MoodleError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Moodle is not configured") from None
    session = (await db.execute(
        select(AttendanceSession).options(*_session_opts).where(AttendanceSession.id == session_id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    return await _session_to_out(session, db)


@router.post("/{session_id}/moodle-conflicts/{record_id}", response_model=SessionOut)
async def resolve_moodle_conflict(
    session_id: int,
    record_id: int,
    body: ResolveConflictRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Keep SmartClass's value or take Moodle's for a student changed in Moodle (FR-320)."""
    session = await _get_taught_session(db, actor, session_id)
    record = await db.get(AttendanceRecord, record_id)
    if not record or record.session_id != session.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")
    if record.moodle_status_found is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This student's status is not in conflict with Moodle")
    if body.keep == "moodle" and record.moodle_status_found not in ATTENDANCE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Moodle's value is not one of SmartClass's statuses; keep SmartClass's")
    await attendance_moodle_sync.resolve_conflict(db, session, record, body.keep, actor.id,
                                                  attendance_moodle_sync.clock())
    return await _session_to_out(session, db)
