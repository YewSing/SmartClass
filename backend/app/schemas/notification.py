"""Module 2 notification feed and push-token shapes (FR-208, FR-209, FR-212) — S11, S13."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class NotificationOut(BaseModel):
    id: int
    event: str
    priority: str                 # urgent | important | general (FR-207)
    title: str
    message: str
    link: Optional[str]           # app-relative path, or null
    read: bool
    read_at: Optional[datetime]
    created_at: datetime


class FeedOut(BaseModel):
    items: list[NotificationOut]
    next_cursor: Optional[str]    # pass back as ?cursor= for the next (older) page; null = last page
    unread_count: int             # all of the caller's unread notifications, every priority


class PriorityOut(BaseModel):
    items: list[NotificationOut]  # unread urgent first, then important; newest first within each
    unread_count: int


class ReadOut(BaseModel):
    notification: NotificationOut
    unread_count: int


class PushTokenIn(BaseModel):
    """S13 (FR-212). `token` is an Expo push token, `ExponentPushToken[...]` or `ExpoPushToken[...]`."""
    token: str = Field(min_length=1, max_length=200)
    platform: Literal["android", "ios"]

    @field_validator("token")
    @classmethod
    def _expo_format(cls, v: str) -> str:
        from app.services.notifications.push import valid_token

        v = v.strip()
        if not valid_token(v):
            raise ValueError("not an Expo push token")
        return v


class PushTokenOut(BaseModel):
    token: str
    platform: str
    created_at: datetime
    last_seen_at: datetime


class ReadAllOut(BaseModel):
    marked: int                   # how many were unread and are now read
    unread_count: int             # always 0 right after
