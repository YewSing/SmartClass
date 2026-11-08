"""Characterisation: current auth behaviour (login / refresh / me), before Moodle login (T10) changes it."""
import pytest

from app.core.security import hash_password
from app.models.user import User

pytestmark = pytest.mark.db

STUDENT_EMAIL, STUDENT_PASSWORD = "student.test@siswa.um.edu.my", "Student@1234"  # conftest `users`


async def _login(client, email=STUDENT_EMAIL, password=STUDENT_PASSWORD):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def test_login_returns_student_profile(client, users):
    resp = await _login(client)
    assert resp.status_code == 200, resp.text
    user = resp.json()["user"]
    assert user["role"] == "student"
    assert user["student"]["matric_no"] == "S0000001"
    assert user["lecturer"] is None


async def test_login_unknown_email_gives_same_error_as_wrong_password(client, users):
    unknown = await _login(client, email="nobody@um.edu.my")
    wrong = await _login(client, password="nope")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


async def test_inactive_user_cannot_login(client, db_session):
    db_session.add(User(email="gone@um.edu.my", password_hash=hash_password("Gone@1234"),
                        role="student", name="Gone", status="inactive"))
    await db_session.commit()
    resp = await _login(client, email="gone@um.edu.my", password="Gone@1234")
    assert resp.status_code == 401


async def test_refresh_gives_new_working_access_token(client, users):
    tokens = (await _login(client)).json()
    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200, resp.text
    access = resp.json()["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == STUDENT_EMAIL


async def test_refresh_rejects_access_token(client, users):
    tokens = (await _login(client)).json()
    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


async def test_me_rejects_refresh_token(client, users):
    tokens = (await _login(client)).json()
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert resp.status_code == 401
