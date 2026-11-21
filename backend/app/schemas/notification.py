"""Module 2 notification feed shapes (FR-208, FR-209) — S11."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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


class ReadAllOut(BaseModel):
    marked: int                   # how many were unread and are now read
    unread_count: int             # always 0 right after
