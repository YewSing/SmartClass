from datetime import datetime, timezone

import pytest

from app.models.dashboard_cache import DashboardCache
from app.services.dashboard_moodle import fetch, refresh


class Client:
    base_url = "https://moodle.example"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def call(self, function, **params):
        if function == "core_group_get_course_user_groups":
            return {"groups": [{"id": 12}]}
        if function == "mod_forum_get_forums_by_courses":
            return [{"id": 10, "course": 7, "type": "news"}, {"id": 11, "course": 7, "type": "general"}]
        if function == "mod_forum_get_forum_discussions":
            assert params["forumid"] == 10
            return {"discussions": [{"discussion": 22, "name": "Welcome", "timemodified": 123}]}
        if function == "core_calendar_get_calendar_events":
            assert params["events[groupids][0]"] == 12
            return {"events": [{"id": 3, "courseid": 7, "groupid": 12, "name": "Assignment due", "timestart": 456},
                               {"id": 5, "courseid": 7, "groupid": 99, "name": "Other group", "timestart": 456},
                               {"id": 4, "courseid": 8, "name": "Other course", "timestart": 456}]}
        raise AssertionError(function)


async def test_fetch_only_news_and_requested_course_events():
    data = await fetch(Client(), [7])
    assert [item["title"] for item in data["announcements"]] == ["Welcome"]
    assert [item["title"] for item in data["deadlines"]] == ["Assignment due"]
    assert data["announcements"][0]["link"] == "https://moodle.example/mod/forum/discuss.php?d=22"


async def test_partial_calendar_warning_is_not_a_successful_snapshot():
    from app.services.kb.moodle_client import MoodleError

    class PartialClient(Client):
        async def call(self, function, **params):
            if function == "core_calendar_get_calendar_events":
                return {"events": [], "warnings": [{"warningcode": "nopermissions"}]}
            return await super().call(function, **params)

    with pytest.raises(MoodleError):
        await fetch(PartialClient(), [7])


@pytest.mark.db
async def test_refresh_failure_preserves_snapshot(users, db_session, monkeypatch):
    old = {"announcements": [], "deadlines": [{"course_id": 7, "title": "Saved"}]}
    db_session.add(DashboardCache(user_id=users["student"].id, data=old, refreshed_at=datetime.now(timezone.utc)))
    await db_session.commit()

    async def fail(*args):
        raise RuntimeError("unavailable")

    monkeypatch.setattr("app.services.dashboard_moodle.fetch", fail)
    await refresh(db_session, users["student"].id, "transient-token", [7])
    assert (await db_session.get(DashboardCache, users["student"].id)).data == old


@pytest.mark.db
async def test_snapshot_filters_removed_enrolments(users, classroom, student_client, db_session):
    from app.models.class_ import Course
    course = await db_session.get(Course, classroom["course_id"])
    course.moodle_course_id = 7
    db_session.add(DashboardCache(user_id=users["student"].id,
        data={"announcements": [{"course_id": 7, "title": "Own course"}, {"course_id": 8, "title": "Removed course"}], "deadlines": []},
        refreshed_at=datetime.now(timezone.utc)))
    await db_session.commit()
    data = (await student_client.get("/student/me/dashboard")).json()["moodle"]
    assert data["available"] is True
    assert [a["title"] for a in data["announcements"]] == ["Own course"]


@pytest.mark.db
async def test_refresh_persists_content_without_credentials(users, db_session, monkeypatch):
    tokens = []

    def client(**kwargs):
        tokens.append(kwargs["token"])
        return Client()

    monkeypatch.setattr("app.services.dashboard_moodle.MoodleClient", client)
    await refresh(db_session, users["student"].id, "transient-only", [7])
    await db_session.commit()
    cached = await db_session.get(DashboardCache, users["student"].id)
    assert cached.data["announcements"][0]["title"] == "Welcome"
    assert tokens == ["transient-only"]
    assert "transient-only" not in str(cached.data)


@pytest.mark.db
@pytest.mark.moodle
async def test_live_moodle_login_populates_dashboard_snapshot(client):
    response = await client.post("/auth/moodle-login", json={"username": "student1", "password": "Student123!"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    dashboard = await client.get("/student/me/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert dashboard.status_code == 200
    assert dashboard.json()["moodle"]["available"] is True
    assert dashboard.json()["moodle"]["refreshed_at"] is not None
