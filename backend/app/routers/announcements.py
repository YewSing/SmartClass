"""Lecturer announcements to a class (FR-217) — S17.

Only the lecturer assigned to the class may send or list them (NFR-04: 403 otherwise, also for
an unknown class, so class ids can't be probed). Sending notifies the class's active enrolled students as *important* and, with
`post_to_moodle`, queues a post to the course news forum in Moodle whose status the list shows.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import ensure_teaches_occurrence, require_role
from app.models.announcement import Announcement
from app.models.class_ import ClassOccurrence, Course
from app.models.user import User
from app.schemas.announcement import AnnouncementIn, AnnouncementOut, MoodlePostOut
from app.services.notifications import announcements

router = APIRouter(prefix="/lecturer/classes", tags=["announcements"])


async def _teaching(db: AsyncSession, actor: User, occurrence_id: int) -> ClassOccurrence:
    await ensure_teaches_occurrence(db, actor, occurrence_id)   # 403, also for an unknown class
    occurrence = await db.get(ClassOccurrence, occurrence_id)
    if occurrence is None:   # pragma: no cover - ensure_teaches_occurrence already refused it
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return occurrence


def _out(row: Announcement, course_code: str, author_name: str | None) -> AnnouncementOut:
    return AnnouncementOut(
        id=row.id, occurrence_id=row.occurrence_id, course_code=course_code, title=row.title,
        message=row.message, author_name=author_name, recipient_count=row.recipient_count,
        created_at=row.created_at,
        moodle=MoodlePostOut(
            status=row.moodle_status, attempts=row.moodle_attempts,
            last_attempt_at=row.moodle_last_attempt_at,
            next_try_at=row.moodle_next_at if row.moodle_status == "pending" else None,
            error=row.moodle_error, discussion_id=row.moodle_discussion_id,
            link=announcements.moodle_link(row.moodle_discussion_id), posted_at=row.moodle_posted_at,
        ),
    )


@router.post("/{occurrence_id}/announcements", response_model=AnnouncementOut,
             status_code=status.HTTP_201_CREATED)
async def send_announcement(
    occurrence_id: int,
    body: AnnouncementIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """Send an announcement to the class's students (important notification), optionally also
    posted to the Moodle news forum (status in the list; failures are retried)."""
    occurrence = await _teaching(db, actor, occurrence_id)
    row = await announcements.create(db, actor, occurrence, body.title, body.message,
                                     body.post_to_moodle)
    await db.refresh(row)
    course_code = await db.scalar(select(Course.code).where(Course.id == occurrence.course_id))
    return _out(row, course_code, actor.name)


@router.get("/{occurrence_id}/announcements", response_model=list[AnnouncementOut])
async def list_announcements(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer")),
):
    """The class's announcements, newest first, with each Moodle post status."""
    occurrence = await _teaching(db, actor, occurrence_id)
    course_code = await db.scalar(select(Course.code).where(Course.id == occurrence.course_id))
    rows = await announcements.list_for_class(db, occurrence_id)
    author_ids = {r.author_user_id for r in rows if r.author_user_id}
    names = dict((await db.execute(select(User.id, User.name).where(User.id.in_(author_ids)))).all()) \
        if author_ids else {}
    return [_out(r, course_code, names.get(r.author_user_id)) for r in rows]
