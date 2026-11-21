"""S16: Moodle announcements and deadlines on login (FR-203, NFR-05).

Moodle is mocked with respx; the `moodle` test at the bottom uses the local SPeCTRUM simulation.
"""
import json
import logging
from datetime import datetime, timezone
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from sqlalchemy import func, select, text

from app.core.config import settings
from app.models.moodle_snapshot import MoodleSnapshot
from app.models.user import User
from app.services import moodle_sync
from app.services.dashboard import moodle_snapshot

PASSWORD = "S3cret-Moodle-Pass!"
TOKEN = "user-token-abc123"
SERVICE_TOKEN = "service-token-must-not-be-used"
NOW = datetime(2026, 11, 22, 2, 0, tzinfo=timezone.utc)      # 10:00 MYT
NOW_TS = int(NOW.timestamp())
DAY = 86400


def _url(path: str) -> str:
    return f"{settings.MOODLE_URL.rstrip('/')}{path}"


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    monkeypatch.setattr(moodle_snapshot, "clock", lambda: NOW)
    monkeypatch.setattr(settings, "MOODLE_TOKEN", SERVICE_TOKEN)   # must never be used here
    monkeypatch.setattr(settings, "MOODLE_PUBLIC_URL", "")


def _discussion(did, name, created):
    return {"discussion": did, "id": did + 1000, "name": name, "subject": name, "created": created,
            "timemodified": created + 5}


DEFAULT_FORUMS = [
    {"id": 11, "course": 7, "type": "news", "name": "Announcements"},
    {"id": 12, "course": 7, "type": "general", "name": "Q&A"},
    {"id": 21, "course": 8, "type": "news", "name": "Announcements"},
]
DEFAULT_DISCUSSIONS = {
    11: [_discussion(501, "Test 1 moved to <b>Week 9</b> &amp; room DK1", NOW_TS - DAY)],
    12: [_discussion(601, "General chat", NOW_TS - 10)],
    21: [_discussion(701, "Lab 3 released", NOW_TS - 2 * DAY)],
}
DEFAULT_EVENTS = [
    {"id": 901, "name": "Assignment 2 is due", "courseid": 8, "timestart": NOW_TS + 3 * DAY,
     "modulename": "assign", "eventtype": "due", "visible": 1},
    {"id": 902, "name": "Project proposal is due", "courseid": 7, "timestart": NOW_TS + DAY,
     "modulename": "assign", "eventtype": "due", "visible": 1},
    {"id": 903, "name": "Hidden quiz", "courseid": 7, "timestart": NOW_TS + DAY, "visible": 0},
    {"id": 904, "name": "Another course", "courseid": 99, "timestart": NOW_TS + DAY, "visible": 1},
    {"id": 905, "name": "Already past", "courseid": 7, "timestart": NOW_TS - DAY, "visible": 1},
]


