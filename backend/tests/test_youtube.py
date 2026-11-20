"""T92: YouTube suggestions (FR-812, Could Have) — the YouTube Data API is mocked with respx."""
import httpx
import pytest
import respx

from app.core.config import settings
from app.models.class_ import Course
from app.services.kb.youtube import SEARCH_URL, keywords_for, search_videos

SEARCH_RESPONSE = {
    "items": [
        {
            "id": {"kind": "youtube#video", "videoId": "abc123"},
            "snippet": {
                "title": "Boundary Value Analysis Explained",
                "channelTitle": "Software Testing Academy",
                "thumbnails": {"medium": {"url": "https://i.ytimg.com/abc123/mq.jpg"}},
            },
        },
    ],
}


@respx.mock
async def test_with_key_returns_parsed_videos(monkeypatch):
    monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "test-key")
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=SEARCH_RESPONSE))
    result = await search_videos("boundary value analysis")
    assert result["enabled"] is True
    [v] = result["videos"]
    assert v["video_id"] == "abc123"
    assert v["title"] == "Boundary Value Analysis Explained"
    assert v["url"] == "https://www.youtube.com/watch?v=abc123"
    assert v["thumbnail_url"] == "https://i.ytimg.com/abc123/mq.jpg"
    assert result["keywords"][0] == "boundary value analysis"


@respx.mock
async def test_without_key_is_off_and_makes_no_call(monkeypatch):
    monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "")
    route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={}))
    result = await search_videos("boundary value analysis")
    assert result["enabled"] is False
    assert result["videos"] == []
    assert route.called is False


@respx.mock
async def test_provider_error_degrades_to_empty(monkeypatch):
    monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "test-key")
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(403, json={"error": "forbidden"}))
    result = await search_videos("boundary value analysis")
    assert result["enabled"] is True
    assert result["videos"] == []


@respx.mock
async def test_bad_json_degrades_to_empty(monkeypatch):
    monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "test-key")
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, content=b"not json"))
    result = await search_videos("boundary value analysis")
    assert result["videos"] == []


def test_keywords_for_topic():
    assert keywords_for("  boundary value analysis ") == [
        "boundary value analysis",
        "boundary value analysis tutorial",
        "boundary value analysis explained",
    ]
    assert keywords_for("") == []
    assert keywords_for(None) == []


# ── the endpoint ──────────────────────────────────────────────────────────────

@pytest.mark.db
@respx.mock
async def test_youtube_endpoint_off_without_key_and_enforces_enrollment(
    student_client, classroom, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "")
    # enrolled course, no key → enabled=False, no YouTube call
    resp = await student_client.post("/student/assistant/youtube",
                                     json={"course_id": classroom["course_id"], "topic": "bva"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is False and body["videos"] == []
    assert body["keywords"] == ["bva", "bva tutorial", "bva explained"]

    # a course the student is not enrolled in → 403
    other = Course(code="CS999", name="Not enrolled")
    db_session.add(other)
    await db_session.flush()
    resp = await student_client.post("/student/assistant/youtube",
                                     json={"course_id": other.id, "topic": "bva"})
    assert resp.status_code == 403


@pytest.mark.db
@respx.mock
async def test_youtube_endpoint_is_student_only(lecturer_client, admin_client, classroom, monkeypatch):
    monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "")
    body = {"course_id": classroom["course_id"], "topic": "bva"}
    assert (await lecturer_client.post("/student/assistant/youtube", json=body)).status_code == 403
    assert (await admin_client.post("/student/assistant/youtube", json=body)).status_code == 403
