"""S17: lecturer announcements (FR-217, NFR-04).

Moodle is mocked with respx (`FakeMoodle`); the `moodle` test at the bottom posts to the local
SPeCTRUM simulation.
"""
import logging
from datetime import datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.announcement import Announcement
from app.models.audit import AuditLog
from app.models.class_ import Course
from app.models.notification import Notification
from app.models.user import User
from app.services.notifications import announcements

pytestmark = pytest.mark.db

SERVICE_TOKEN = "svc-token-announcements-xyz"
NOW = datetime(2026, 11, 22, 10, 0)          # naive MYT
MOODLE_COURSE_ID = 77
NEWS_FORUM_ID = 31


def _url(path: str) -> str:
    return f"{settings.MOODLE_URL.rstrip('/')}{path}"


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = Clock(NOW)
    monkeypatch.setattr(announcements, "clock", c)
    monkeypatch.setattr(settings, "MOODLE_TOKEN", SERVICE_TOKEN)
    monkeypatch.setattr(settings, "MOODLE_PUBLIC_URL", "")
    monkeypatch.setattr(settings, "ANNOUNCEMENT_MOODLE_RETRY_BASE_SECONDS", 30)
    monkeypatch.setattr(settings, "ANNOUNCEMENT_MOODLE_RETRY_MAX_SECONDS", 1800)
    monkeypatch.setattr(settings, "ANNOUNCEMENT_MOODLE_MAX_ATTEMPTS", 5)
    monkeypatch.setattr(settings, "ANNOUNCEMENT_MOODLE_INTERVAL_SECONDS", 30)
    return c