def mock_moodle(*, forums=None, discussions=None, events=None, fail=None, warnings=None, calls=None,
                intercept=None):
    """token.php + the login profile calls (student in WIF3001 id 7 and WIA2002 id 8) + the
    snapshot calls. `fail` = wsfunction name that errors; `warnings` = wsfunction answering with
    warnings. `calls` collects (wsfunction, form) for inspection. `intercept(fn)` (async) may
    return a response or raise before the normal answer."""
    forums = DEFAULT_FORUMS if forums is None else forums
    discussions = DEFAULT_DISCUSSIONS if discussions is None else discussions
    events = DEFAULT_EVENTS if events is None else events
    respx.post(_url("/login/token.php")).mock(
        return_value=httpx.Response(200, json={"token": TOKEN, "privatetoken": None}))

    async def ws(request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        assert form["wstoken"] == TOKEN, "only the user's own token may be used"
        fn = form["wsfunction"]
        if calls is not None:
            calls.append((fn, form))
        if intercept is not None:
            answer = await intercept(fn)
            if answer is not None:
                return answer
        if fn == fail:
            return httpx.Response(200, json={"exception": "moodle_exception", "errorcode": "nopermission",
                                             "message": "no"})
        if fn == "core_webservice_get_site_info":
            return httpx.Response(200, json={"userid": 42, "username": "23004001", "fullname": "Ali Hassan"})
        if fn == "core_user_get_users_by_field":
            return httpx.Response(200, json=[{"id": 42, "username": "23004001", "fullname": "Ali Hassan",
                                              "email": "ali@siswa.um.edu.my", "idnumber": "23004001"}])
        if fn == "core_enrol_get_users_courses":
            return httpx.Response(200, json=[{"id": 7, "shortname": "WIF3001", "fullname": "Software Testing"},
                                             {"id": 8, "shortname": "WIA2002", "fullname": "Databases"}])
        if fn == "core_enrol_get_enrolled_users":
            return httpx.Response(200, json=[{"id": 42, "roles": [{"shortname": "student"}]}])
        if fn == "mod_forum_get_forums_by_courses":
            return httpx.Response(200, json=forums)
        if fn == "mod_forum_get_forum_discussions":
            body = {"discussions": discussions.get(int(form["forumid"]), []), "warnings": []}
            if fn == warnings:
                body["warnings"] = [{"item": "forum", "warningcode": "x", "message": "partial"}]
            return httpx.Response(200, json=body)
        if fn == "core_calendar_get_calendar_events":
            body = {"events": events, "warnings": []}
            if fn == warnings:
                body["warnings"] = [{"item": "course", "itemid": 8, "warningcode": "nopermissions",
                                     "message": "partial"}]
            return httpx.Response(200, json=body)
        raise AssertionError(f"unexpected wsfunction {fn}")

    respx.post(_url("/webservice/rest/server.php")).mock(side_effect=ws)


async def _login(client):
    return await client.post("/auth/moodle-login", json={"username": "23004001", "password": PASSWORD})


async def _snapshot(db_session):
    db_session.expire_all()
    return (await db_session.execute(select(MoodleSnapshot))).scalars().all()


# ── unit tests (respx) ────────────────────────────────────────────────────────

@pytest.mark.db
@respx.mock
async def test_login_saves_announcements_and_deadlines(client, db_session):
    mock_moodle()
    resp = await _login(client)
    assert resp.status_code == 200, resp.text
    user_id = resp.json()["user"]["id"]

    [row] = await _snapshot(db_session)
    assert row.user_id == user_id
    assert row.refreshed_at == datetime(2026, 11, 22, 10, 0)     # naive MYT
    base = settings.MOODLE_URL.rstrip("/")
    # only news forums, newest first, title cleaned of HTML, with course + date + Moodle link
    assert row.announcements == [
        {"course_id": 7, "course_code": "WIF3001", "course_name": "Software Testing", "id": 501,
         "title": "Test 1 moved to Week 9 & room DK1", "date": "2026-11-21T10:00:00+08:00",
         "link": f"{base}/mod/forum/discuss.php?d=501"},
        {"course_id": 8, "course_code": "WIA2002", "course_name": "Databases", "id": 701,
         "title": "Lab 3 released", "date": "2026-11-20T10:00:00+08:00",
         "link": f"{base}/mod/forum/discuss.php?d=701"},
    ]
    # visible, upcoming events of the user's courses only, soonest first
    assert [(d["id"], d["course_code"], d["type"]) for d in row.deadlines] == [
        (902, "WIF3001", "assign"), (901, "WIA2002", "assign")]
    first = row.deadlines[0]
    assert first["title"] == "Project proposal is due"
    assert first["date"] == "2026-11-23T10:00:00+08:00"
    assert first["link"] == f"{base}/calendar/view.php?view=day&course=7&time={NOW_TS + DAY}"

    got = await moodle_snapshot.get_snapshot(db_session, user_id)
    assert got["announcements"] == row.announcements and got["refreshed_at"] == row.refreshed_at


@pytest.mark.db
@respx.mock
async def test_requests_use_the_users_courses_and_the_deadline_window(client, monkeypatch):
    monkeypatch.setattr(settings, "MOODLE_SNAPSHOT_DEADLINE_DAYS", 14)
    calls = []
    mock_moodle(calls=calls)
    assert (await _login(client)).status_code == 200
    forms = {fn: form for fn, form in calls}
    assert {forms["mod_forum_get_forums_by_courses"][k] for k in ("courseids[0]", "courseids[1]")} == {"7", "8"}
    # discussions only for the news forums
    assert sorted(f["forumid"] for fn, f in calls if fn == "mod_forum_get_forum_discussions") == ["11", "21"]
    cal = forms["core_calendar_get_calendar_events"]
    assert {cal["events[courseids][0]"], cal["events[courseids][1]"]} == {"7", "8"}
    assert cal["options[userevents]"] == "0" and cal["options[siteevents]"] == "0"
    assert int(cal["options[timestart]"]) == NOW_TS
    assert int(cal["options[timeend]"]) == NOW_TS + 14 * DAY


@pytest.mark.db
@respx.mock
async def test_relogin_replaces_the_snapshot(client, db_session, monkeypatch):
    mock_moodle()
    assert (await _login(client)).status_code == 200
    respx.reset()
    later = datetime(2026, 11, 23, 2, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(moodle_snapshot, "clock", lambda: later)
    mock_moodle(discussions={11: [_discussion(502, "New post", NOW_TS)]}, events=[])
    assert (await _login(client)).status_code == 200
    [row] = await _snapshot(db_session)
    assert [a["id"] for a in row.announcements] == [502]
    assert row.deadlines == []
    assert row.refreshed_at == datetime(2026, 11, 23, 10, 0)


@pytest.mark.db
@respx.mock
@pytest.mark.parametrize("failure", [
    {"fail": "mod_forum_get_forums_by_courses"},
    {"fail": "mod_forum_get_forum_discussions"},
    {"fail": "core_calendar_get_calendar_events"},
    {"warnings": "core_calendar_get_calendar_events"},
    {"warnings": "mod_forum_get_forum_discussions"},
    {"forums": {"unexpected": "shape"}},
    {"events": [{"name": "no id", "courseid": 7, "timestart": NOW_TS + DAY}]},
])
async def test_moodle_failure_keeps_previous_snapshot_and_login_succeeds(client, db_session, monkeypatch,
                                                                          failure, caplog):
    mock_moodle()
    assert (await _login(client)).status_code == 200
    [before] = await _snapshot(db_session)
    before = (before.announcements, before.deadlines, before.refreshed_at)

    respx.reset()
    monkeypatch.setattr(moodle_snapshot, "clock", lambda: datetime(2026, 11, 23, 2, 0, tzinfo=timezone.utc))
    mock_moodle(**failure)
    caplog.set_level(logging.DEBUG)
    resp = await _login(client)
    assert resp.status_code == 200, resp.text
    [after] = await _snapshot(db_session)
    assert (after.announcements, after.deadlines, after.refreshed_at) == before
    assert "previous snapshot kept" in caplog.text
    assert TOKEN not in caplog.text and PASSWORD not in caplog.text


@pytest.mark.db
@respx.mock
@pytest.mark.parametrize("error", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow"),
                                   httpx.Response(500, text="boom"), httpx.Response(200, text="<html>")])
async def test_moodle_down_during_snapshot_never_fails_login(client, db_session, error):
    """The first login with no snapshot yet: login works, nothing is saved."""
    async def flaky(fn):
        if fn.startswith(("mod_forum", "core_calendar")):
            if isinstance(error, Exception):
                raise error
            return error
        return None

    mock_moodle(intercept=flaky)
    resp = await _login(client)
    assert resp.status_code == 200, resp.text
    assert await _snapshot(db_session) == []
    assert (await db_session.execute(select(func.count(User.id)))).scalar_one() == 1


@pytest.mark.db
@respx.mock
async def test_slow_moodle_is_cut_off_by_the_timeout(client, db_session, monkeypatch):
    import asyncio

    monkeypatch.setattr(settings, "MOODLE_SNAPSHOT_TIMEOUT_SECONDS", 0.2)
    async def slow(fn):
        if fn == "core_calendar_get_calendar_events":
            await asyncio.sleep(5)
        return None

    mock_moodle(intercept=slow)
    loop = asyncio.get_running_loop()
    started = loop.time()
    resp = await _login(client)
    assert resp.status_code == 200
    assert loop.time() - started < 3
    assert await _snapshot(db_session) == []


@pytest.mark.db
@respx.mock
async def test_token_is_never_stored_logged_or_returned(client, db_session, caplog):
    caplog.set_level(logging.DEBUG)
    mock_moodle()
    resp = await _login(client)
    assert resp.status_code == 200
    assert TOKEN not in resp.text and PASSWORD not in resp.text
    assert TOKEN not in caplog.text and PASSWORD not in caplog.text
    # no column of any table holds the token
    tables = (await db_session.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))).scalars().all()
    for table in tables:
        rows = (await db_session.execute(text(f'SELECT row_to_json(t)::text FROM "{table}" t'))).scalars().all()
        assert not any(TOKEN in r for r in rows), table
    # the password reached Moodle only once, at token.php
    assert len([c for c in respx.calls if c.request.url.path.endswith("/login/token.php")]) == 1
    for call in respx.calls:
        if not call.request.url.path.endswith("/login/token.php"):
            assert PASSWORD.encode() not in call.request.content


