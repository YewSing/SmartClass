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
# Closing a session starts a Moodle sync in the background as soon as it commits (T38b); with a
# MOODLE_TOKEN in .env that would reach the real Moodle. Tests that exercise it turn it back on
# (interval > 0) against the respx fake.
settings.MOODLE_ATTENDANCE_SYNC_INTERVAL_SECONDS = 0

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core import security  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402

# The user fixtures hash ~6 passwords per db test; at bcrypt's default cost (12) that was
# ~1.5 s of setup per test, most of the suite's run time. Cost 4 is still real bcrypt
# (hash, verify and wrong-password checks behave the same); the app itself keeps the default.
security._pwd_ctx.update(bcrypt__rounds=4)
from app.main import app  # noqa: E402
from app.models.user import Lecturer, Student, User  # noqa: E402

ADMIN_EMAIL, ADMIN_PASSWORD = "admin@um.edu.my", "Admin@1234"
LECTURER_EMAIL, LECTURER_PASSWORD = "lecturer.test@um.edu.my", "Lecturer@1234"
STUDENT_EMAIL, STUDENT_PASSWORD = "student.test@siswa.um.edu.my", "Student@1234"


# ── marker-based skips (live / moodle need real config) ──────────────────────

def _face_libs_missing() -> str | None:
    """Why `face` tests can't run here (insightface/rapidocr are optional backend deps)."""
    import importlib.util

    for module in ("insightface", "rapidocr_onnxruntime"):
        if importlib.util.find_spec(module) is None:
            return f"{module} not installed"
    model_dir = Path.home() / ".insightface" / "models" / settings.INSIGHTFACE_MODEL
    if not model_dir.is_dir():
        return f"InsightFace model {settings.INSIGHTFACE_MODEL} not downloaded"
    return None


def pytest_collection_modifyitems(config, items):
    skip_live = pytest.mark.skip(reason="LLM_API_KEY not set")
    skip_moodle = pytest.mark.skip(reason="MOODLE_TOKEN not set")
    face_items = [i for i in items if i.get_closest_marker("face")]
    face_missing = _face_libs_missing() if face_items else None
    for item in items:
        if face_missing and item in face_items:
            item.add_marker(pytest.mark.skip(reason=face_missing))
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


class _TestDatabaseLock:
    """One pytest run at a time per test database. A second run (another terminal, or a loop
    builder's leftover run) would DROP ... WITH (FORCE) and truncate it under the first one:
    users vanish mid-test (401s) and a TRUNCATE can wait on a stale transaction for ever."""

    def __init__(self, name: str):
        import tempfile

        self.path = Path(tempfile.gettempdir()) / f"smartclass-pytest-{name}.lock"
        self.file = None

    def acquire(self) -> None:
        import time

        self.file = open(self.path, "a+b")
        warned = False
        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    self.file.seek(0)
                    msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError:
                if not warned:
                    print(f"\nAnother pytest run is using {_test_url.database}; waiting for it to finish...",
                          file=sys.stderr)
                    warned = True
                time.sleep(2)

    def release(self) -> None:
        if self.file is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self.file.close()  # closing also drops an flock
        self.file = None


@pytest.fixture(scope="session")
def _test_database():
    """Create + migrate smartclass_test once per session (only when a db test runs)."""
    lock = _TestDatabaseLock(_test_url.database)
    lock.acquire()
    try:
        yield _prepare_test_database()
    finally:
        lock.release()


def _prepare_test_database() -> str:
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


@pytest.fixture
async def classroom(users) -> dict:
    """CS101 lecture owned by the test lecturer with 3 enrolled students (incl. the test student),
    plus CS202 owned by another lecturer. Returns plain ids."""
    from sqlalchemy import select

    from app.models.class_ import ClassOccurrence, Course, Enrollment

    async with AsyncSessionLocal() as db:
        lec = (await db.execute(select(Lecturer).where(Lecturer.user_id == users["lecturer"].id))).scalar_one()
        stu = (await db.execute(select(Student).where(Student.user_id == users["student"].id))).scalar_one()

        other_lec_user = User(email="other.lecturer@um.edu.my", password_hash=hash_password("Other@1234"),
                              role="lecturer", name="Other Lecturer", status="active")
        extra_users = [
            User(email=f"student{i}@siswa.um.edu.my", password_hash=hash_password("Student@1234"),
                 role="student", name=f"Student {i}", status="active")
            for i in (2, 3)
        ]
        db.add_all([other_lec_user, *extra_users])
        await db.flush()
        other_lec = Lecturer(user_id=other_lec_user.id, staff_id="STAFF-T002", dept="Computer Science")
        extra_students = [
            Student(user_id=u.id, matric_no=f"S000000{i}", programme="Software Engineering")
            for i, u in zip((2, 3), extra_users)
        ]
        db.add_all([other_lec, *extra_students])
        await db.flush()

        course = Course(code="CS101", name="Intro to Testing")
        other_course = Course(code="CS202", name="Other Course")
        db.add_all([course, other_course])
        await db.flush()
        occ = ClassOccurrence(course_id=course.id, type="LECTURE", day_of_week="Mon",
                              start_time="08:00", end_time="10:00", room="DK1", lecturer_id=lec.id)
        other_occ = ClassOccurrence(course_id=other_course.id, type="LECTURE", day_of_week="Tue",
                                    start_time="10:00", end_time="12:00", room="DK2", lecturer_id=other_lec.id)
        db.add_all([occ, other_occ])
        await db.flush()
        students = [stu, *extra_students]
        db.add_all([Enrollment(student_id=s.id, occurrence_id=occ.id) for s in students])
        await db.commit()
        return {
            "course_id": course.id,
            "occurrence_id": occ.id,
            "other_occurrence_id": other_occ.id,
            "lecturer_id": lec.id,
            "other_lecturer_id": other_lec.id,
            "other_lecturer_user_id": other_lec_user.id,
            "student_ids": [s.id for s in students],  # students.id, ordered by matric_no
            "student_user_ids": [s.user_id for s in students],
        }


@pytest.fixture
async def device() -> dict:
    """A camera device in room DK1 (the `classroom` room) with its own key (T40, FR-408)."""
    from app.models.camera import Camera
    from app.services import device_service

    async with AsyncSessionLocal() as db:
        cam = Camera(label="DK1 door", room="DK1", device_id="cam-1")
        key = device_service.issue_key(cam)
        db.add(cam)
        await db.commit()
        return {"id": cam.id, "device_id": cam.device_id, "key": key, "headers": {"X-Device-Key": key}}


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
async def other_lecturer_client(classroom):
    async with _client(create_access_token(classroom["other_lecturer_user_id"], "lecturer")) as c:
        yield c


@pytest.fixture
async def student_client(users):
    async with _client(create_access_token(users["student"].id, "student")) as c:
        yield c
