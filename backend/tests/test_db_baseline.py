"""Baseline `db` tests: the test database, seeded users and per-role clients work."""
import pytest
from sqlalchemy import func, select

from app.models.user import User

pytestmark = pytest.mark.db

ADMIN_EMAIL, ADMIN_PASSWORD = "admin@um.edu.my", "Admin@1234"  # same as conftest `users` / scripts/seed.py


async def test_login_with_seeded_admin(client, users):
    resp = await client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["email"] == ADMIN_EMAIL
    assert body["user"]["role"] == "admin"

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


async def test_login_wrong_password_is_rejected(client, users):
    resp = await client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong-password"})
    assert resp.status_code == 401


async def test_role_clients_are_authenticated(admin_client, lecturer_client, student_client):
    for role, c in [("admin", admin_client), ("lecturer", lecturer_client), ("student", student_client)]:
        resp = await c.get("/auth/me")
        assert resp.status_code == 200, resp.text
        assert resp.json()["role"] == role


async def test_unauthenticated_client_is_rejected(client):
    resp = await client.get("/auth/me")
    assert resp.status_code in (401, 403)


async def test_tables_are_empty_between_tests(db_session):
    count = await db_session.scalar(select(func.count()).select_from(User))
    assert count == 0