async def test_refresh_without_a_token_does_nothing_and_never_uses_the_service_token(monkeypatch):
    """MoodleClient falls back to the service token (which sees every course) when given none."""
    profile = moodle_sync_profile()
    profile.moodle_token = None
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(_url("/webservice/rest/server.php"))
        assert await moodle_snapshot.refresh_on_login(1, profile) is False
        assert not route.called


async def test_refresh_clears_the_token_from_the_profile(monkeypatch):
    profile = moodle_sync_profile()
    profile.moodle_token = TOKEN

    async def boom(*args):
        raise RuntimeError("db down")

    monkeypatch.setattr(moodle_snapshot, "_refresh", boom)
    assert await moodle_snapshot.refresh_on_login(1, profile) is False
    assert profile.moodle_token is None
    assert TOKEN not in repr(profile)


def moodle_sync_profile():
    from app.services.moodle_auth import MoodleProfile
    return MoodleProfile(user_id=42, username="u", fullname="U", email=None, idnumber=None,
                         department=None, teaches=False,
                         courses=[moodle_sync.MoodleCourse(id=7, shortname="WIF3001", fullname="Software Testing")])


@pytest.mark.db
@respx.mock
async def test_links_use_the_public_moodle_url_and_lists_are_capped(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "MOODLE_PUBLIC_URL", "https://spectrum.um.edu.my/")
    monkeypatch.setattr(settings, "MOODLE_SNAPSHOT_MAX_ITEMS", 3)
    many = [_discussion(800 + i, f"Post {i}", NOW_TS - i * 60) for i in range(8)]
    events = [{"id": 950 + i, "name": f"Due {i}", "courseid": 7, "timestart": NOW_TS + (i + 1) * 3600,
               "visible": 1} for i in range(6)]
    mock_moodle(discussions={11: many}, events=events)
    assert (await _login(client)).status_code == 200
    [row] = await _snapshot(db_session)
    assert [a["id"] for a in row.announcements] == [800, 801, 802]
    assert [d["id"] for d in row.deadlines] == [950, 951, 952]
    assert row.announcements[0]["link"] == "https://spectrum.um.edu.my/mod/forum/discuss.php?d=800"
    assert row.deadlines[0]["link"].startswith("https://spectrum.um.edu.my/calendar/view.php?")
    assert row.deadlines[0]["type"] is None


