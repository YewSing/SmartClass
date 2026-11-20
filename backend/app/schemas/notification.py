from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    event_type: str
    priority: str
    title: str
    message: str
    link: str | None
    created_at: datetime
    read_at: datetime | None
    model_config = {"from_attributes": True}
