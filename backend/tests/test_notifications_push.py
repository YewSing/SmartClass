"""S13: push tokens and Expo push for urgent/important notifications (FR-210, FR-212).

Every Expo call goes to the respx fake (`fake_expo_push`); nothing leaves the process."""
import logging
from urllib.parse import quote

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.push_token import PushToken
from app.services import notify
from app.services.notifications import push

pytestmark = pytest.mark.db

TOK_A = "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaaa]"
TOK_B = "ExponentPushToken[bbbbbbbbbbbbbbbbbbbbbb]"
TOK_C = "ExpoPushToken[cccccccccccccccccccccc]"
QUIZ = {"quiz_id": 7, "quiz_title": "Week 3 quiz", "course_code": "SH101"}


async def register(sc, user_id: int, token: str, platform: str = "android", role: str = "student"):
    async with sc.client(user_id, role) as c:
        return await c.post("/me/push-tokens", json={"token": token, "platform": platform})


async def tokens_of(user_id: int) -> list[str]:
    async with AsyncSessionLocal() as db:
        return sorted((await db.scalars(select(PushToken.token).where(PushToken.user_id == user_id))).all())


async def all_tokens() -> list[tuple[int, str]]:
    async with AsyncSessionLocal() as db:
        return sorted((await db.execute(select(PushToken.user_id, PushToken.token))).all())


async def emit(event: str, user_ids, payload) -> None:
    await notify.emit(event, user_ids, payload)
    await push.drain()


# ── registration ──────────────────────────────────────────────────────────────

async def test_register_new_token_then_refresh_is_one_row(shino_class):
    me = shino_class.student_user_ids[0]
    r = await register(shino_class, me, TOK_A)
    assert r.status_code == 201
    assert r.json()["token"] == TOK_A and r.json()["platform"] == "android"
    r2 = await register(shino_class, me, TOK_A)
    assert r2.status_code == 200
    assert await all_tokens() == [(me, TOK_A)]


async def test_two_devices_are_two_rows(shino_class):
    me = shino_class.student_user_ids[0]
    assert (await register(shino_class, me, TOK_A)).status_code == 201
    assert (await register(shino_class, me, TOK_C, platform="ios")).status_code == 201
    assert await tokens_of(me) == sorted([TOK_A, TOK_C])


async def test_same_device_signing_in_as_another_user_moves_the_token(shino_class):
    a, b = shino_class.student_user_ids[:2]
    await register(shino_class, a, TOK_A)
    r = await register(shino_class, b, TOK_A)
    assert r.status_code == 200
    assert await all_tokens() == [(b, TOK_A)]


async def test_concurrent_first_registrations_make_one_row(shino_class):
    import asyncio

    me = shino_class.student_user_ids[0]
    results = await asyncio.gather(*[register(shino_class, me, TOK_A) for _ in range(5)])
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 200, 200, 200, 201]
    assert await all_tokens() == [(me, TOK_A)]


@pytest.mark.parametrize("bad", [
    "", "abc", "ExponentPushToken[]", "ExponentPushToken[short]", "ExponentPushToken[aaaaaaaaaaaa",
    "https://evil.example/ExponentPushToken[aaaaaaaaaaaa]", "ExponentPushToken[aaaa aaaa aaaa]",
    "ExponentPushToken[" + "a" * 300 + "]",
])
async def test_invalid_token_format_is_422(shino_class, bad):
    r = await register(shino_class, shino_class.student_user_ids[0], bad)
    assert r.status_code == 422
    assert await all_tokens() == []


async def test_unknown_platform_is_422(shino_class):
    r = await register(shino_class, shino_class.student_user_ids[0], TOK_A, platform="web")
    assert r.status_code == 422


async def test_lecturer_can_register_too(shino_class):
    r = await register(shino_class, shino_class.lecturer_user_id, TOK_B, role="lecturer")
    assert r.status_code == 201


async def test_endpoints_need_sign_in(shino_class):
    async with shino_class.client() as c:
        r = await c.post("/me/push-tokens", json={"token": TOK_A, "platform": "android"})
        assert r.status_code in (401, 403)
        assert (await c.delete(f"/me/push-tokens/{quote(TOK_A)}")).status_code in (401, 403)
    assert await all_tokens() == []


# ── removal ───────────────────────────────────────────────────────────────────

async def test_delete_own_token(shino_class):
    me = shino_class.student_user_ids[0]
    await register(shino_class, me, TOK_A)
    async with shino_class.client(me, "student") as c:
        r = await c.delete(f"/me/push-tokens/{quote(TOK_A)}")
        assert r.status_code == 204
        assert (await c.delete(f"/me/push-tokens/{quote(TOK_A)}")).status_code == 404
    assert await all_tokens() == []


async def test_cannot_delete_someone_elses_token(shino_class):
    a, b = shino_class.student_user_ids[:2]
    await register(shino_class, a, TOK_A)
    async with shino_class.client(b, "student") as c:
        assert (await c.delete(f"/me/push-tokens/{quote(TOK_A)}")).status_code == 404
    assert await all_tokens() == [(a, TOK_A)]


# ── push delivery ─────────────────────────────────────────────────────────────

async def test_urgent_and_important_are_pushed_to_the_recipients_android_devices(shino_class, fake_expo_push):
    a, b, c = shino_class.student_user_ids[:3]
    await register(shino_class, a, TOK_A)
    await register(shino_class, b, TOK_B)
    await register(shino_class, c, TOK_C)          # not a recipient
    await emit("quiz.published", [a, b], QUIZ)     # important
    assert sorted(fake_expo_push.tokens) == [TOK_A, TOK_B]
    msg = fake_expo_push.messages[0]
    assert msg["title"] and msg["body"]
    assert msg["data"]["priority"] == "important" and msg["data"]["event"] == "quiz.published"
    assert msg["data"]["link"].startswith("/") and isinstance(msg["data"]["notification_id"], int)