@pytest.mark.db
@respx.mock
async def test_snapshot_is_per_user(client, db_session):
    mock_moodle()
    me = (await _login(client)).json()["user"]["id"]
    other = User(email="o@siswa.um.edu.my", password_hash=None, role="student", name="O", status="active")
    db_session.add(other)
    await db_session.commit()
    assert await moodle_snapshot.get_snapshot(db_session, other.id) is None
    assert (await moodle_snapshot.get_snapshot(db_session, me))["announcements"]


def test_course_sync_does_not_refresh_the_snapshot():
    """Manual/scheduled course syncs (FR-104) never touch the snapshot (FR-203)."""
    import inspect

    source = inspect.getsource(moodle_sync)
    assert "moodle_snapshot" not in source and "refresh_on_login" not in source


# ── against the local Moodle (SPeCTRUM simulation) ───────────────────────────

@pytest.mark.db
@pytest.mark.moodle
async def test_local_moodle_login_saves_a_snapshot(client, db_session, monkeypatch):
    monkeypatch.setattr(moodle_snapshot, "clock", lambda: datetime.now(timezone.utc))
    resp = await client.post("/auth/moodle-login", json={"username": "student1", "password": "Student123!"})
    assert resp.status_code == 200, resp.text
    user_id = resp.json()["user"]["id"]
    snap = await moodle_snapshot.get_snapshot(db_session, user_id)
    assert snap is not None, "the snapshot web services must be allowed in the smartclass service"
    assert isinstance(snap["announcements"], list) and isinstance(snap["deadlines"], list)
    for item in snap["announcements"] + snap["deadlines"]:
        assert {"course_id", "course_code", "course_name", "id", "title", "date", "link"} <= set(item)
        assert item["link"].startswith(settings.MOODLE_URL.rstrip("/"))
    raw = json.dumps(snap["announcements"] + snap["deadlines"])
    assert "token" not in raw.lower()
