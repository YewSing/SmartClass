"""S30: interaction session tied to the M3 class session (FR-501, FR-502, NFR-04).

The class session is started and ended through M3's own services (`shino_class` uses
`session_schedule.start_now`; `end_class` uses `session_service.close_session`), never by M5.
"""
import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.interaction import InteractionSession
from app.models.session import AttendanceSession
from app.models.user import User
from app.services import session_service
from app.services.interaction import sessions

pytestmark = pytest.mark.db


async def end_class(session_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await session_service.close_session(session_id, db)
        await db.commit()


async def interaction_row(session_id: int) -> InteractionSession | None:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(InteractionSession)
                               .where(InteractionSession.attendance_session_id == session_id))


async def audit_actions(session_id: int) -> list[str]:
    async with AsyncSessionLocal() as db:
        rows = await db.scalars(select(AuditLog.action).where(
            AuditLog.target_type == "attendance_session", AuditLog.target_id == str(session_id),
            AuditLog.action.like("INTERACTION_%")).order_by(AuditLog.id))
        return list(rows)


async def get(c, user_id, role):
    async with c.client(user_id, role) as api:
        return await api.get(f"/interaction/{c.session_id}")


async def post(c, user_id, role, action):
    async with c.client(user_id, role) as api:
        return await api.post(f"/lecturer/interaction/{c.session_id}/{action}")


@pytest.fixture
def closed_events(monkeypatch):
    """Record `on_closed` calls together with what the DB showed at that moment."""
    seen: list[tuple[int, str | None]] = []

    async def listener(attendance_session_id: int) -> None:
        row = await interaction_row(attendance_session_id)
        seen.append((attendance_session_id, row.status if row else None))

    monkeypatch.setattr(sessions, "on_closed", [listener])
    return seen


