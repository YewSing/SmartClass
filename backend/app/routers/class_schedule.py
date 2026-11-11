"""The weekly class schedule and one-class changes (FR-301, FR-315–FR-317)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import ensure_teaches_occurrence, require_role
from app.models.class_ import ClassOccurrence
from app.models.session import AttendanceSession
from app.models.user import Lecturer, User
from app.routers.classes import _occurrence_to_out
from app.routers.sessions import _session_opts, _session_to_out
from app.schemas.class_ import ClassTimeRequest, OccurrenceOut, WeeklyScheduleRequest
from app.schemas.session import SessionOut
from app.services import session_schedule

router = APIRouter(prefix="/lecturer/classes", tags=["classes"])

_lecturer = require_role("lecturer")


async def _get_taught_occurrence(db: AsyncSession, actor: User, occurrence_id: int) -> ClassOccurrence:
    occ = (await db.execute(
        select(ClassOccurrence)
        .options(
            selectinload(ClassOccurrence.course),
            selectinload(ClassOccurrence.lecturer).selectinload(Lecturer.user),
            selectinload(ClassOccurrence.enrollments),
        )
        .where(ClassOccurrence.id == occurrence_id)
    )).scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Occurrence not found")
    await ensure_teaches_occurrence(db, actor, occ.id)
    return occ


async def _session_out(db: AsyncSession, session_id: int) -> SessionOut:
    session = (await db.execute(
        select(AttendanceSession).options(*_session_opts).where(AttendanceSession.id == session_id)
    )).scalar_one()
    return await _session_to_out(session, db)


@router.put("/{occurrence_id}/schedule", response_model=OccurrenceOut)
async def set_weekly_schedule(
    occurrence_id: int,
    body: WeeklyScheduleRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Set the class's weekly slot, or clear it (no schedule)."""
    occ = await _get_taught_occurrence(db, actor, occurrence_id)
    occ = await session_schedule.set_weekly_schedule(db, occ, body, actor)
    return _occurrence_to_out(occ, len(occ.enrollments))


@router.put("/{occurrence_id}/dates/{class_date}", response_model=SessionOut)
async def change_class_time(
    occurrence_id: int,
    class_date: date,
    body: ClassTimeRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Move one class date's time (before or during the class)."""
    occ = await _get_taught_occurrence(db, actor, occurrence_id)
    session = await session_schedule.change_time(
        db, occ, class_date,
        session_schedule.parse_hhmm(body.start_time), session_schedule.parse_hhmm(body.end_time),
        session_schedule.clock(), actor.id,
    )
    return await _session_out(db, session.id)


@router.post("/{occurrence_id}/dates/{class_date}/cancel", response_model=SessionOut)
async def cancel_class(
    occurrence_id: int,
    class_date: date,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """Cancel one class date, ahead of or during it."""
    occ = await _get_taught_occurrence(db, actor, occurrence_id)
    session = await session_schedule.cancel_class(
        db, occ, class_date, session_schedule.clock(), actor.id
    )
    return await _session_out(db, session.id)