class FakeMoodle:
    """The Moodle web services an announcement post uses, answering for the service token only."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.forums = [
            {"id": 30, "course": MOODLE_COURSE_ID, "type": "general", "name": "Q&A"},
            {"id": NEWS_FORUM_ID, "course": MOODLE_COURSE_ID, "type": "news", "name": "Announcements"},
        ]
        self.discussions: list[dict] = []    # newest last
        self.fail_next = 0                   # add_discussion answers a Moodle exception
        self.lose_reply_next = 0             # add_discussion creates the post, then the reply is lost
        self.network_down = False
        self.course_exists = True
        self._next_id = 900

    def added(self) -> list[dict]:
        return [form for fn, form in self.calls if fn == "mod_forum_add_discussion"]

    def handle(self, request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        assert form["wstoken"] == SERVICE_TOKEN
        fn = form["wsfunction"]
        self.calls.append((fn, form))
        if self.network_down:
            raise httpx.ConnectError(f"cannot reach {request.url}", request=request)
        if fn == "core_course_get_courses_by_field":
            courses = [{"id": MOODLE_COURSE_ID, "shortname": form["value"]}] if self.course_exists else []
            return httpx.Response(200, json={"courses": courses, "warnings": []})
        if fn == "mod_forum_get_forums_by_courses":
            return httpx.Response(200, json=[f for f in self.forums
                                             if f["course"] == int(form["courseids[0]"])])
        if fn == "mod_forum_get_forum_discussions":
            return httpx.Response(200, json={"discussions": list(reversed(self.discussions)), "warnings": []})
        if fn == "mod_forum_add_discussion":
            if self.fail_next:
                self.fail_next -= 1
                return httpx.Response(200, json={"exception": "moodle_exception",
                                                 "errorcode": "cannotcreatediscussion",
                                                 "message": "Could not create new discussion"})
            self._next_id += 1
            self.discussions.append({"discussion": self._next_id, "id": self._next_id + 5000,
                                     "name": form["subject"], "subject": form["subject"],
                                     "message": form["message"], "forum": int(form["forumid"])})
            if self.lose_reply_next:
                self.lose_reply_next -= 1
                raise httpx.ReadTimeout("reply lost", request=request)
            return httpx.Response(200, json={"discussionid": self._next_id, "warnings": []})
        raise AssertionError(f"unexpected wsfunction {fn}")


@pytest.fixture
def moodle(clock):
    fake = FakeMoodle()
    with respx.mock(assert_all_called=False) as router:
        router.post(_url("/webservice/rest/server.php")).mock(side_effect=fake.handle)
        yield fake


async def _send(c, occurrence_id, **body):
    body = {"title": "Test 1 moved", "message": "Test 1 is now on Friday.", **body}
    return await c.post(f"/lecturer/classes/{occurrence_id}/announcements", json=body)


async def _notifications(event="announcement.posted"):
    async with AsyncSessionLocal() as db:
        return list((await db.execute(
            select(Notification).where(Notification.event == event).order_by(Notification.user_id)
        )).scalars())


async def _row(announcement_id) -> Announcement:
    async with AsyncSessionLocal() as db:
        return await db.get(Announcement, announcement_id)


# ── sending + notifications ──────────────────────────────────────────────────

async def test_lecturer_announcement_notifies_enrolled_students_as_important(shino_class, moodle):
    sc = shino_class
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        resp = await _send(c, sc.occurrence_id, title="Test 1 moved",
                           message="Test 1 is now on Friday.\nBring your matric card.")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["occurrence_id"] == sc.occurrence_id and body["course_code"] == "SH101"
    assert body["title"] == "Test 1 moved" and body["recipient_count"] == 4
    assert body["author_name"] == "Shino Lecturer"
    assert body["moodle"]["status"] == "not_requested" and body["moodle"]["attempts"] == 0

    notes = await _notifications()
    assert sorted(n.user_id for n in notes) == sorted(sc.student_user_ids)      # nobody else
    for n in notes:
        assert n.priority == "important"
        assert n.title == "Test 1 moved"
        assert n.message == "Test 1 is now on Friday.\nBring your matric card."
        assert n.link == f"/announcements/{body['id']}"
    await announcements.drain()
    assert moodle.calls == []                         # in-app only: Moodle never called

    async with AsyncSessionLocal() as db:
        [audit] = (await db.execute(select(AuditLog).where(AuditLog.action == "ANNOUNCEMENT_SEND"))).scalars()
    assert audit.actor_id == sc.lecturer_user_id and audit.target_id == str(sc.occurrence_id)
    assert "Friday" not in (audit.new_val or "")      # the audit log keeps no message text


async def test_long_message_is_delivered_in_full(shino_class, moodle):
    sc = shino_class
    message = ("Line one of a long announcement. " * 20 + "\n" + "x" * 300)[:1000]
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        resp = await _send(c, sc.occurrence_id, title="  Room   change\tfor Week 9  ", message=message)
    assert resp.status_code == 201, resp.text
    assert resp.json()["title"] == "Room change for Week 9"
    notes = await _notifications()
    assert len(notes) == 4 and all(n.message == message.strip() for n in notes)
    assert all(n.title == "Room change for Week 9" for n in notes)


async def test_inactive_students_are_not_notified(shino_class, moodle):
    sc = shino_class
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == sc.student_user_ids[0]).values(status="inactive"))
        await db.commit()
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        resp = await _send(c, sc.occurrence_id)
    assert resp.status_code == 201 and resp.json()["recipient_count"] == 3
    assert sorted(n.user_id for n in await _notifications()) == sorted(sc.student_user_ids[1:])


async def test_two_announcements_are_two_notifications(shino_class, moodle):
    sc = shino_class
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        assert (await _send(c, sc.occurrence_id)).status_code == 201
        assert (await _send(c, sc.occurrence_id)).status_code == 201   # same text, new announcement
    assert len(await _notifications()) == 8


async def test_only_the_teaching_lecturer_can_send_or_list(shino_class, moodle):
    sc = shino_class
    for user_id, role in [(sc.other_lecturer_user_id, "lecturer"), (sc.student_user_ids[0], "student"),
                          (sc.outsider_user_id, "student")]:
        async with sc.client(user_id, role) as c:
            assert (await _send(c, sc.occurrence_id)).status_code == 403
            assert (await c.get(f"/lecturer/classes/{sc.occurrence_id}/announcements")).status_code == 403
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        assert (await _send(c, 999999)).status_code == 403                    # unknown class
        assert (await _send(c, sc.other_occurrence_id)).status_code == 403    # not their class
        assert (await c.get("/lecturer/classes/999999/announcements")).status_code == 403
    async with sc.client() as c:
        assert (await _send(c, sc.occurrence_id)).status_code in (401, 403)
    assert await _notifications() == []
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(Announcement))).scalars().all() == []


@pytest.mark.parametrize("body", [
    {"title": "   "},
    {"message": " \n\t "},
    {"title": "t" * 201},
    {"message": "m" * 1001},
    {"post_to_moodle": "yes"},
    {"title": 5},
    {"priority": "urgent"},           # the priority is set by the event, never by the caller
])
async def test_invalid_bodies_are_rejected(shino_class, moodle, body):
    sc = shino_class
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        resp = await _send(c, sc.occurrence_id, **body)
    assert resp.status_code == 422, resp.text
    assert await _notifications() == []


# ── posting to Moodle ────────────────────────────────────────────────────────

async def test_post_to_moodle_goes_to_the_course_news_forum(shino_class, moodle):
    sc = shino_class
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        resp = await _send(c, sc.occurrence_id, title="Lab <3> moved",
                           message="Lab is in <b>DK2</b> & starts 9am.\nSee you.", post_to_moodle=True)
        assert resp.status_code == 201
        assert resp.json()["moodle"]["status"] == "pending"
        await announcements.drain()
        [item] = (await c.get(f"/lecturer/classes/{sc.occurrence_id}/announcements")).json()

    [form] = moodle.added()
    assert form["forumid"] == str(NEWS_FORUM_ID)                  # the news forum, not Q&A
    assert form["subject"] == "Lab <3> moved"
    assert "Lab is in &lt;b&gt;DK2&lt;/b&gt; &amp; starts 9am.<br>See you." in form["message"]
    assert "Shino Lecturer" in form["message"]
    assert announcements.marker(item["id"]) in form["message"]
    assert item["moodle"]["status"] == "posted" and item["moodle"]["attempts"] == 1
    assert item["moodle"]["error"] is None and item["moodle"]["next_try_at"] is None
    assert item["moodle"]["discussion_id"] == moodle.discussions[0]["discussion"]
    assert item["moodle"]["link"] == _url(f"/mod/forum/discuss.php?d={item['moodle']['discussion_id']}")
    assert len(await _notifications()) == 4                       # students are notified as well


async def test_known_moodle_course_id_skips_the_lookup(shino_class, moodle):
    sc = shino_class
    async with AsyncSessionLocal() as db:
        await db.execute(update(Course).where(Course.id == sc.course_id).values(moodle_course_id=MOODLE_COURSE_ID))
        await db.commit()
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        resp = await _send(c, sc.occurrence_id, post_to_moodle=True)
    await announcements.drain()
    assert "core_course_get_courses_by_field" not in [fn for fn, _ in moodle.calls]
    assert (await _row(resp.json()["id"])).moodle_status == "posted"


async def test_failed_post_is_retried_with_backoff_until_posted(shino_class, moodle, clock):
    sc = shino_class
    moodle.fail_next = 2
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        resp = await _send(c, sc.occurrence_id, post_to_moodle=True)
        aid = resp.json()["id"]
        await announcements.drain()
        [item] = (await c.get(f"/lecturer/classes/{sc.occurrence_id}/announcements")).json()
    # the in-app notification is sent although Moodle failed (UC exception flow)
    assert len(await _notifications()) == 4
    m = item["moodle"]
    assert m["status"] == "pending" and m["attempts"] == 1
    assert "cannotcreatediscussion" in m["error"]
    assert m["next_try_at"] == (NOW + timedelta(seconds=30)).isoformat()

    clock.now = NOW + timedelta(seconds=10)                 # not due yet
    assert await announcements.run_due() == {}
    assert len(moodle.added()) == 1

    clock.now = NOW + timedelta(seconds=31)
    assert await announcements.run_due() == {aid: "pending"}
    row = await _row(aid)
    assert row.moodle_attempts == 2 and row.moodle_next_at == clock.now + timedelta(seconds=60)

    clock.now = row.moodle_next_at
    assert await announcements.run_due() == {aid: "posted"}
    row = await _row(aid)
    assert row.moodle_attempts == 3 and row.moodle_error is None and row.moodle_next_at is None
    assert len(moodle.discussions) == 1
    assert await announcements.run_due() == {}             # nothing left to do
    assert len(await _notifications()) == 4                 # retries never re-notify students


async def test_post_gives_up_after_the_last_try(shino_class, moodle, clock, monkeypatch):
    sc = shino_class
    monkeypatch.setattr(settings, "ANNOUNCEMENT_MOODLE_MAX_ATTEMPTS", 3)
    moodle.fail_next = 99
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        aid = (await _send(c, sc.occurrence_id, post_to_moodle=True)).json()["id"]
    await announcements.drain()
    for _ in range(5):
        clock.now += timedelta(hours=1)
        await announcements.run_due()
    row = await _row(aid)
    assert row.moodle_status == "failed" and row.moodle_attempts == 3
    assert row.moodle_next_at is None and "cannotcreatediscussion" in row.moodle_error
    assert len(moodle.added()) == 3


async def test_backoff_is_capped(clock, monkeypatch):
    monkeypatch.setattr(settings, "ANNOUNCEMENT_MOODLE_RETRY_MAX_SECONDS", 100)
    assert [announcements.retry_delay(n).total_seconds() for n in (1, 2, 3, 4, 10)] == [30, 60, 100, 100, 100]


async def test_lost_reply_is_not_posted_twice(shino_class, moodle, clock):
    sc = shino_class
    moodle.lose_reply_next = 1
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        aid = (await _send(c, sc.occurrence_id, post_to_moodle=True)).json()["id"]
    await announcements.drain()
    row = await _row(aid)
    assert row.moodle_status == "pending" and row.moodle_error == "ReadTimeout"
    clock.now = row.moodle_next_at
    assert await announcements.run_due() == {aid: "posted"}
    assert len(moodle.added()) == 1 and len(moodle.discussions) == 1
    assert (await _row(aid)).moodle_discussion_id == moodle.discussions[0]["discussion"]


async def test_marker_of_another_announcement_does_not_count(shino_class, moodle, clock):
    """#1's retry must not mistake #12's post (or any other) for its own."""
    sc = shino_class
    moodle.fail_next = 1
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        aid = (await _send(c, sc.occurrence_id, post_to_moodle=True)).json()["id"]
    await announcements.drain()
    moodle.discussions.append({"discussion": 555, "message": f"x {announcements.marker(int(f'{aid}2'))}"})
    clock.now = (await _row(aid)).moodle_next_at
    await announcements.run_due()
    assert len(moodle.added()) == 2 and (await _row(aid)).moodle_discussion_id != 555


