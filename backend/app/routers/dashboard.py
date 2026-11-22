"""Student and lecturer dashboards (FR-201, FR-202) — S18.

Each endpoint reads only the signed-in user's own data (NFR-04); see `services/dashboard/reads.py`.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User
from app.schemas.dashboard import LecturerDashboardOut, StudentDashboardOut
from app.services.dashboard import reads

router = APIRouter(tags=["dashboard"])


@router.get("/student/me/dashboard", response_model=StudentDashboardOut)
async def student_dashboard(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("student")),
):
    """Today's classes with my attendance status, my rate per course, Moodle deadlines and
    announcements (with refreshed_at) and my unread urgent/important notifications."""
    return await reads.student_dashboard(db, actor)


@router.get("/lecturer/dashboard", response_model=LecturerDashboardOut)
async def lecturer_dashboard(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Today's classes, the current (open) or latest closed session's attendance counts and my
    unread urgent/important notifications."""
    return await reads.lecturer_dashboard(db, actor)
