from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_role
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/admin/audit-logs", tags=["admin-audit"])

_admin_only = require_role("admin")


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_only),
):
    q = (
        select(AuditLog)
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.ts.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await db.execute(q)
    return result.scalars().all()