@pytest.mark.parametrize("setup, error", [
    (lambda m: setattr(m, "forums", [f for f in m.forums if f["type"] != "news"]), "has no announcements forum"),
    (lambda m: setattr(m, "course_exists", False), "is not in Moodle"),
])
async def test_course_problems_are_shown_to_the_lecturer(shino_class, moodle, setup, error):
    sc = shino_class
    setup(moodle)
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        await _send(c, sc.occurrence_id, post_to_moodle=True)
        await announcements.drain()
        [item] = (await c.get(f"/lecturer/classes/{sc.occurrence_id}/announcements")).json()
    assert item["moodle"]["status"] == "pending" and error in item["moodle"]["error"]
    assert moodle.added() == []


async def test_network_failure_logs_and_stores_no_token_or_url(shino_class, moodle, caplog):
    sc = shino_class
    moodle.network_down = True
    caplog.set_level(logging.DEBUG)
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        aid = (await _send(c, sc.occurrence_id, post_to_moodle=True)).json()["id"]
    await announcements.drain()
    row = await _row(aid)
    assert row.moodle_status == "pending" and row.moodle_error == "ConnectError"
    assert SERVICE_TOKEN not in caplog.text and "server.php" not in caplog.text
    assert "Test 1 is now on Friday" not in caplog.text


