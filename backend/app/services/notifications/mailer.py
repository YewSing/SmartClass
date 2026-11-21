"""Email for urgent and important notifications (FR-211) — S14.

`store.deliver` calls `schedule(ids)` after its commit. The send runs in a background task (stdlib
`smtplib` in a worker thread), so a slow or unreachable mail server never delays or fails the
request that raised the event. Only urgent and important notifications are emailed, to the
recipient's registered address (`users.email`); general ones never are. Email is off while
`SMTP_HOST` is empty.

Temporary failures (connection lost, timeouts, 4xx replies) are retried at most
`EMAIL_MAX_RETRIES` times per send, with a doubling delay; what is still unsent after that is
logged and dropped. A permanent rejection of one recipient (5xx) drops only that message; a login
failure stops the send. Logs carry counts and exception class names only: never an address, the
SMTP password or the message text.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from collections.abc import Iterable
from email.message import EmailMessage
from email.utils import make_msgid

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.notification import Notification
from app.models.user import User

log = logging.getLogger(__name__)

EMAILED_PRIORITIES = ("urgent", "important")

_tasks: set[asyncio.Task] = set()


class _StopSending(Exception):
    """A failure no retry can fix (bad login, bad sender)."""


def enabled() -> bool:
    return bool(settings.SMTP_HOST.strip())


def schedule(notification_ids: Iterable[int]) -> None:
    """Start emailing these committed notifications in the background. Never raises."""
    ids = sorted(set(notification_ids))
    if not ids or not enabled():
        return
    try:
        task = asyncio.get_running_loop().create_task(send(ids))
    except RuntimeError:          # no running loop (sync caller)
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    """Wait for every scheduled email (tests, shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


def _one_line(text: str) -> str:
    return " ".join((text or "").split())     # no CR/LF in headers (header injection)


def _build(n: Notification, to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    prefix = "[SmartClass] Urgent: " if n.priority == "urgent" else "[SmartClass] "
    msg["Subject"] = _one_line(prefix + n.title)
    msg["Message-ID"] = make_msgid(domain="smartclass.local")
    body = [n.message, ""]
    base = settings.EMAIL_LINK_BASE_URL.strip().rstrip("/")
    if base and n.link:
        body.append(f"Open it in SmartClass: {base}{n.link}")
    else:
        body.append("Open the SmartClass app to see it.")
    body += ["", "You get this email because it is an urgent or important SmartClass notification."]
    msg.set_content("\n".join(body))
    return msg


async def _messages(ids: list[int]) -> list[EmailMessage]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Notification, User.email)
            .join(User, User.id == Notification.user_id)
            .where(Notification.id.in_(ids),
                   Notification.priority.in_(EMAILED_PRIORITIES),
                   User.status == "active")
            .order_by(Notification.id)
        )).all()
    return [_build(n, email.strip()) for n, email in rows if email and "@" in email]


def _deliver(messages: list[EmailMessage]) -> tuple[int, int, Exception | None]:
    """Send in order over one connection until the first temporary failure.

    Returns (handled, rejected, error): `handled` messages are done (sent or permanently
    rejected, `rejected` of them rejected); `error` is the temporary failure that stopped it."""
    handled = rejected = 0
    security = settings.SMTP_SECURITY.strip().lower()
    timeout = settings.SMTP_TIMEOUT_SECONDS
    try:
        if security == "ssl":
            conn = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout,
                                    context=ssl.create_default_context())
        else:
            conn = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
        with conn:
            if security == "starttls":
                conn.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME:
                try:
                    conn.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                except smtplib.SMTPAuthenticationError as exc:
                    raise _StopSending("login refused") from exc
            for msg in messages:
                try:
                    conn.send_message(msg)
                except smtplib.SMTPRecipientsRefused as exc:
                    codes = [code for code, _ in exc.recipients.values()]
                    if any(code < 500 for code in codes):
                        raise smtplib.SMTPException("recipient temporarily refused") from exc
                    rejected += 1
                except smtplib.SMTPSenderRefused as exc:
                    raise _StopSending("sender refused") from exc
                except smtplib.SMTPResponseException as exc:
                    if exc.smtp_code < 500:
                        raise
                    rejected += 1
                handled += 1
    except _StopSending:
        raise
    except (smtplib.SMTPException, OSError) as exc:
        return handled, rejected, exc
    return handled, rejected, None


async def send(notification_ids: Iterable[int]) -> int:
    """Email the urgent/important ones of these notifications. Returns the number accepted by
    the mail server. Never raises."""
    ids = sorted(set(notification_ids))
    sent = 0
    try:
        if not ids or not enabled():
            return 0
        pending = await _messages(ids)
        retries = 0
        while pending:
            handled, rejected, error = await asyncio.to_thread(_deliver, pending)
            sent += handled - rejected
            if rejected:
                log.warning("email: %d messages rejected by the mail server", rejected)
            pending = pending[handled:]
            if error is None:
                break
            if retries >= settings.EMAIL_MAX_RETRIES:
                log.warning("email: %d messages not sent after %d retries (%s)",
                            len(pending), retries, error.__class__.__name__)
                break
            delay = settings.EMAIL_RETRY_DELAY_SECONDS * (2 ** retries)
            retries += 1
            log.info("email: retry %d for %d messages in %.1fs (%s)",
                     retries, len(pending), delay, error.__class__.__name__)
            await asyncio.sleep(delay)
        return sent
    except _StopSending as exc:
        log.warning("email: stopped, %s (check the SMTP settings)", exc)
        return sent
    except Exception as exc:     # email must never fail the event that was stored
        log.warning("email failed: %s", exc.__class__.__name__)
        return sent
