"""Shared pytest setup.

`db` tests run against a separate `smartclass_test` database on the docker postgres. It is
dropped, recreated and migrated with alembic once per test session, and every table is
truncated after each `db` test. The dev database is never touched.

Override the test database with TEST_DATABASE_URL (its name must end in `_test`).
"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Point the app at the test database BEFORE app.core.database creates its engine.
from app.core.config import settings  # noqa: E402

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or (
    make_url(settings.DATABASE_URL).set(database="smartclass_test").render_as_string(hide_password=False)
)
_test_url = make_url(TEST_DATABASE_URL)
if not (_test_url.database or "").endswith("_test"):
    raise RuntimeError(f"Refusing to run tests against database '{_test_url.database}' (name must end in _test)")
settings.DATABASE_URL = TEST_DATABASE_URL
os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # for the alembic subprocess

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import Lecturer, Student, User  # noqa: E402

ADMIN_EMAIL, ADMIN_PASSWORD = "admin@um.edu.my", "Admin@1234"
LECTURER_EMAIL, LECTURER_PASSWORD = "lecturer.test@um.edu.my", "Lecturer@1234"
STUDENT_EMAIL, STUDENT_PASSWORD = "student.test@siswa.um.edu.my", "Student@1234"


# ── marker-based skips (live / moodle need real config) ──────────────────────

def pytest_collection_modifyitems(config, items):
    skip_live = pytest.mark.skip(reason="LLM_API_KEY not set")
    skip_moodle = pytest.mark.skip(reason="MOODLE_TOKEN not set")
    for item in items:
        if "db" in item.keywords:
            item.fixturenames.insert(0, "_test_database")
        if "live" in item.keywords and not settings.LLM_API_KEY:
            item.add_marker(skip_live)
        if "moodle" in item.keywords and not settings.MOODLE_TOKEN:
            item.add_marker(skip_moodle)


# ── test database ─────────────────────────────────────────────────────────────

async def _recreate_database() -> None:
    import asyncpg

    admin_dsn = _test_url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    conn = await asyncpg.connect(admin_dsn)
    try:
        name = _test_url.database
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def _test_database():
    """Create + migrate smartclass_test once per session (only when a db test runs)."""
    try:
        asyncio.run(_recreate_database())
    except OSError as exc:
        pytest.fail(f"Test postgres not reachable at {_test_url.host}:{_test_url.port} ({exc}). "
                    "Start it with `docker compose up -d` in backend/.", pytrace=False)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR, env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"alembic upgrade head failed on the test database:\n{result.stderr}", pytrace=False)
    return TEST_DATABASE_URL


async def _truncate_all() -> None:
    async with engine.begin() as conn:
        rows = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
        ))
        tables = [r[0] for r in rows]
        if tables:
            await conn.execute(text(
                "TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"
            ))


@pytest.fixture(autouse=True)
async def _db_isolation(request):
    """For `db` tests (which also get `_test_database`): wipe the tables and drop pooled connections afterwards."""
    if request.node.get_closest_marker("db") is None:
        yield
        return
    try:
        yield
    finally:
        await _truncate_all()
        # Each test has its own event loop; pooled asyncpg connections must not outlive it.
        await engine.dispose()


@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


# ── seeded users + HTTP clients ───────────────────────────────────────────────

@pytest.fixture
async def users() -> dict[str, User]:
    """One active admin, lecturer and student (same admin credentials as scripts/seed.py)."""
    async with AsyncSessionLocal() as db:
        admin = User(email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD),
                     role="admin", name="Admin User", status="active")
        lec_user = User(email=LECTURER_EMAIL, password_hash=hash_password(LECTURER_PASSWORD),
                        role="lecturer", name="Test Lecturer", status="active")
        stu_user = User(email=STUDENT_EMAIL, password_hash=hash_password(STUDENT_PASSWORD),
                        role="student", name="Test Student", status="active")
        db.add_all([admin, lec_user, stu_user])
        await db.flush()
        db.add_all([
            Lecturer(user_id=lec_user.id, staff_id="STAFF-T001", dept="Software Engineering"),
            Student(user_id=stu_user.id, matric_no="S0000001", programme="Software Engineering"),
        ])
        await db.commit()
        return {"admin": admin, "lecturer": lec_user, "student": stu_user}


def _client(token: str | None = None) -> httpx.AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers)


@pytest.fixture
async def client():
    async with _client() as c:
        yield c


@pytest.fixture
async def admin_client(users):
    async with _client(create_access_token(users["admin"].id, "admin")) as c:
        yield c


@pytest.fixture
async def lecturer_client(users):
    async with _client(create_access_token(users["lecturer"].id, "lecturer")) as c:
        yield c


@pytest.fixture
async def student_client(users):
    async with _client(create_access_token(users["student"].id, "student")) as c:
        yield c
