"""S14: email for urgent/important notifications (FR-211).

Every SMTP call goes to the in-memory `fake_smtp` sink; nothing leaves the process."""
import logging
import smtplib

import pytest
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.services import notify
from app.services.notifications import mailer

pytestmark = pytest.mark.db

QUIZ = {"quiz_id": 7, "quiz_title": "Week 3 quiz", "course_code": "SH101"}
PASSWORD = "smtp-pass-very-secret"


@pytest.fixture
def smtp_on(monkeypatch, fake_smtp):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test.local")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_SECURITY", "starttls")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "mailer@test.local")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", PASSWORD)
    monkeypatch.setattr(settings, "SMTP_FROM", "SmartClass <no-reply@test.local>")
    monkeypatch.setattr(settings, "EMAIL_MAX_RETRIES", 3)
    monkeypatch.setattr(settings, "EMAIL_RETRY_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(settings, "EMAIL_LINK_BASE_URL", "")
    return fake_smtp


async def email_of(user_id: int) -> str:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.email).where(User.id == user_id))


async def emit(event: str, user_ids, payload) -> None:
    await notify.emit(event, user_ids, payload)
    await mailer.drain()


def recipients(sink) -> list[str]:
    return sorted(r for m in sink.sent for r in m.recipients)


# ── who gets email ────────────────────────────────────────────────────────────

async def test_important_is_emailed_to_each_recipients_address(shino_class, smtp_on):
    a, b = shino_class.student_user_ids[:2]
    await emit("quiz.published", [a, b], QUIZ)
    assert recipients(smtp_on) == sorted([await email_of(a), await email_of(b)])
    mail = smtp_on.sent[0]
    assert mail.subject.startswith("[SmartClass] ") and "Week 3 quiz" in mail.raw
    assert mail.sender == "SmartClass <no-reply@test.local>"
    assert (mail.host, mail.port) == ("smtp.test.local", 587)
    assert mail.used_tls and mail.username == "mailer@test.local"


async def test_urgent_is_emailed_with_urgent_subject(shino_class, smtp_on):
    me = shino_class.lecturer_user_id
    await emit("confusion.spike", [me], {"attendance_session_id": shino_class.session_id,
                                         "course_code": "SH101", "spike_id": 1})
    assert recipients(smtp_on) == [await email_of(me)]
    assert smtp_on.sent[0].subject.startswith("[SmartClass] Urgent: ")


async def test_general_is_never_emailed(shino_class, smtp_on):
    me = shino_class.student_user_ids[0]
    await emit("attendance.recorded", [me], {"session_id": shino_class.session_id,
                                             "course_code": "SH101", "status": "present"})
    await emit("poll.started", [me], {"attendance_session_id": shino_class.session_id,
                                      "course_code": "SH101", "poll_id": 1})
    async with shino_class.client(me, "student") as c:
        assert (await c.get("/notifications")).json()["unread_count"] == 2   # stored, in-app only
    assert smtp_on.attempts == 0 and smtp_on.sent == []


async def test_duplicate_event_is_not_emailed_again(shino_class, smtp_on):
    me = shino_class.student_user_ids[0]
    await emit("quiz.published", [me], QUIZ)
    await emit("quiz.published", [me], QUIZ)      # deduplicated by the store (FR-216)
    assert len(smtp_on.sent) == 1


async def test_inactive_user_is_not_emailed(shino_class, smtp_on):
    a, b = shino_class.student_user_ids[:2]
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == a).values(status="inactive"))
        await db.commit()
    await emit("quiz.published", [a, b], QUIZ)
    assert recipients(smtp_on) == [await email_of(b)]


# ── settings ──────────────────────────────────────────────────────────────────

