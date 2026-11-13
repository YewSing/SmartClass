"""Characterisation: legacy unrecognised-face review queue (admin list/dismiss/promote, until T96)."""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.attendance import AttendanceRecord
from app.models.audit import AuditLog
from app.models.consent import FaceConsent
from app.models.face import FaceEmbedding
from app.models.face_review import FaceReviewEntry

pytestmark = pytest.mark.db

# T46b: /internal/face-review is gone and nothing adds rows any more; the admin endpoints stay
# until T96, so these tests put a legacy row in the table directly.


def _vec(*head: float) -> list[float]:
    """512-dim embedding whose first components are `head`, rest zero."""
    return [*head, *([0.0] * (512 - len(head)))]


async def _report(embedding, session_id=None, similarity=0.0):
    async with AsyncSessionLocal() as db:
        db.add(FaceReviewEntry(embedding=embedding, session_id=session_id, camera_device_id="cam-1",
                               similarity=similarity, occurrences=1))
        await db.commit()


async def _entries(db):
    db.expire_all()
    return (await db.execute(select(FaceReviewEntry).order_by(FaceReviewEntry.id))).scalars().all()


async def test_admin_list_queue(client, admin_client, lecturer_client, classroom):
    session_id = (await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )).json()["id"]
    await _report(_vec(1.0), session_id=session_id, similarity=0.2)

    resp = await admin_client.get("/admin/face-review")
    assert resp.status_code == 200, resp.text
    [entry] = resp.json()
    assert entry["session_id"] == session_id
    assert entry["class_name"] == "Intro to Testing"
    assert entry["session_date"] is not None
    assert entry["occurrences"] == 1
    assert entry["closest_match_student_id"] is None  # no enrolled faces yet

    assert (await lecturer_client.get("/admin/face-review")).status_code == 403


async def test_admin_dismiss_entry(client, admin_client, users, db_session):
    await _report(_vec(1.0))
    [entry] = await _entries(db_session)
    entry_id = entry.id

    assert (await admin_client.delete(f"/admin/face-review/{entry_id}")).status_code == 204
    assert await _entries(db_session) == []
    log = (await db_session.execute(select(AuditLog))).scalar_one()
    assert (log.action, log.actor_id, log.target_id) == ("FACE_REVIEW_DISMISS", users["admin"].id, str(entry_id))

    assert (await admin_client.delete(f"/admin/face-review/{entry_id}")).status_code == 404


async def test_admin_promote_sets_embedding_and_marks_present(
    client, admin_client, lecturer_client, users, classroom, db_session
):
    session_id = (await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )).json()["id"]
    await _report(_vec(0.0, 1.0), session_id=session_id, similarity=0.2)
    [entry] = await _entries(db_session)
    entry_id = entry.id
    student_user_id, student_id = classroom["student_user_ids"][2], classroom["student_ids"][2]
    db_session.add(FaceConsent(student_id=student_id, version=settings.FACE_CONSENT_VERSION))  # T14: NFR-03
    await db_session.commit()

    resp = await admin_client.post(f"/admin/face-review/{entry_id}/promote",
                                   json={"student_user_id": student_user_id, "mark_present": True})
    assert resp.status_code == 204, resp.text

    assert await _entries(db_session) == []
    emb = (await db_session.execute(
        select(FaceEmbedding).where(FaceEmbedding.student_id == student_id)
    )).scalar_one()
    assert list(emb.embedding[:2]) == [0.0, 1.0]
    rec = (await db_session.execute(select(AttendanceRecord).where(
        AttendanceRecord.session_id == session_id, AttendanceRecord.student_id == student_id
    ))).scalar_one()
    assert rec.status == "present"
    assert rec.override_by == users["admin"].id
    log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "FACE_PROMOTE"))).scalar_one()
    assert log.action == "FACE_PROMOTE"

    # Promoting again (entry gone) is 404.
    assert (await admin_client.post(f"/admin/face-review/{entry_id}/promote",
                                    json={"student_user_id": student_user_id})).status_code == 404


async def test_promote_unknown_student_is_404_and_keeps_entry(client, admin_client, users, db_session):
    await _report(_vec(1.0))
    [entry] = await _entries(db_session)
    resp = await admin_client.post(f"/admin/face-review/{entry.id}/promote", json={"student_user_id": 999_999})
    assert resp.status_code == 404
    assert len(await _entries(db_session)) == 1
    assert await db_session.scalar(select(func.count()).select_from(FaceEmbedding)) == 0


# ── T46b: the legacy rows are deleted (NFR-02) ───────────────────────────────

def _migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "b5c6d7e8f9a0_empty_legacy_face_review_queue.py"
    spec = importlib.util.spec_from_file_location("t46b_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_migration_deletes_every_legacy_review_row(users, db_session):
    await _report(_vec(1.0))
    await _report(_vec(0.0, 1.0))
    assert len(await _entries(db_session)) == 2

    await db_session.execute(_migration().DELETE_LEGACY_ROWS)
    await db_session.commit()

    assert await _entries(db_session) == []


def test_migration_follows_the_current_head():
    m = _migration()
    assert (m.revision, m.down_revision) == ("b5c6d7e8f9a0", "a4b5c6d7e8f9")
