"""Read dashboard content with the user's own transient Moodle token."""
import logging
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.models.dashboard_cache import DashboardCache
from app.services.kb.moodle_client import MoodleClient, MoodleError

log = logging.getLogger(__name__)


async def fetch(client, course_ids):
    ids = sorted(set(course_ids))
    announcements, deadlines = [], []
    for course_id in ids:
        forums = await client.call("mod_forum_get_forums_by_courses", **{"courseids[0]": course_id})
        for forum in forums:
            if forum.get("type") != "news" or forum.get("course") != course_id:
                continue
            body = await client.call("mod_forum_get_forum_discussions", forumid=forum["id"], page=0, perpage=20)
            if body.get("warnings"):
                raise MoodleError("Incomplete forum snapshot")
            for item in body.get("discussions", []):
                announcements.append({"course_id": course_id, "id": item["discussion"],
                    "title": item.get("name") or item.get("subject") or "Announcement",
                    "date": item.get("timemodified"),
                    "link": f"{client.base_url}/mod/forum/discuss.php?d={item['discussion']}"})
        groups = await client.call("core_group_get_course_user_groups", courseid=course_id)
        if groups.get("warnings"):
            raise MoodleError("Incomplete course group snapshot")
        group_params = {f"events[groupids][{i}]": group["id"] for i, group in enumerate(groups.get("groups", []))}
        allowed_groups = {group["id"] for group in groups.get("groups", [])}
        body = await client.call("core_calendar_get_calendar_events", **group_params, **{
            "events[courseids][0]": course_id, "options[userevents]": 0, "options[siteevents]": 0,
            "options[timestart]": int(datetime.now(timezone.utc).timestamp())})
        if body.get("warnings"):
            raise MoodleError("Incomplete calendar snapshot")
        for item in body.get("events", []):
            if item.get("courseid") != course_id or not item.get("visible", 1):
                continue
            if item.get("groupid") and item["groupid"] not in allowed_groups:
                continue
            deadlines.append({"course_id": course_id, "id": item["id"], "title": item["name"],
                "date": item["timestart"],
                "link": f"{client.base_url}/calendar/view.php?view=day&time={item['timestart']}"})
    return {"announcements": sorted(announcements, key=lambda x: x["date"] or 0, reverse=True),
            "deadlines": sorted(deadlines, key=lambda x: x["date"])}


async def refresh(db, user_id, token, course_ids):
    """Best effort: Moodle failure preserves the prior snapshot and never breaks login."""
    if not token:
        return
    try:
        async with MoodleClient(token=token, timeout=5) as client:
            data = await fetch(client, course_ids)
        # A savepoint isolates persistence failures from the owning login transaction.
        async with db.begin_nested():
            stmt = insert(DashboardCache).values(user_id=user_id, data=data, refreshed_at=datetime.now(timezone.utc))
            await db.execute(stmt.on_conflict_do_update(index_elements=[DashboardCache.user_id],
                set_={"data": stmt.excluded.data, "refreshed_at": stmt.excluded.refreshed_at}))
    except Exception as exc:
        log.warning("Moodle dashboard refresh unavailable: %s", type(exc).__name__)
