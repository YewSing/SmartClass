"""T12: admin account management (FR-103, FR-108, FR-118).

Deactivate/reactivate, create admin, and the rule that a deactivated account is locked out of
local login, Moodle login, token refresh and any token it already holds.
"""
import json

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.user import User
from app.services import moodle_auth

pytestmark = pytest.mark.db

STUDENT_EMAIL, STUDENT_PASSWORD = "student.test@siswa.um.edu.my", "Student@1234"  # conftest `users`


async def _login(client, email=STUDENT_EMAIL, password=STUDENT_PASSWORD):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def _audit(db_session, action):
    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)
    )).scalars().all()
    return rows


async def _status(db_session, user_id):
    return await db_session.scalar(
        select(User.status).where(User.id == user_id).execution_options(populate_existing=True))


# ── deactivated accounts are locked out ───────────────────────────────────────

async def test_deactivated_user_cannot_log_in_refresh_or_use_old_token(admin_client, client, users):
    tokens = (await _login(client)).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.get("/auth/me", headers=headers)).status_code == 200

    resp = await admin_client.delete(f"/admin/users/{users['student'].id}")
    assert resp.status_code == 204, resp.text

    assert (await _login(client)).status_code == 401
    assert (await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).status_code == 401
    assert (await client.get("/auth/me", headers=headers)).status_code == 401


async def test_deactivated_moodle_user_cannot_sign_in_through_moodle(admin_client, client, db_session, monkeypatch):
    user = User(email="ali@siswa.um.edu.my", password_hash=None, role="student", name="Ali",
                status="active", moodle_user_id=42)
    db_session.add(user)
    await db_session.commit()

    async def fake_authenticate(username, password):
        return moodle_auth.MoodleProfile(user_id=42, username="23004001", fullname="Ali", email="ali@siswa.um.edu.my",
                                         idnumber="23004001", department=None, teaches=False)
    monkeypatch.setattr(moodle_auth, "authenticate", fake_authenticate)

    login = {"username": "23004001", "password": "pw"}
    assert (await client.post("/auth/moodle-login", json=login)).status_code == 200

    assert (await admin_client.delete(f"/admin/users/{user.id}")).status_code == 204
    resp = await client.post("/auth/moodle-login", json=login)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"  # same generic message as wrong password
    assert await _status(db_session, user.id) == "inactive"  # Moodle login doesn't reactivate it

    assert (await admin_client.post(f"/admin/users/{user.id}/reactivate")).status_code == 204
    assert (await client.post("/auth/moodle-login", json=login)).status_code == 200


async def test_reactivated_user_can_log_in_again(admin_client, client, users):
    await admin_client.delete(f"/admin/users/{users['student'].id}")
    assert (await _login(client)).status_code == 401
    resp = await admin_client.post(f"/admin/users/{users['student'].id}/reactivate")
    assert resp.status_code == 204, resp.text
    assert (await _login(client)).status_code == 200


# ── an admin can't lock themselves out ────────────────────────────────────────

async def test_admin_cannot_deactivate_themselves(admin_client, db_session, users):
    resp = await admin_client.delete(f"/admin/users/{users['admin'].id}")
    assert resp.status_code == 400
    assert await _status(db_session, users["admin"].id) == "active"
    assert await _audit(db_session, "USER_DEACTIVATE") == []


async def test_admin_cannot_deactivate_themselves_through_update(admin_client, db_session, users):
    resp = await admin_client.put(f"/admin/users/{users['admin'].id}", json={"status": "inactive"})
    assert resp.status_code == 400
    assert await _status(db_session, users["admin"].id) == "active"


async def test_update_rejects_unknown_status(admin_client, db_session, users):
    resp = await admin_client.put(f"/admin/users/{users['student'].id}", json={"status": "banned"})
    assert resp.status_code == 422
    assert await _status(db_session, users["student"].id) == "active"


# ── every change is audited ───────────────────────────────────────────────────

async def test_deactivate_and_reactivate_write_audit_entries(admin_client, db_session, users):
    sid = users["student"].id
    await admin_client.delete(f"/admin/users/{sid}")
    await admin_client.post(f"/admin/users/{sid}/reactivate")

    (deact,) = await _audit(db_session, "USER_DEACTIVATE")
    (react,) = await _audit(db_session, "USER_REACTIVATE")
    for row in (deact, react):
        assert row.actor_id == users["admin"].id
        assert (row.target_type, row.target_id) == ("user", str(sid))
    assert json.loads(deact.old_val) == {"status": "active"}
    assert json.loads(deact.new_val) == {"status": "inactive"}
    assert json.loads(react.old_val) == {"status": "inactive"}
    assert json.loads(react.new_val) == {"status": "active"}


async def test_status_change_through_update_is_audited_as_deactivation(admin_client, db_session, users):
    sid = users["student"].id
    resp = await admin_client.put(f"/admin/users/{sid}", json={"status": "inactive"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "inactive"
    (row,) = await _audit(db_session, "USER_DEACTIVATE")
    assert row.target_id == str(sid)
    assert await _audit(db_session, "USER_UPDATE") == []  # nothing else changed


async def test_repeating_a_deactivation_writes_no_second_entry(admin_client, db_session, users):
    sid = users["student"].id
    assert (await admin_client.delete(f"/admin/users/{sid}")).status_code == 204
    assert (await admin_client.delete(f"/admin/users/{sid}")).status_code == 204
    assert len(await _audit(db_session, "USER_DEACTIVATE")) == 1


async def test_unknown_user_gives_404(admin_client, users):
    assert (await admin_client.delete("/admin/users/999999")).status_code == 404
    assert (await admin_client.post("/admin/users/999999/reactivate")).status_code == 404


# ── create admin ──────────────────────────────────────────────────────────────

async def test_admin_creates_another_admin_who_can_log_in_locally(admin_client, client, db_session, users):
    resp = await admin_client.post("/admin/users", json={
        "email": "admin2@um.edu.my", "password": "Admin2@1234", "name": "Second Admin", "role": "admin"})
    assert resp.status_code == 201, resp.text
    new_id = resp.json()["id"]
    assert resp.json()["role"] == "admin"

    row = (await db_session.execute(select(User).where(User.id == new_id))).scalar_one()
    assert row.password_hash and row.password_hash.startswith("$2")  # bcrypt, never the plain password (NFR-05)

    login = await _login(client, email="admin2@um.edu.my", password="Admin2@1234")
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "admin"

    (entry,) = await _audit(db_session, "USER_CREATE")
    assert entry.actor_id == users["admin"].id
    assert json.loads(entry.new_val) == {"email": "admin2@um.edu.my", "role": "admin"}
    assert "Admin2@1234" not in (entry.new_val or "")


# ── only admins ───────────────────────────────────────────────────────────────

async def test_non_admins_cannot_manage_accounts(lecturer_client, student_client, db_session, users):
    sid = users["student"].id
    for c in (lecturer_client, student_client):
        assert (await c.delete(f"/admin/users/{sid}")).status_code == 403
        assert (await c.post(f"/admin/users/{sid}/reactivate")).status_code == 403
        assert (await c.put(f"/admin/users/{sid}", json={"status": "inactive"})).status_code == 403
        resp = await c.post("/admin/users", json={
            "email": "x@um.edu.my", "password": "X@123456", "name": "X", "role": "admin"})
        assert resp.status_code == 403
    assert await _status(db_session, sid) == "active"
    assert (await db_session.execute(select(User).where(User.email == "x@um.edu.my"))).first() is None
