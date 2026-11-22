"""
Test data for the notification centre E2E flows (plan-shino.md S19).

    python scripts/e2e_notifications.py seed  --user devlecturer@um.edu.my [--older 22]
    python scripts/e2e_notifications.py send  --user devlecturer@um.edu.my --api http://127.0.0.1:8001
    python scripts/e2e_notifications.py actor --user student4@example.com --api http://127.0.0.1:8000
    python scripts/e2e_notifications.py clean --user devlecturer@um.edu.my

`seed` gives the user three unread notifications (urgent, important with a link, general) and
`--older` read ones from earlier days (for "load more"). The user's own unread notifications are
marked read for the run, so the bell starts at 3, and their notification preferences are saved.

`send` asks the running API for a test notification as the user (`POST /notifications/test`), so it
arrives live over the websocket like a real one. `actor` waits until the user has read all seeded
notifications ("Mark all as read"), then sends one. Tokens stay in memory.

`clean` deletes the seeded and test notifications, marks the user's own ones unread again and puts
their preferences back. Writes rows directly (no push or email is sent). Run from backend/ against
the dev database (DATABASE_URL in .env).
"""
import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
import time
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import delete, func, select, update

from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.core.timezone import now_myt
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.user import User

SUBJECT = "e2e-s19"           # subject_key prefix of seeded rows
DEADLINE_SECONDS = 300


def _marker(email: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", email)
    return os.path.join(tempfile.gettempdir(), f"smartclass-e2e-notifications-{safe}.json")


async def _user(db, email: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        sys.exit(f"No SmartClass user with email {email}. Sign them in once first.")
    return user


def _seed_rows(user: User, older: int) -> list[Notification]:
    now = now_myt()
    lecturer = user.role in ("lecturer", "admin")
    items = [
        ("urgent", "E2E urgent notice", "Something needs your attention now.", None),
        ("important", "E2E face enrolment to review" if lecturer else "E2E room change",
         "A student's face enrolment needs your review." if lecturer else "Today's class moves to DK2.",
         "/face-verification" if lecturer else "/profile/face"),
        ("general", "E2E general update", "A small update about your class.", None),
    ]
    rows = [
        Notification(user_id=user.id, event="announcement.posted", priority=p, title=t, message=m, link=link,
                     subject_key=f"{SUBJECT}:new:{i}", created_at=now - timedelta(minutes=5 * (len(items) - i)))
        for i, (p, t, m, link) in enumerate(items)
    ]
    rows += [
        Notification(user_id=user.id, event="announcement.posted", priority="general",
                     title=f"E2E old {i}", message=f"An older notification ({i}).", link=None,
                     subject_key=f"{SUBJECT}:old:{i}", created_at=now - timedelta(days=2, minutes=older - i),
                     read_at=now - timedelta(days=1))
        for i in range(older)
    ]
    return rows


async def seed(email: str, older: int) -> None:
    await clean(email, quiet=True)
    async with AsyncSessionLocal() as db:
        user = await _user(db, email)
        own_unread = list((await db.scalars(select(Notification.id).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)))).all())
        prefs = await db.get(NotificationPreference, user.id)
        saved_prefs = None if prefs is None else {"push_general": prefs.push_general,
                                                   "email_general": prefs.email_general}
        if own_unread:
            await db.execute(update(Notification).where(Notification.id.in_(own_unread))
                             .values(read_at=now_myt()))
        if prefs is not None:
            await db.delete(prefs)          # the flow starts from the defaults
        db.add_all(_seed_rows(user, older))
        user_id, role = user.id, user.role
        await db.commit()
    with open(_marker(email), "w") as f:
        json.dump({"user_id": user_id, "role": role, "own_unread": own_unread, "prefs": saved_prefs}, f)
    print(f"seeded 3 unread + {older} read notifications for {email}; {len(own_unread)} own marked read")


async def clean(email: str, quiet: bool = False) -> None:
    marker = {}
    if os.path.exists(_marker(email)):
        try:
            with open(_marker(email)) as f:
                marker = json.load(f)
        except (OSError, ValueError):
            marker = {}
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            return
        removed = (await db.execute(delete(Notification).where(
            Notification.user_id == user.id,
            (Notification.subject_key.like(f"{SUBJECT}:%")) | (Notification.event == "notification.test"),
        ))).rowcount or 0
        if marker.get("own_unread"):
            await db.execute(update(Notification).where(Notification.id.in_(marker["own_unread"]))
                             .values(read_at=None))
        if "prefs" in marker:
            await db.execute(delete(NotificationPreference).where(NotificationPreference.user_id == user.id))
            if marker["prefs"] is not None:
                db.add(NotificationPreference(user_id=user.id, **marker["prefs"]))
        await db.commit()
    if os.path.exists(_marker(email)):
        os.remove(_marker(email))
    if not quiet:
        print(f"removed {removed} E2E notifications for {email}; own notifications and preferences restored")


async def _token(email: str) -> str:
    async with AsyncSessionLocal() as db:
        user = await _user(db, email)
        return create_access_token(user.id, user.role)


def _send(api: str, token: str) -> None:
    res = httpx.post(f"{api}/notifications/test", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if res.status_code != 200:
        sys.exit(f"POST /notifications/test failed: {res.status_code} {res.text}")
    print(f"test notification sent: {res.json()}")


async def send(email: str, api: str) -> None:
    _send(api, await _token(email))


async def actor(email: str, api: str) -> None:
    token = await _token(email)
    deadline = time.monotonic() + DEADLINE_SECONDS
    while time.monotonic() < deadline:
        async with AsyncSessionLocal() as db:
            unread = await db.scalar(select(func.count()).select_from(Notification).join(
                User, User.id == Notification.user_id).where(
                User.email == email, Notification.read_at.is_(None),
                Notification.subject_key.like(f"{SUBJECT}:%")))
        if unread == 0:
            await asyncio.sleep(4)          # the phone shows "All caught up" first
            _send(api, token)
            return
        await asyncio.sleep(1)
    sys.exit(f"Timed out after {DEADLINE_SECONDS}s waiting for the notifications to be read.")


async def _main(args) -> None:
    try:
        if args.action == "seed":
            await seed(args.user, args.older)
        elif args.action == "send":
            await send(args.user, args.api)
        elif args.action == "actor":
            await actor(args.user, args.api)
        else:
            await clean(args.user)
    finally:
        await engine.dispose()   # before the loop closes, or Windows prints "Event loop is closed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("action", choices=["seed", "send", "actor", "clean"])
    parser.add_argument("--user", required=True, help="the user's SmartClass email")
    parser.add_argument("--older", type=int, default=0, help="read notifications from earlier days")
    parser.add_argument("--api", default=os.environ.get("E2E_API_URL", "http://127.0.0.1:8000"))
    asyncio.run(_main(parser.parse_args()))