async def require_open(session_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await sessions.require_open(db, session_id)
        await db.rollback()


# ── lifecycle ────────────────────────────────────────────────────────────────

async def test_running_class_is_open_for_lecturer_and_students(shino_class):
    c = shino_class
    r = await get(c, c.lecturer_user_id, "lecturer")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "open" and body["closed_reason"] is None
    assert body["role"] == "lecturer" and body["class_status"] == "open"
    assert body["course_code"] == "SH101" and body["occurrence_id"] == c.occurrence_id
    assert body["opened_at"] is not None and body["closed_at"] is None

    for uid in c.student_user_ids:
        r = await get(c, uid, "student")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "open" and r.json()["role"] == "student"

    row = await interaction_row(c.session_id)
    assert row is not None and row.status == "open"        # joining created exactly one row
    async with AsyncSessionLocal() as db:
        n = await db.scalar(select(func.count()).select_from(InteractionSession))
    assert n == 1
    await require_open(c.session_id)                      # writes are allowed


async def test_lecturer_closes_early_and_reopens(shino_class, closed_events):
    c = shino_class
    r = await post(c, c.lecturer_user_id, "lecturer", "close")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed" and r.json()["closed_reason"] == "lecturer"
    assert r.json()["class_status"] == "open"             # the class keeps running
    assert closed_events == [(c.session_id, "closed")]    # told after the commit

    async with AsyncSessionLocal() as db:
        assert (await db.get(AttendanceSession, c.session_id)).status == "open"

    r = await get(c, c.student_user_ids[0], "student")
    assert r.json()["status"] == "closed" and r.json()["closed_reason"] == "lecturer"
    with pytest.raises(HTTPException) as exc:
        await require_open(c.session_id)
    assert exc.value.status_code == 409

    # closing twice changes nothing
    r = await post(c, c.lecturer_user_id, "lecturer", "close")
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert closed_events == [(c.session_id, "closed")]

    r = await post(c, c.lecturer_user_id, "lecturer", "open")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "open" and r.json()["closed_reason"] is None
    await require_open(c.session_id)
    r = await post(c, c.lecturer_user_id, "lecturer", "open")   # idempotent
    assert r.status_code == 200 and r.json()["status"] == "open"

    assert await audit_actions(c.session_id) == ["INTERACTION_CLOSED", "INTERACTION_OPENED"]


async def test_ending_the_class_closes_interaction_at_once(shino_class, closed_events):
    c = shino_class
    assert (await get(c, c.lecturer_user_id, "lecturer")).json()["status"] == "open"

    await end_class(c.session_id)        # M3 ends the class; M5 code is not involved

    # Treated as closed immediately, before any sweep has run.
    row = await interaction_row(c.session_id)
    assert row.status == "open"          # the row hasn't been swept yet...
    for uid, role in [(c.lecturer_user_id, "lecturer"), (c.student_user_ids[0], "student")]:
        body = (await get(c, uid, role)).json()
        assert body["status"] == "closed" and body["closed_reason"] == "class_ended"   # ...but it's closed
        assert body["class_status"] == "closed" and body["closed_at"] is not None
    with pytest.raises(HTTPException) as exc:
        await require_open(c.session_id)
    assert exc.value.status_code == 409

    r = await post(c, c.lecturer_user_id, "lecturer", "open")
    assert r.status_code == 409                                    # can't reopen after class
    r = await post(c, c.lecturer_user_id, "lecturer", "close")
    assert r.status_code == 200 and r.json()["closed_reason"] == "class_ended"
    assert closed_events == []

    # The sweep writes it down and tells listeners once.
    assert await sessions.sweep() == [c.session_id]
    row = await interaction_row(c.session_id)
    assert row.status == "closed" and row.closed_reason == "class_ended" and row.closed_at is not None
    assert closed_events == [(c.session_id, "closed")]
    assert await sessions.sweep() == []
    assert closed_events == [(c.session_id, "closed")]


async def test_class_ended_after_lecturer_close_keeps_lecturer_reason(shino_class, closed_events):
    c = shino_class
    await post(c, c.lecturer_user_id, "lecturer", "close")
    await end_class(c.session_id)
    assert await sessions.sweep() == []               # nothing open to close
    body = (await get(c, c.student_user_ids[0], "student")).json()
    assert body["status"] == "closed" and body["class_status"] == "closed"
    assert body["closed_reason"] == "lecturer"
    row = await interaction_row(c.session_id)
    assert row.status == "closed" and row.closed_reason == "lecturer"


async def test_sweep_leaves_running_classes_alone(shino_class, closed_events):
    c = shino_class
    await get(c, c.lecturer_user_id, "lecturer")
    assert await sessions.sweep() == []
    assert (await interaction_row(c.session_id)).status == "open"
    assert closed_events == []


async def test_class_not_started_is_closed(shino_class):
    c = shino_class
    async with AsyncSessionLocal() as db:   # a scheduled class that hasn't begun yet
        await db.execute(update(AttendanceSession).where(AttendanceSession.id == c.session_id)
                         .values(status="scheduled"))
        await db.commit()
    body = (await get(c, c.student_user_ids[0], "student")).json()
    assert body["status"] == "closed" and body["closed_reason"] == "not_started"
    assert await interaction_row(c.session_id) is None     # joining a closed class creates nothing
    assert (await post(c, c.lecturer_user_id, "lecturer", "open")).status_code == 409
    with pytest.raises(HTTPException):
        await require_open(c.session_id)


@pytest.mark.parametrize("status", ["needs_confirmation", "cancelled"])
async def test_other_non_open_class_states_close_it(shino_class, closed_events, status):
    c = shino_class
    await get(c, c.lecturer_user_id, "lecturer")
    async with AsyncSessionLocal() as db:
        await db.execute(update(AttendanceSession).where(AttendanceSession.id == c.session_id)
                         .values(status=status))
        await db.commit()
    body = (await get(c, c.lecturer_user_id, "lecturer")).json()
    assert body["status"] == "closed" and body["closed_reason"] == "class_ended"
    assert await sessions.sweep() == [c.session_id]


# ── the row lock: a write and M3's close can't interleave ────────────────────

async def test_write_check_holds_off_class_close(shino_class):
    c = shino_class
    async with AsyncSessionLocal() as writer:
        await sessions.require_open(writer, c.session_id)    # a write is in progress

        async with AsyncSessionLocal() as m3:
            await m3.execute(text("SET LOCAL lock_timeout = '300ms'"))
            with pytest.raises(DBAPIError):                  # M3's close has to wait
                await session_service.close_session(c.session_id, m3)
            await m3.rollback()
        await writer.commit()

    await end_class(c.session_id)                            # once the write is done it goes through
    with pytest.raises(HTTPException):
        await require_open(c.session_id)


async def test_close_waiting_on_a_write_lands_after_it(shino_class):
    c = shino_class
    async with AsyncSessionLocal() as writer:
        await sessions.require_open(writer, c.session_id)
        closing = asyncio.create_task(end_class(c.session_id))
        await asyncio.sleep(0.3)
        assert not closing.done()                            # blocked by the write's lock
        await writer.commit()
    await asyncio.wait_for(closing, timeout=5)
    with pytest.raises(HTTPException):
        await require_open(c.session_id)


async def test_lecturer_close_and_write_check_conflict(shino_class):
    c = shino_class
    lecturer = await _user(c.lecturer_user_id)
    async with AsyncSessionLocal() as writer:
        await sessions.require_open(writer, c.session_id)
        async with AsyncSessionLocal() as lec:
            await lec.execute(text("SET LOCAL lock_timeout = '300ms'"))
            with pytest.raises(DBAPIError):
                await sessions.close_interaction(lec, lecturer, c.session_id)
            await lec.rollback()
        await writer.commit()


async def _user(user_id: int) -> User:
    async with AsyncSessionLocal() as db:
        return await db.get(User, user_id)


# ── access (FR-502, NFR-04) ──────────────────────────────────────────────────

async def test_access_matrix(shino_class):
    c = shino_class
    assert (await get(c, c.outsider_user_id, "student")).status_code == 403
    assert (await get(c, c.other_lecturer_user_id, "lecturer")).status_code == 403
    for action in ("open", "close"):
        assert (await post(c, c.other_lecturer_user_id, "lecturer", action)).status_code == 403
        assert (await post(c, c.student_user_ids[0], "student", action)).status_code == 403
        assert (await post(c, c.outsider_user_id, "student", action)).status_code == 403

    async with c.client() as api:                     # no token
        assert (await api.get(f"/interaction/{c.session_id}")).status_code in (401, 403)

    async with c.client(c.lecturer_user_id, "lecturer") as api:   # unknown id looks the same as forbidden
        assert (await api.get("/interaction/999999")).status_code == 403
        assert (await api.post("/lecturer/interaction/999999/close")).status_code == 403

    # nothing was created or audited by the refused calls
    assert await interaction_row(c.session_id) is None
    assert await audit_actions(c.session_id) == []


async def test_admin_cannot_join(shino_class):
    c = shino_class
    async with AsyncSessionLocal() as db:
        admin = User(email="shino.admin@um.edu.my", password_hash="x", role="admin", name="Admin",
                     status="active")
        db.add(admin)
        await db.commit()
    assert (await get(c, admin.id, "admin")).status_code == 403


async def test_inactive_enrolled_student_is_refused(shino_class):
    c = shino_class
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == c.student_user_ids[1]).values(status="inactive"))
        await db.commit()
    assert (await get(c, c.student_user_ids[1], "student")).status_code == 401
    assert (await get(c, c.student_user_ids[0], "student")).status_code == 200


