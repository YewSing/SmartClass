from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditActorOut(BaseModel):
    id: int
    name: str
    email: str
    role: str

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: int
    actor: AuditActorOut
    action: str
    target_type: str
    target_id: str
    old_val: Optional[str] = None
    new_val: Optional[str] = None
    ts: datetime

    model_config = {"from_attributes": True}
