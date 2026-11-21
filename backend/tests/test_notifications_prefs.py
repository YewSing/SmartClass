"""S15: notification preferences (FR-214) and retention (FR-218).

Push goes to the respx fake (`fake_expo_push`), email to the in-memory `fake_smtp` sink; the
clock is monkeypatched. Nothing leaves the process."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.notification import Notification
from app.models.user import User
from app.services import notify
from app.services.notifications import mailer, push, retention, store

pytestmark = pytest.mark.db

URL = "/me/notification-preferences"
TOK = "ExponentPushToken[pppppppppppppppppppppp]"
DEFAULTS = {"push": {"urgent": True, "important": True, "general": False},
            "email": {"urgent": True, "important": True, "general": False}}
QUIZ = {"quiz_id": 7, "quiz_title": "Week 3 quiz", "course_code": "SH101"}


@pytest.fixture
def channels_on(monkeypatch, fake_smtp, fake_expo_push):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test.local")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(settings, "EMAIL_RETRY_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(settings, "PUSH_ENABLED", True)
    return fake_smtp, fake_expo_push


async def emit(event, user_ids, payload):
    await notify.emit(event, user_ids, payload)
    await push.drain()
    await mailer.drain()


def general_payload(sc, n=1):
    return {"attendance_session_id": sc.session_id, "course_code": "SH101", "poll_id": n}


async def put(sc, user_id, body, role="student"):
    async with sc.client(user_id, role) as c:
        return await c.put(URL, json=body)


async def register(sc, user_id):
    async with sc.client(user_id, "student") as c:
        assert (await c.post("/me/push-tokens", json={"token": TOK, "platform": "android"})).status_code == 201


# ── GET / PUT ─────────────────────────────────────────────────────────────────

async def test_defaults_general_off_and_urgent_important_on(shino_class):
    async with shino_class.client(shino_class.student_user_ids[0], "student") as c:
        r = await c.get(URL)
    assert r.status_code == 200 and r.json() == DEFAULTS


async def test_put_general_is_saved_per_user(shino_class):
    a, b = shino_class.student_user_ids[:2]
    r = await put(shino_class, a, {"push": {"general": True}, "email": {"general": True}})
    assert r.status_code == 200
    assert r.json()["push"]["general"] is True and r.json()["email"]["general"] is True
    async with shino_class.client(a, "student") as c:
        assert (await c.get(URL)).json()["push"] == {"urgent": True, "important": True, "general": True}
    async with shino_class.client(b, "student") as c:
        assert (await c.get(URL)).json() == DEFAULTS       # other users untouched


async def test_partial_put_keeps_the_other_channel(shino_class):
    me = shino_class.lecturer_user_id
    await put(shino_class, me, {"push": {"general": True}, "email": {"general": True}}, role="lecturer")
    r = await put(shino_class, me, {"email": {"general": False}}, role="lecturer")
    assert r.json()["push"]["general"] is True and r.json()["email"]["general"] is False
    r = await put(shino_class, me, {}, role="lecturer")
    assert r.json()["push"]["general"] is True and r.json()["email"]["general"] is False


@pytest.mark.parametrize("body", [
    {"push": {"urgent": False}},
    {"push": {"important": False}},
    {"email": {"urgent": False}},
    {"email": {"important": False, "general": True}},
])
async def test_urgent_and_important_cannot_be_turned_off(shino_class, body):
    me = shino_class.student_user_ids[0]
    r = await put(shino_class, me, body)
    assert r.status_code == 422
    async with shino_class.client(me, "student") as c:
        assert (await c.get(URL)).json() == DEFAULTS      # nothing half-saved


async def test_sending_true_for_urgent_important_is_accepted(shino_class):
    r = await put(shino_class, shino_class.student_user_ids[0],
                  {"push": {"urgent": True, "important": True, "general": True}})
    assert r.status_code == 200 and r.json()["push"]["general"] is True


@pytest.mark.parametrize("body", [
    {"push": {"general": "no"}},
    {"push": {"general": 1}},
    {"sms": {"general": True}},
    {"push": {"general": True, "quiz": False}},
])
async def test_bad_bodies_are_422(shino_class, body):
    assert (await put(shino_class, shino_class.student_user_ids[0], body)).status_code == 422


async def test_preferences_need_sign_in(shino_class):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get(URL)).status_code in (401, 403)      # HTTPBearer: no header -> 403
        assert (await c.put(URL, json={})).status_code in (401, 403)
        bad = {"Authorization": "Bearer not-a-token"}
        assert (await c.get(URL, headers=bad)).status_code == 401


# ── effect on delivery ────────────────────────────────────────────────────────

async def test_general_not_pushed_or_emailed_by_default(shino_class, channels_on):
    smtp, expo = channels_on
    me = shino_class.student_user_ids[0]
    await register(shino_class, me)
    await emit("poll.started", [me], general_payload(shino_class))
    assert expo.messages == [] and smtp.sent == []


async def test_general_push_on_pushes_general_to_that_user_only(shino_class, channels_on):
    smtp, expo = channels_on
    a, b = shino_class.student_user_ids[:2]
    await register(shino_class, a)
    await put(shino_class, a, {"push": {"general": True}})
    await emit("poll.started", [a, b], general_payload(shino_class))
    assert expo.tokens == [TOK]
    assert smtp.sent == []                           # email still off for general


async def test_general_email_on_emails_only_opted_in_user(shino_class, channels_on):
    smtp, expo = channels_on
    a, b = shino_class.student_user_ids[:2]
    await put(shino_class, a, {"email": {"general": True}})
    await emit("poll.started", [a, b], general_payload(shino_class))
    async with AsyncSessionLocal() as db:
        email_a = await db.scalar(select(User.email).where(User.id == a))
    assert [r for m in smtp.sent for r in m.recipients] == [email_a]
    assert expo.messages == []


async def test_turning_general_back_off_stops_it(shino_class, channels_on):
    smtp, expo = channels_on
    me = shino_class.student_user_ids[0]
    await register(shino_class, me)
    await put(shino_class, me, {"push": {"general": True}, "email": {"general": True}})
    await put(shino_class, me, {"push": {"general": False}, "email": {"general": False}})
    await emit("poll.started", [me], general_payload(shino_class))
    assert expo.messages == [] and smtp.sent == []


async def test_urgent_important_still_delivered_with_general_off(shino_class, channels_on):
    smtp, expo = channels_on
    me = shino_class.student_user_ids[0]
    await register(shino_class, me)
    await put(shino_class, me, {"push": {"general": False}, "email": {"general": False}})
    await emit("quiz.published", [me], QUIZ)
    assert expo.tokens == [TOK] and len(smtp.sent) == 1


# ── retention (FR-218) ────────────────────────────────────────────────────────

async def _emit_at(monkeypatch, when: datetime, user_id: int, n: int):
    monkeypatch.setattr(store, "clock", lambda: when)
    await notify.emit("poll.started", [user_id], {"poll_id": n, "course_code": "SH101",
                                                  "attendance_session_id": 1})


async def _count() -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(Notification))


async def test_purge_deletes_only_older_than_retention(shino_class, monkeypatch):
    me = shino_class.student_user_ids[0]
    now = datetime(2026, 11, 22, 3, 0)
    monkeypatch.setattr(settings, "NOTIFICATION_RETENTION_DAYS", 90)
    await _emit_at(monkeypatch, now - timedelta(days=120), me, 1)
    await _emit_at(monkeypatch, now - timedelta(days=90, minutes=1), me, 2)
    await _emit_at(monkeypatch, now - timedelta(days=89, hours=23), me, 3)
    await _emit_at(monkeypatch, now - timedelta(days=1), me, 4)
    # read or unread makes no difference
    async with shino_class.client(me, "student") as c:
        await c.post("/notifications/read-all")
    monkeypatch.setattr(retention, "clock", lambda: now)
    assert await retention.purge() == 2
    async with shino_class.client(me, "student") as c:
        items = (await c.get("/notifications")).json()["items"]
    assert sorted(i["created_at"][:10] for i in items) == ["2026-08-24", "2026-11-21"]


async def test_purge_uses_configured_days(shino_class, monkeypatch):
    me = shino_class.student_user_ids[0]
    now = datetime(2026, 11, 22, 3, 0)
    await _emit_at(monkeypatch, now - timedelta(days=10), me, 1)
    await _emit_at(monkeypatch, now - timedelta(days=3), me, 2)
    monkeypatch.setattr(retention, "clock", lambda: now)
    monkeypatch.setattr(settings, "NOTIFICATION_RETENTION_DAYS", 7)
    assert await retention.purge() == 1
    assert await _count() == 1
    assert await retention.purge() == 0             # idempotent


async def test_default_retention_is_90_days():
    from app.core.config import Settings

    assert Settings.model_fields["NOTIFICATION_RETENTION_DAYS"].default == 90
    assert Settings.model_fields["NOTIFICATION_RETENTION_INTERVAL_SECONDS"].default == 86400


async def test_zero_or_negative_retention_deletes_nothing(shino_class, monkeypatch):
    me = shino_class.student_user_ids[0]
    now = datetime(2026, 11, 22, 3, 0)
    await _emit_at(monkeypatch, now - timedelta(days=400), me, 1)
    monkeypatch.setattr(retention, "clock", lambda: now)
    monkeypatch.setattr(settings, "NOTIFICATION_RETENTION_DAYS", 0)
    assert await retention.purge() == 0
    assert await _count() == 1


async def test_daily_loop_purges_then_sleeps_a_day(shino_class, monkeypatch):
    import asyncio

    me = shino_class.student_user_ids[0]
    now = datetime(2026, 11, 22, 3, 0)
    await _emit_at(monkeypatch, now - timedelta(days=200), me, 1)
    monkeypatch.setattr(retention, "clock", lambda: now)
    monkeypatch.setattr(settings, "NOTIFICATION_RETENTION_DAYS", 90)
    monkeypatch.setattr(settings, "NOTIFICATION_RETENTION_INTERVAL_SECONDS", 86400)
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        raise asyncio.CancelledError

    monkeypatch.setattr(retention, "_sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await retention.retention_loop()
    assert slept == [86400] and await _count() == 0


async def test_loop_survives_a_failed_purge(monkeypatch):
    import asyncio

    monkeypatch.setattr(settings, "NOTIFICATION_RETENTION_INTERVAL_SECONDS", 86400)
    calls = []

    async def boom():
        calls.append(1)
        raise RuntimeError("db down")

    async def fake_sleep(seconds):
        if len(calls) >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(retention, "purge", boom)
    monkeypatch.setattr(retention, "_sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await retention.retention_loop()
    assert len(calls) == 2


async def test_loop_off_when_interval_not_positive(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATION_RETENTION_INTERVAL_SECONDS", 0)
    called = []

    async def spy():
        called.append(1)
        return 0

    monkeypatch.setattr(retention, "purge", spy)
    await retention.retention_loop()
    assert called == []
