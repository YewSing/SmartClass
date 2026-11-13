"""YouTube suggestions for a study topic (FR-812, Could Have).

External learning resources, behind `YOUTUBE_API_KEY`. With no key the feature is simply off
(no call is made); with a key the Data API `search.list` is called for the topic and the videos
are returned alongside a few search keywords. A provider error degrades to empty videos rather
than failing the request, since this is a non-critical extra.
"""
import httpx

from app.core.config import settings

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def keywords_for(topic: str) -> list[str]:
    """A few search terms the student can copy (the topic, plus common suffixes)."""
    t = (topic or "").strip()
    if not t:
        return []
    return [t, f"{t} tutorial", f"{t} explained"]


async def search_videos(topic: str, max_results: int | None = None) -> dict:
    """Return {videos, keywords, enabled}. `enabled` is False when no key is configured."""
    keywords = keywords_for(topic)
    if not settings.YOUTUBE_API_KEY:
        return {"videos": [], "keywords": keywords, "enabled": False}

    limit = max_results or settings.YOUTUBE_MAX_RESULTS
    videos: list[dict] = []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(SEARCH_URL, params={
                "part": "snippet", "type": "video", "q": topic.strip(),
                "key": settings.YOUTUBE_API_KEY, "maxResults": limit,
            })
            resp.raise_for_status()
            items = (resp.json().get("items") or []) if resp.content else []
    except (httpx.HTTPError, ValueError):
        return {"videos": [], "keywords": keywords, "enabled": True}

    for item in items:
        video_id = (item.get("id") or {}).get("videoId")
        snippet = item.get("snippet") or {}
        if not video_id or not snippet.get("title"):
            continue
        thumbs = snippet.get("thumbnails") or {}
        thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
        videos.append({
            "video_id": video_id,
            "title": snippet["title"],
            "channel": snippet.get("channelTitle") or "",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": thumb,
        })
    return {"videos": videos, "keywords": keywords, "enabled": True}
