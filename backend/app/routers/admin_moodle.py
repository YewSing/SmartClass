"""Admin "Sync now" for courses and enrolments from Moodle (FR-104)."""
import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User
from app.services import moodle_sync
from app.services.audit_service import write_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/moodle", tags=["admin-moodle"])

_admin_only = require_role("admin")


@router.post("/sync")
async def sync_now(db: AsyncSession = Depends(get_db), admin: User = Depends(_admin_only)):
    try:
        report = await moodle_sync.sync_all(db)
    except Exception as exc:
        await db.rollback()
        # Only the class name: Moodle errors can carry URLs with the service token (NFR-08)
        logger.warning("Moodle sync failed: %s", exc.__class__.__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Moodle sync failed; nothing was changed.") from None
    result = asdict(report)
    await write_log(db, admin.id, "MOODLE_SYNC", "moodle", "all", new_val=result)
    return result


@router.get("/sync")
async def last_sync(_: User = Depends(_admin_only)):
    """The last full sync's time and result (scheduled or manual), or null before the first."""
    return moodle_sync.last_sync