async def test_off_when_smtp_host_unset(shino_class, fake_smtp, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    me = shino_class.student_user_ids[0]
    await emit("quiz.published", [me], QUIZ)
    assert fake_smtp.attempts == 0
    async with shino_class.client(me, "student") as c:
        assert (await c.get("/notifications")).json()["unread_count"] == 1


async def test_ssl_mode_and_no_login_without_username(shino_class, smtp_on, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_SECURITY", "ssl")
    monkeypatch.setattr(settings, "SMTP_PORT", 465)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "")
    await emit("quiz.published", [shino_class.student_user_ids[0]], QUIZ)
    mail = smtp_on.sent[0]
    assert mail.port == 465 and mail.used_tls and mail.username is None


async def test_plain_mode_does_not_start_tls(shino_class, smtp_on, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_SECURITY", "none")
    await emit("quiz.published", [shino_class.student_user_ids[0]], QUIZ)
    assert smtp_on.sent[0].used_tls is False


async def test_link_included_only_with_base_url(shino_class, smtp_on, monkeypatch):
    a, b = shino_class.student_user_ids[:2]
    await emit("quiz.published", [a], QUIZ)
    assert "http" not in smtp_on.sent[0].raw
    monkeypatch.setattr(settings, "EMAIL_LINK_BASE_URL", "https://smartclass.example/")
    await emit("quiz.published", [b], {**QUIZ, "quiz_id": 8})
    body = smtp_on.sent[1].message.get_content()
    assert "https://smartclass.example/" in body and "//quiz" not in body.replace("https://", "")


async def test_newlines_in_title_cannot_inject_headers(shino_class, smtp_on):
    me = shino_class.student_user_ids[0]
    await emit("quiz.published", [me], {**QUIZ, "title": "Quiz\r\nBcc: victim@evil.example"})
    mail = smtp_on.sent[0]
    assert mail.recipients == [await email_of(me)]
    assert mail.message["Bcc"] is None and "\n" not in mail.subject


# ── background, retries, failures ─────────────────────────────────────────────

async def test_emit_returns_before_the_email_is_sent(shino_class, smtp_on):
    me = shino_class.student_user_ids[0]
    await notify.emit("quiz.published", [me], QUIZ)
    assert smtp_on.sent == []                    # scheduled, not yet sent
    await mailer.drain()
    assert len(smtp_on.sent) == 1


async def test_temporary_failure_is_retried(shino_class, smtp_on):
    a, b = shino_class.student_user_ids[:2]
    smtp_on.fail_next = 2
    await emit("quiz.published", [a, b], QUIZ)
    assert recipients(smtp_on) == sorted([await email_of(a), await email_of(b)])
    assert smtp_on.attempts == 4                  # 2 failed + 2 sent


async def test_retries_stop_after_max_and_are_logged_without_secrets(shino_class, smtp_on, caplog):
    me = shino_class.student_user_ids[0]
    smtp_on.fail_next = 100
    with caplog.at_level(logging.INFO):
        await emit("quiz.published", [me], QUIZ)
    assert smtp_on.attempts == 1 + settings.EMAIL_MAX_RETRIES
    assert smtp_on.sent == []
    assert "email:" in caplog.text and "not sent after 3 retries" in caplog.text
    addr = await email_of(me)
    assert PASSWORD not in caplog.text and addr not in caplog.text
    async with shino_class.client(me, "student") as c:   # the notification itself is kept
        assert (await c.get("/notifications")).json()["unread_count"] == 1


async def test_connection_refused_is_retried_then_dropped(shino_class, smtp_on, monkeypatch, caplog):
    calls = []

    class Down:
        def __init__(self, *a, **k):
            calls.append(1)
            raise ConnectionRefusedError("down")

    monkeypatch.setattr(smtplib, "SMTP", Down)
    with caplog.at_level(logging.WARNING):
        await emit("quiz.published", shino_class.student_user_ids[:2], QUIZ)
    assert len(calls) == 1 + settings.EMAIL_MAX_RETRIES
    assert "ConnectionRefusedError" in caplog.text and PASSWORD not in caplog.text


async def test_rejected_recipient_drops_only_that_message(shino_class, smtp_on, monkeypatch):
    a, b = shino_class.student_user_ids[:2]
    bad = await email_of(a)
    real = smtplib.SMTP

    class Picky(real):
        def send_message(self, msg, *args, **kwargs):
            if msg["To"] == bad:
                raise smtplib.SMTPRecipientsRefused({bad: (550, b"no such user")})
            return super().send_message(msg, *args, **kwargs)

    monkeypatch.setattr(smtplib, "SMTP", Picky)
    await emit("quiz.published", [a, b], QUIZ)
    assert recipients(smtp_on) == [await email_of(b)]


async def test_temporarily_refused_recipient_is_retried(shino_class, smtp_on, monkeypatch):
    me = shino_class.student_user_ids[0]
    addr = await email_of(me)
    real = smtplib.SMTP
    refusals = [1]

    class Greylist(real):
        def send_message(self, msg, *args, **kwargs):
            if refusals:
                refusals.pop()
                raise smtplib.SMTPRecipientsRefused({addr: (451, b"try again later")})
            return super().send_message(msg, *args, **kwargs)

    monkeypatch.setattr(smtplib, "SMTP", Greylist)
    await emit("quiz.published", [me], QUIZ)
    assert recipients(smtp_on) == [addr]


async def test_login_failure_stops_without_retry_or_password_in_logs(shino_class, smtp_on, monkeypatch,
                                                                     caplog):
    real = smtplib.SMTP

    class BadLogin(real):
        def login(self, user, password, *args, **kwargs):
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(smtplib, "SMTP", BadLogin)
    with caplog.at_level(logging.INFO):
        await emit("quiz.published", [shino_class.student_user_ids[0]], QUIZ)
    assert smtp_on.attempts == 0
    assert "check the SMTP settings" in caplog.text and PASSWORD not in caplog.text


async def test_email_failure_does_not_affect_push_or_feed(shino_class, smtp_on, fake_expo_push):
    from app.services.notifications import push

    me = shino_class.student_user_ids[0]
    async with shino_class.client(me, "student") as c:
        await c.post("/me/push-tokens", json={"token": "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaaa]",
                                              "platform": "android"})
    smtp_on.fail_next = 100
    await emit("quiz.published", [me], QUIZ)
    await push.drain()
    assert len(fake_expo_push.messages) == 1