async def test_urgent_is_pushed(shino_class, fake_expo_push):
    me = shino_class.lecturer_user_id
    await register(shino_class, me, TOK_A, role="lecturer")
    await emit("confusion.spike", [me], {"attendance_session_id": shino_class.session_id,
                                         "course_code": "SH101", "spike_id": 1})
    assert fake_expo_push.tokens == [TOK_A]
    assert fake_expo_push.messages[0]["data"]["priority"] == "urgent"


async def test_general_is_not_pushed(shino_class, fake_expo_push):
    me = shino_class.student_user_ids[0]
    await register(shino_class, me, TOK_A)
    await emit("attendance.recorded", [me], {"session_id": shino_class.session_id,
                                             "course_code": "SH101", "status": "present"})
    await emit("poll.started", [me], {"attendance_session_id": shino_class.session_id,
                                      "course_code": "SH101", "poll_id": 1})
    async with shino_class.client(me, "student") as c:
        assert (await c.get("/notifications")).json()["unread_count"] == 2   # stored, in-app only
    assert fake_expo_push.messages == []


async def test_ios_devices_are_not_pushed_by_default(shino_class, fake_expo_push):
    me = shino_class.student_user_ids[0]
    await register(shino_class, me, TOK_C, platform="ios")
    await emit("quiz.published", [me], QUIZ)
    assert fake_expo_push.messages == []        # FR-210: iOS gets in-app (and email, S14)


async def test_duplicate_event_is_not_pushed_again(shino_class, fake_expo_push):
    me = shino_class.student_user_ids[0]
    await register(shino_class, me, TOK_A)
    await emit("quiz.published", [me], QUIZ)
    await emit("quiz.published", [me], QUIZ)     # deduplicated by the store (FR-216)
    assert fake_expo_push.tokens == [TOK_A]


async def test_messages_are_batched_by_100(shino_class, fake_expo_push, monkeypatch):
    me = shino_class.student_user_ids[0]
    async with AsyncSessionLocal() as db:
        db.add_all([PushToken(user_id=me, token=f"ExponentPushToken[{i:022d}]", platform="android")
                    for i in range(150)])
        await db.commit()
    await emit("quiz.published", [me], QUIZ)
    assert [len(b) for b in fake_expo_push.batches] == [100, 50]
    assert len(set(fake_expo_push.tokens)) == 150


async def test_device_not_registered_deletes_that_token_only(shino_class, fake_expo_push):
    a, b = shino_class.student_user_ids[:2]
    await register(shino_class, a, TOK_A)
    await register(shino_class, b, TOK_B)
    fake_expo_push.unregistered.add(TOK_A)
    await emit("quiz.published", [a, b], QUIZ)
    assert await all_tokens() == [(b, TOK_B)]


async def test_network_failure_does_not_fail_the_request_or_lose_the_notification(
        shino_class, fake_expo_push, caplog):
    me = shino_class.student_user_ids[0]
    await register(shino_class, me, TOK_A)
    fake_expo_push.fail_network = True
    with caplog.at_level(logging.WARNING):
        await emit("quiz.published", [me], QUIZ)
    async with shino_class.client(me, "student") as c:
        body = (await c.get("/notifications")).json()
    assert body["unread_count"] == 1                     # stored and in the feed
    assert await all_tokens() == [(me, TOK_A)]           # a network error keeps the token
    assert "expo push" in caplog.text and TOK_A not in caplog.text


async def test_expo_server_error_keeps_tokens(shino_class, fake_expo_push):
    me = shino_class.student_user_ids[0]
    await register(shino_class, me, TOK_A)
    fake_expo_push.status_code = 500
    await emit("quiz.published", [me], QUIZ)
    assert len(fake_expo_push.batches) == 1
    assert await all_tokens() == [(me, TOK_A)]


async def test_emit_returns_before_the_push_is_sent(shino_class, fake_expo_push):
    """The push runs in a background task: emit's caller is never held up by Expo."""
    me = shino_class.student_user_ids[0]
    await register(shino_class, me, TOK_A)
    await notify.emit("quiz.published", [me], QUIZ)
    assert fake_expo_push.messages == []        # scheduled, not yet sent
    await push.drain()
    assert fake_expo_push.tokens == [TOK_A]


async def test_access_token_header_when_configured(shino_class, fake_expo_push, monkeypatch):
    monkeypatch.setattr(settings, "EXPO_ACCESS_TOKEN", "expo-secret")
    me = shino_class.student_user_ids[0]
    await register(shino_class, me, TOK_A)
    await emit("quiz.published", [me], QUIZ)
    assert len(fake_expo_push.requests) == 1
    assert fake_expo_push.requests[0].headers["Authorization"] == "Bearer expo-secret"


async def test_no_authorization_header_without_access_token(shino_class, fake_expo_push, monkeypatch):
    monkeypatch.setattr(settings, "EXPO_ACCESS_TOKEN", "")
    me = shino_class.student_user_ids[0]
    await register(shino_class, me, TOK_A)
    await emit("quiz.published", [me], QUIZ)
    assert "Authorization" not in fake_expo_push.requests[0].headers


async def test_push_disabled_sends_nothing(shino_class, fake_expo_push, monkeypatch):
    monkeypatch.setattr(settings, "PUSH_ENABLED", False)
    me = shino_class.student_user_ids[0]
    await register(shino_class, me, TOK_A)
    await emit("quiz.published", [me], QUIZ)
    assert fake_expo_push.messages == []
