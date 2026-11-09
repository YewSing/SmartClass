"""T14: PDPA face-data consent + withdrawal (FR-109, FR-116, NFR-03)."""
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.main import app
from app.models.audit import AuditLog
from app.models.consent import FaceConsent
from app.models.face import FaceEmbedding
from app.models.face_review import FaceReviewEntry
from app.models.user import Student

pytestmark = pytest.mark.db

URL = "/student/me/face-consent"
VERSION = settings.FACE_CONSENT_VERSION


async def _student_id(db, user) -> int:
    return await db.scalar(select(Student.id).where(Student.user_id == user.id))


async def _consents(db, student_id):
    db.expire_all()
    return (await db.execute(
        select(FaceConsent).where(FaceConsent.student_id == student_id).order_by(FaceConsent.id)
    )).scalars().all()


async def _audit(db, action):
    return (await db.execute(select(AuditLog).where(AuditLog.action == action))).scalars().all()


async def test_status_before_consent(student_client, users):
    resp = await student_client.get(URL)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"active": False, "version": None, "accepted_at": None, "current_version": VERSION}


async def test_give_consent_records_version_and_time_and_audits(student_client, users, db_session):
    resp = await student_client.post(URL, json={"version": VERSION})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["active"] is True and body["version"] == VERSION and body["accepted_at"]

    [consent] = await _consents(db_session, await _student_id(db_session, users["student"]))
    assert consent.version == VERSION
    assert consent.accepted_at is not None and consent.withdrawn_at is None
    [log] = await _audit(db_session, "FACE_CONSENT_GIVE")
    assert (log.actor_id, log.target_id) == (users["student"].id, str(users["student"].id))

    assert (await student_client.get(URL)).json()["active"] is True


async def test_giving_consent_twice_keeps_one_record(student_client, users, db_session):
    assert (await student_client.post(URL, json={"version": VERSION})).status_code == 201
    assert (await student_client.post(URL, json={"version": VERSION})).status_code == 200
    assert len(await _consents(db_session, await _student_id(db_session, users["student"]))) == 1


async def test_outdated_notice_version_is_refused(student_client, users, db_session):
    resp = await student_client.post(URL, json={"version": "2020-01-old"})
    assert resp.status_code == 409
    assert await _consents(db_session, await _student_id(db_session, users["student"])) == []


async def test_new_notice_version_replaces_old_consent(student_client, users, db_session):
    sid = await _student_id(db_session, users["student"])
    db_session.add(FaceConsent(student_id=sid, version="2025-old"))
    await db_session.commit()

    assert (await student_client.post(URL, json={"version": VERSION})).status_code == 201
    old, new = await _consents(db_session, sid)
    assert old.withdrawn_at is not None
    assert new.version == VERSION and new.withdrawn_at is None


async def test_withdraw_deletes_embeddings_at_once_and_audits(student_client, users, db_session):
    sid = await _student_id(db_session, users["student"])
    assert (await student_client.post(URL, json={"version": VERSION})).status_code == 201
    db_session.add(FaceEmbedding(student_id=sid, embedding=[0.1] * 512))
    await db_session.commit()

    assert (await student_client.delete(URL)).status_code == 204

    db_session.expire_all()
    assert await db_session.scalar(
        select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.student_id == sid)) == 0
    [consent] = await _consents(db_session, sid)
    assert consent.withdrawn_at is not None  # record kept, marked withdrawn
    [log] = await _audit(db_session, "FACE_CONSENT_WITHDRAW")
    assert log.actor_id == users["student"].id
    assert '"embeddings_deleted": 1' in log.new_val
    assert (await student_client.get(URL)).json()["active"] is False


async def test_withdraw_without_consent_is_404(student_client, users):
    assert (await student_client.delete(URL)).status_code == 404


async def test_withdraw_leaves_other_students_embeddings(student_client, users, classroom, db_session):
    other = classroom["student_ids"][1]
    db_session.add(FaceEmbedding(student_id=other, embedding=[0.2] * 512))
    await db_session.commit()
    await student_client.post(URL, json={"version": VERSION})
    assert (await student_client.delete(URL)).status_code == 204
    assert await db_session.scalar(
        select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.student_id == other)) == 1


async def test_consent_endpoints_are_student_only(lecturer_client, admin_client, users):
    for c in (lecturer_client, admin_client):
        assert (await c.get(URL)).status_code == 403
        assert (await c.post(URL, json={"version": VERSION})).status_code == 403
        assert (await c.delete(URL)).status_code == 403


async def test_admin_face_enroll_refused_without_consent(admin_client, users, db_session, monkeypatch):
    monkeypatch.setattr(app.state, "face_app", None, raising=False)  # lifespan doesn't run in tests
    sid = await _student_id(db_session, users["student"])
    resp = await admin_client.post(
        f"/admin/students/{users['student'].id}/face-enroll",
        files={"images": ("a.jpg", b"not-an-image", "image/jpeg")},
    )
    assert resp.status_code == 409
    assert "consent" in resp.json()["detail"]
    assert await db_session.scalar(select(func.count()).select_from(FaceEmbedding)) == 0

    # With consent the request gets past the consent check to the (unloaded) face model.
    db_session.add(FaceConsent(student_id=sid, version=VERSION))
    await db_session.commit()
    resp = await admin_client.post(
        f"/admin/students/{users['student'].id}/face-enroll",
        files={"images": ("a.jpg", b"not-an-image", "image/jpeg")},
    )
    assert resp.status_code == 503


async def test_admin_face_enroll_refused_after_withdrawal(student_client, admin_client, users):
    await student_client.post(URL, json={"version": VERSION})
    await student_client.delete(URL)
    resp = await admin_client.post(
        f"/admin/students/{users['student'].id}/face-enroll",
        files={"images": ("a.jpg", b"not-an-image", "image/jpeg")},
    )
    assert resp.status_code == 409


async def test_face_review_promote_refused_without_consent(admin_client, users, db_session):
    entry = FaceReviewEntry(embedding=[0.3] * 512)
    db_session.add(entry)
    await db_session.commit()

    resp = await admin_client.post(f"/admin/face-review/{entry.id}/promote",
                                   json={"student_user_id": users["student"].id})
    assert resp.status_code == 409
    db_session.expire_all()
    assert await db_session.scalar(select(func.count()).select_from(FaceEmbedding)) == 0
    assert await db_session.scalar(select(func.count()).select_from(FaceReviewEntry)) == 1  # entry kept
