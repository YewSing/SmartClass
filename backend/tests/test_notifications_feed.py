"""S11: notification feed and read state (FR-208, FR-209)."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.notification import Notification
from app.services.notifications import store

T0 = datetime(2026, 11, 23, 9, 0)

pytestmark = pytest.mark.db


async def add(user_id: int, n: int, priority: str = "general", start: datetime = T0,
              step: timedelta = timedelta(minutes=1), read: bool = False, tag: str = "n") -> list[int]:
    """Insert `n` notifications for `user_id`, the i-th at start + i*step. Returns their ids."""
    async with AsyncSessionLocal() as db:
        rows = [
            Notification(user_id=user_id, event="announcement.posted", priority=priority,
                         title=f"{tag}{i}", message=f"msg {tag}{i}", link=f"/announcements/{i}",
                         subject_key=f"{tag}:{i}", created_at=start + i * step,
                         read_at=(start if read else None))
            for i in range(n)
        ]
        db.add_all(rows)
        await db.commit()
        return [r.id for r in rows]


async def read_at_of(nid: int):
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(Notification.read_at).where(Notification.id == nid))


@pytest.fixture
def clock(monkeypatch):
    state = {"now": T0 + timedelta(hours=1)}
    monkeypatch.setattr(store, "clock", lambda: state["now"])
    return state


# ── feed ─────────────────────────────────────────────────────────────────────────

async def test_feed_newest_first_with_read_state_and_unread_count(shino_class):
    me = shino_class.student_user_ids[0]
    await add(me, 3, tag="old", read=True)
    await add(me, 2, tag="new", start=T0 + timedelta(hours=1))
    async with shino_class.client(me, "student") as c:
        r = await c.get("/notifications")
    assert r.status_code == 200
    body = r.json()
    assert [i["title"] for i in body["items"]] == ["new1", "new0", "old2", "old1", "old0"]
    assert [i["read"] for i in body["items"]] == [False, False, True, True, True]
    assert body["unread_count"] == 2
    assert body["next_cursor"] is None
    first = body["items"][0]
    assert first["link"] == "/announcements/1" and first["priority"] == "general"
    assert set(first) == {"id", "event", "priority", "title", "message", "link", "read", "read_at", "created_at"}


async def test_same_timestamp_is_ordered_by_id(shino_class):
    me = shino_class.student_user_ids[0]
    ids = await add(me, 4, step=timedelta(0))
    async with shino_class.client(me, "student") as c:
        body = (await c.get("/notifications")).json()
    assert [i["id"] for i in body["items"]] == sorted(ids, reverse=True)


async def test_cursor_pagination_has_no_gaps_or_repeats(shino_class):
    me = shino_class.student_user_ids[0]
    # Two notifications share each timestamp, so pages split inside a tie.
    ids = await add(me, 5, tag="a") + await add(me, 5, tag="b")
    seen, cursor, pages = [], None, 0
    async with shino_class.client(me, "student") as c:
        while True:
            params = {"limit": 3, **({"cursor": cursor} if cursor else {})}
            body = (await c.get("/notifications", params=params)).json()
            pages += 1
            assert len(body["items"]) <= 3
            seen += [i["id"] for i in body["items"]]
            assert body["unread_count"] == 10
            cursor = body["next_cursor"]
            if cursor is None:
                break
    assert pages == 4
    assert len(seen) == len(set(seen)) == 10 and set(seen) == set(ids)
    async with shino_class.client(me, "student") as c:
        whole = [i["id"] for i in (await c.get("/notifications", params={"limit": 100})).json()["items"]]
    assert seen == whole


async def test_new_arrivals_between_pages_do_not_shift_older_pages(shino_class):
    me = shino_class.student_user_ids[0]
    await add(me, 4)
    async with shino_class.client(me, "student") as c:
        p1 = (await c.get("/notifications", params={"limit": 2})).json()
        await add(me, 3, start=T0 + timedelta(days=1), tag="late")
        p2 = (await c.get("/notifications", params={"limit": 2, "cursor": p1["next_cursor"]})).json()
    assert [i["title"] for i in p1["items"]] == ["n3", "n2"]
    assert [i["title"] for i in p2["items"]] == ["n1", "n0"]
    assert p2["next_cursor"] is None


async def test_exact_page_size_has_no_next_cursor(shino_class):
    me = shino_class.student_user_ids[0]
    await add(me, 3)
    async with shino_class.client(me, "student") as c:
        body = (await c.get("/notifications", params={"limit": 3})).json()
    assert len(body["items"]) == 3 and body["next_cursor"] is None


@pytest.mark.parametrize("params", [
    {"cursor": "not-a-cursor"}, {"cursor": "!!!"}, {"limit": 0}, {"limit": 101},
])
async def test_bad_cursor_or_limit_is_422(shino_class, params):
    async with shino_class.client(shino_class.student_user_ids[0], "student") as c:
        assert (await c.get("/notifications", params=params)).status_code == 422


async def test_empty_feed(shino_class):
    async with shino_class.client(shino_class.lecturer_user_id, "lecturer") as c:
        body = (await c.get("/notifications")).json()
    assert body == {"items": [], "next_cursor": None, "unread_count": 0}


async def test_every_role_has_a_feed(shino_class, users):
    for user in users.values():
        await add(user.id, 1, tag=user.role)
        async with shino_class.client(user.id, user.role) as c:
            body = (await c.get("/notifications")).json()
        assert [i["title"] for i in body["items"]] == [f"{user.role}0"]


async def test_requires_sign_in(shino_class):
    async with shino_class.client() as c:
        for method, path in [("get", "/notifications"), ("get", "/notifications/priority"),
                             ("post", "/notifications/read-all"), ("post", "/notifications/1/read")]:
            assert (await getattr(c, method)(path)).status_code in (401, 403), path


# ── priority (dashboard) ─────────────────────────────────────────────────────────

async def test_priority_lists_only_unread_urgent_then_important(shino_class):
    me = shino_class.student_user_ids[0]
    await add(me, 2, priority="important", tag="imp")
    await add(me, 2, priority="urgent", tag="urg", start=T0 - timedelta(hours=1))
    await add(me, 2, priority="general", tag="gen", start=T0 + timedelta(hours=2))
    await add(me, 1, priority="urgent", tag="readurg", read=True, start=T0 + timedelta(hours=3))
    async with shino_class.client(me, "student") as c:
        body = (await c.get("/notifications/priority")).json()
    assert [i["title"] for i in body["items"]] == ["urg1", "urg0", "imp1", "imp0"]
    assert all(not i["read"] for i in body["items"])
    assert body["unread_count"] == 6   # includes the 2 general ones


async def test_priority_item_leaves_once_read(shino_class, clock):
    me = shino_class.student_user_ids[0]
    [nid] = await add(me, 1, priority="urgent")
    async with shino_class.client(me, "student") as c:
        assert len((await c.get("/notifications/priority")).json()["items"]) == 1
        assert (await c.post(f"/notifications/{nid}/read")).status_code == 200
        assert (await c.get("/notifications/priority")).json()["items"] == []


# ── read state ───────────────────────────────────────────────────────────────────

async def test_mark_read_is_idempotent_and_updates_count(shino_class, clock):
    me = shino_class.student_user_ids[0]
    a, b = await add(me, 2)
    async with shino_class.client(me, "student") as c:
        r = await c.post(f"/notifications/{a}/read")
        assert r.status_code == 200
        body = r.json()
        assert body["notification"]["id"] == a and body["notification"]["read"] is True
        assert body["unread_count"] == 1
        first = await read_at_of(a)
        assert first == clock["now"]
        clock["now"] += timedelta(hours=1)
        again = (await c.post(f"/notifications/{a}/read")).json()
        assert again["unread_count"] == 1
    assert await read_at_of(a) == first          # first read time kept
    assert await read_at_of(b) is None


async def test_read_all_marks_only_the_callers_unread(shino_class, clock):
    me, other = shino_class.student_user_ids[:2]
    [old] = await add(me, 1, read=True, tag="old")
    await add(me, 3, priority="urgent")
    others = await add(other, 2)
    async with shino_class.client(me, "student") as c:
        body = (await c.post("/notifications/read-all")).json()
        assert body == {"marked": 3, "unread_count": 0}
        assert (await c.post("/notifications/read-all")).json() == {"marked": 0, "unread_count": 0}
        feed = (await c.get("/notifications")).json()
    assert all(i["read"] for i in feed["items"])
    assert await read_at_of(old) == T0               # an already-read one keeps its time
    for nid in others:
        assert await read_at_of(nid) is None
    async with shino_class.client(other, "student") as c:
        assert (await c.get("/notifications")).json()["unread_count"] == 2


# ── isolation ────────────────────────────────────────────────────────────────────

async def test_users_never_see_or_mark_each_others_notifications(shino_class, clock):
    me = shino_class.student_user_ids[0]
    [mine] = await add(me, 1, priority="urgent", tag="mine")
    [lecturers] = await add(shino_class.lecturer_user_id, 1, priority="urgent", tag="lec")
    async with shino_class.client(shino_class.outsider_user_id, "student") as c:
        feed = (await c.get("/notifications")).json()
        assert feed["items"] == [] and feed["unread_count"] == 0
        assert (await c.get("/notifications/priority")).json()["items"] == []
        r = await c.post(f"/notifications/{mine}/read")
        assert r.status_code == 404
        assert (await c.post("/notifications/999999/read")).status_code == 404
        assert (await c.post("/notifications/read-all")).json()["marked"] == 0
    async with shino_class.client(me, "student") as c:
        assert [i["title"] for i in (await c.get("/notifications")).json()["items"]] == ["mine0"]
        assert (await c.post(f"/notifications/{lecturers}/read")).status_code == 404
    assert await read_at_of(mine) is None
    assert await read_at_of(lecturers) is None


async def test_cursor_from_another_user_shows_only_own_rows(shino_class):
    me, other = shino_class.student_user_ids[:2]
    await add(me, 3, tag="me")
    await add(other, 3, tag="other")
    async with shino_class.client(other, "student") as c:
        cursor = (await c.get("/notifications", params={"limit": 1})).json()["next_cursor"]
    async with shino_class.client(me, "student") as c:
        body = (await c.get("/notifications", params={"cursor": cursor})).json()
    assert {i["title"][:2] for i in body["items"]} == {"me"}


async def test_emitted_notification_appears_in_feed(shino_class):
    from app.services import notify
    me = shino_class.student_user_ids[0]
    await notify.emit("quiz.published", [me], {"quiz_id": 4, "quiz_title": "Q4", "course_code": "SH101"})
    async with shino_class.client(me, "student") as c:
        body = (await c.get("/notifications/priority")).json()
    assert [(i["event"], i["title"], i["link"]) for i in body["items"]] == \
        [("quiz.published", "New quiz: Q4", "/quizzes/4")]