async def test_without_moodle_token_the_first_failure_is_final(shino_class, monkeypatch, clock):
    sc = shino_class
    monkeypatch.setattr(settings, "MOODLE_TOKEN", "")
    with respx.mock(assert_all_called=False):                 # any Moodle call would fail the test
        async with sc.client(sc.lecturer_user_id, "lecturer") as c:
            resp = await _send(c, sc.occurrence_id, post_to_moodle=True)
        await announcements.drain()
    assert resp.status_code == 201
    row = await _row(resp.json()["id"])
    assert row.moodle_status == "failed" and "MOODLE_TOKEN" in row.moodle_error
    assert len(await _notifications()) == 4


async def test_pending_post_survives_a_restart(shino_class, moodle, clock, monkeypatch):
    """The queue is the table: a row left pending (server stopped before its first try) is
    posted by the retry loop."""
    sc = shino_class
    monkeypatch.setattr(announcements, "schedule", lambda _id: None)    # "crash" before the try
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        aid = (await _send(c, sc.occurrence_id, post_to_moodle=True)).json()["id"]
    assert (await _row(aid)).moodle_status == "pending" and moodle.added() == []
    assert await announcements.run_due() == {aid: "posted"}


# ── listing ──────────────────────────────────────────────────────────────────

async def test_list_is_newest_first_and_per_class(shino_class, moodle):
    sc = shino_class
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        first = (await _send(c, sc.occurrence_id, title="First")).json()["id"]
        second = (await _send(c, sc.occurrence_id, title="Second", post_to_moodle=True)).json()["id"]
        await announcements.drain()
        items = (await c.get(f"/lecturer/classes/{sc.occurrence_id}/announcements")).json()
    async with sc.client(sc.other_lecturer_user_id, "lecturer") as c:
        await _send(c, sc.other_occurrence_id, title="Other class")
        other = (await c.get(f"/lecturer/classes/{sc.other_occurrence_id}/announcements")).json()
    assert [i["id"] for i in items] == [second, first]
    assert [i["moodle"]["status"] for i in items] == ["posted", "not_requested"]
    assert set(items[0]) == {"id", "occurrence_id", "course_code", "title", "message", "author_name",
                             "recipient_count", "created_at", "moodle"}
    assert [i["title"] for i in other] == ["Other class"]


