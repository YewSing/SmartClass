import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def write_log(
    db: AsyncSession,
    actor_id: int,
    action: str,
    target_type: str,
    target_id: Any,
    old_val: Any = None,
    new_val: Any = None,
) -> None:
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        old_val=json.dumps(old_val) if old_val is not None else None,
        new_val=json.dumps(new_val) if new_val is not None else None,
    )
    db.add(log)
