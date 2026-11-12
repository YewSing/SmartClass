"""The weekly class schedule (FR-301, FR-316). Changing or cancelling one class was removed in T38b."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import ensure_teaches_occurrence, require_role
from app.models.class_ import ClassOccurrence
from app.models.user import Lecturer, User
from app.routers.classes import _occurrence_to_out
from app.schemas.class_ import OccurrenceOut, WeeklyScheduleRequest
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
