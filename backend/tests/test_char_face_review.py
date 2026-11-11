"""Characterisation: unrecognised-face review queue (worker → backend, admin list/dismiss/promote)."""
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.attendance import AttendanceRecord
from app.models.audit import AuditLog
from app.models.consent import FaceConsent
from app.models.face import FaceEmbedding
from app.models.face_review import FaceReviewEntry

pytestmark = pytest.mark.db

INTERNAL_KEY = "test-internal-key"


def _vec(*head: float) -> list[float]:
    """512-dim embedding whose first components are `head`, rest zero."""
    return [*head, *([0.0] * (512 - len(head)))]


@pytest.fixture(autouse=True)
def _internal_key(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_KEY)


async def _report(client, embedding, **extra):
    return await client.post(
        "/internal/face-review",
        json={"embedding": embedding, **extra},
        headers={"X-Internal-Key": INTERNAL_KEY},
    )


async def _entries(db):
    db.expire_all()
    return (await db.execute(select(FaceReviewEntry).order_by(FaceReviewEntry.id))).scalars().all()


async def test_internal_endpoint_needs_key_and_512_dims(client, users):
    resp = await client.post("/internal/face-review", json={"embedding": _vec(1.0)},
                             headers={"X-Internal-Key": "wrong"})
    assert resp.status_code == 401
    resp = await client.post("/internal/face-review", json={"embedding": _vec(1.0)})
    assert resp.status_code == 422  # header missing
    assert (await _report(client, [1.0, 0.0])).status_code == 400


async def test_similar_faces_are_merged_and_closest_match_recorded(
    client, lecturer_client, classroom, db_session
):
    db_session.add(FaceEmbedding(student_id=classroom["student_ids"][1], embedding=_vec(1.0)))
    await db_session.commit()
    session_id = (await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )).json()["id"]

    assert (await _report(client, _vec(1.0, 0.1), session_id=session_id, similarity=0.2,
                          camera_device_id="cam-1")).status_code == 204
    assert (await _report(client, _vec(1.0, 0.2), session_id=session_id, similarity=0.3)).status_code == 204
    assert (await _report(client, _vec(0.0, 1.0), session_id=session_id, similarity=0.1)).status_code == 204

    entries = await _entries(db_session)
    assert len(entries) == 2
    merged, separate = entries
    assert merged.occurrences == 2
    assert merged.similarity == pytest.approx(0.3)  # keeps the best reading
    assert merged.camera_device_id == "cam-1"
    assert merged.closest_match_student_id == classroom["student_user_ids"][1]  # users.id, not students.id
    assert merged.closest_match_confidence == pytest.approx(0.98, abs=0.01)
    assert separate.occurrences == 1

    # Unidentified count in the session reflects the queue.
    sessions = (await lecturer_client.get("/lecturer/sessions")).json()
    assert sessions[0]["unid"] == 2


async def test_admin_list_queue(client, admin_client, lecturer_client, classroom):
    session_id = (await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )).json()["id"]
    await _report(client, _vec(1.0), session_id=session_id, similarity=0.2)

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
    await _report(client, _vec(1.0))
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
    await _report(client, _vec(0.0, 1.0), session_id=session_id, similarity=0.2)
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
    await _report(client, _vec(1.0))
    [entry] = await _entries(db_session)
    resp = await admin_client.post(f"/admin/face-review/{entry.id}/promote", json={"student_user_id": 999_999})
    assert resp.status_code == 404
    assert len(await _entries(db_session)) == 1
    assert await db_session.scalar(select(func.count()).select_from(FaceEmbedding)) == 0