# ── against the local Moodle (SPeCTRUM simulation) ───────────────────────────

@pytest.mark.moodle
async def test_local_moodle_post_lands_in_the_news_forum(shino_class, monkeypatch):
    from app.services.kb.moodle_client import MoodleClient

    sc = shino_class
    async with AsyncSessionLocal() as db:         # post through the seeded WIA0000 course
        await db.execute(update(Course).where(Course.id == sc.course_id).values(code="WIA0000"))
        await db.commit()
    title = f"[SmartClass test] S17 announcement {datetime.now():%Y-%m-%d %H:%M:%S}"
    async with sc.client(sc.lecturer_user_id, "lecturer") as c:
        aid = (await _send(c, sc.occurrence_id, title=title, message="Posted by the S17 moodle test.",
                           post_to_moodle=True)).json()["id"]
    await announcements.drain()
    row = await _row(aid)
    assert row.moodle_status == "posted", row.moodle_error
    async with MoodleClient() as client:
        forum_id = await announcements._news_forum(client, Course(code="WIA0000"))
        body = await client.call("mod_forum_get_forum_discussions", forumid=forum_id, page=0, perpage=20)
    mine = [d for d in body["discussions"] if int(d["discussion"]) == row.moodle_discussion_id]
    assert mine and mine[0]["name"] == title
    assert announcements.marker(aid) in mine[0]["message"]     # what a retry looks for
