"""S19: "Send a test notification" from the apps' preferences screen.

The test notification is an ordinary important one (feed, push), at most one per minute per user.
Expo push goes to the respx fake only."""
from datetime import datetime, timedelta

import pytest

from app.services.notifications import push, store

pytestmark = pytest.mark.db

T0 = datetime(2026, 11, 23, 9, 0)
TOK = "ExponentPushToken[tttttttttttttttttttttt]"


@pytest.fixture
def clock(monkeypatch):
    state = {"now": T0}
    monkeypatch.setattr(store, "clock", lambda: state["now"])
    return state


async def test_test_notification_lands_in_the_callers_feed_and_is_pushed(shino_class, fake_expo_push, clock):
    me = shino_class.lecturer_user_id
    async with shino_class.client(me, "lecturer") as c:
        assert (await c.post("/me/push-tokens", json={"token": TOK, "platform": "android"})).status_code == 201
        r = await c.post("/notifications/test")
        assert r.status_code == 200 and r.json() == {"sent": True}
        await push.drain()
        feed = (await c.get("/notifications")).json()
    assert feed["unread_count"] == 1
    [item] = feed["items"]
    assert item["event"] == "notification.test" and item["priority"] == "important"
    assert item["title"] == "Test notification" and item["link"] is None
    assert fake_expo_push.tokens == [TOK]


async def test_only_one_test_notification_per_minute(shino_class, clock):
    me = shino_class.student_user_ids[0]
    async with shino_class.client(me, "student") as c:
        assert (await c.post("/notifications/test")).json() == {"sent": True}
        clock["now"] = T0 + timedelta(seconds=30)
        assert (await c.post("/notifications/test")).json() == {"sent": False}
        clock["now"] = T0 + timedelta(seconds=61)
        assert (await c.post("/notifications/test")).json() == {"sent": True}
        assert (await c.get("/notifications")).json()["unread_count"] == 2


async def test_test_notification_goes_to_the_caller_only(shino_class, clock):
    me, other = shino_class.student_user_ids[:2]
    async with shino_class.client(me, "student") as c:
        await c.post("/notifications/test")
    async with shino_class.client(other, "student") as c:
        assert (await c.get("/notifications")).json()["items"] == []


async def test_test_notification_needs_sign_in(shino_class):
    async with shino_class.client() as c:
        assert (await c.post("/notifications/test")).status_code in (401, 403)