async def test_other_class_session_is_not_reachable(shino_class):
    """A student enrolled in SH101 can't join a class session of SH202."""
    from app.models.class_ import ClassOccurrence
    from app.models.user import Lecturer
    from app.services import session_schedule

    c = shino_class
    async with AsyncSessionLocal() as db:
        occ = await db.get(ClassOccurrence, c.other_occurrence_id)
        lec = await db.get(Lecturer, c.other_lecturer_id)
        other = await session_schedule.start_now(db, occ, lec, session_schedule.clock(), duration_minutes=60)
        await db.commit()
        other_id = other.id
    async with c.client(c.student_user_ids[0], "student") as api:
        assert (await api.get(f"/interaction/{other_id}")).status_code == 403
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        assert (await api.get(f"/interaction/{other_id}")).status_code == 403
    async with c.client(c.other_lecturer_user_id, "lecturer") as api:
        r = await api.get(f"/interaction/{other_id}")
        assert r.status_code == 200 and r.json()["course_code"] == "SH202"


# ── background loop ──────────────────────────────────────────────────────────

async def test_sweep_loop_runs_until_cancelled_and_survives_errors(monkeypatch):
    calls = {"sweep": 0, "sleep": []}

    async def fake_sweep():
        calls["sweep"] += 1
        if calls["sweep"] == 1:
            raise RuntimeError("db down")
        return []

    async def fake_sleep(seconds):
        calls["sleep"].append(seconds)
        if len(calls["sleep"]) >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(settings, "INTERACTION_SWEEP_SECONDS", 10)
    monkeypatch.setattr(sessions, "sweep", fake_sweep)
    monkeypatch.setattr(sessions, "_sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await sessions.interaction_sweep_loop()
    assert calls["sweep"] == 2 and calls["sleep"] == [10, 10]   # well under 30 s between sweeps


async def test_sweep_loop_off_when_interval_not_positive(monkeypatch):
    called = []

    async def fake_sweep():
        called.append(1)
        return []

    monkeypatch.setattr(settings, "INTERACTION_SWEEP_SECONDS", 0)
    monkeypatch.setattr(sessions, "sweep", fake_sweep)
    await sessions.interaction_sweep_loop()
    assert called == []


def test_default_sweep_interval_closes_within_30_seconds():
    assert 0 < settings.INTERACTION_SWEEP_SECONDS <= 30
