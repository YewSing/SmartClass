"""T17: lecturer verification queue + admin fallback (FR-113, FR-114, FR-117, NFR-01, NFR-03).

Pending submissions are inserted directly (T16 tests how they are created), with photos,
OCR lines and the averaged selfie embedding, as the enrolment endpoint stores them.
"""
import json

import numpy as np
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.consent import FaceConsent
from app.models.face import FaceEmbedding
from app.models.face_enrolment import FaceEnrolment, FaceEnrolmentImage
from app.models.user import Student

pytestmark = pytest.mark.db

URL = "/face-verification"
EMB = (np.ones(512) / np.sqrt(512)).tolist()


async def _pending(db, student_id: int, *, consent: bool = True) -> int:
    if consent:
        db.add(FaceConsent(student_id=student_id, version=settings.FACE_CONSENT_VERSION))
    enrolment = FaceEnrolment(
        student_id=student_id, status="pending_review", check_reasons=["matric_mismatch"],
        face_score=0.82, ocr_matric="S0009999", ocr_matric_confidence=0.95, name_score=1.0,
        quality_scores={"glare_fraction": 0.01}, ocr_lines=["TEST STUDENT", "S0009999"], embedding=EMB,
    )
    db.add(enrolment)
    await db.flush()
    db.add_all([FaceEnrolmentImage(enrolment_id=enrolment.id, kind="selfie", position=i,
                                   content_type="image/jpeg", data=b"selfie%d" % i) for i in range(3)])
    db.add(FaceEnrolmentImage(enrolment_id=enrolment.id, kind="card", position=0,
                              content_type="image/png", data=b"card-bytes"))
    await db.commit()
    return enrolment.id


@pytest.fixture
async def sub(classroom, db_session) -> int:
    """A pending submission by the test student, who is in the test lecturer's CS101."""
    return await _pending(db_session, classroom["student_ids"][0])


async def _count(db, model, *where):
    db.expire_all()
    return await db.scalar(select(func.count()).select_from(model).where(*where))


async def _audit(db, action):
    db.expire_all()
    return (await db.execute(select(AuditLog).where(AuditLog.action == action))).scalars().all()


# ── listing ──────────────────────────────────────────────────────────────────

async def test_lecturer_lists_own_students_submission_with_details(lecturer_client, sub, users):
    resp = await lecturer_client.get(f"{URL}/pending")
    assert resp.status_code == 200, resp.text
    [item] = resp.json()
    assert item["id"] == sub and item["student_user_id"] == users["student"].id
    assert item["student_name"] == "Test Student" and item["matric_no"] == "S0000001"
    assert item["ocr_matric"] == "S0009999" and item["ocr_matric_confidence"] == 0.95
    assert item["face_score"] == 0.82 and item["name_score"] == 1.0
    assert item["check_reasons"] == ["matric_mismatch"] and item["ocr_lines"] == ["TEST STUDENT", "S0009999"]
    assert item["courses"] == ["CS101"]
    assert [(i["kind"], i["position"]) for i in item["images"]] == [
        ("selfie", 0), ("selfie", 1), ("selfie", 2), ("card", 0)]


async def test_images_are_served_to_the_reviewer_without_caching(lecturer_client, sub):
    [item] = (await lecturer_client.get(f"{URL}/pending")).json()
    card = next(i for i in item["images"] if i["kind"] == "card")
    resp = await lecturer_client.get(card["url"])
    assert resp.status_code == 200
    assert resp.content == b"card-bytes" and resp.headers["content-type"] == "image/png"
    assert resp.headers["cache-control"] == "no-store"


async def test_image_of_another_submission_is_404(lecturer_client, sub, classroom, db_session):
    other = await _pending(db_session, classroom["student_ids"][1])
    [item] = [i for i in (await lecturer_client.get(f"{URL}/pending")).json() if i["id"] == other]
    image_id = item["images"][0]["id"]
    assert (await lecturer_client.get(f"{URL}/{sub}/images/{image_id}")).status_code == 404


async def test_other_lecturer_sees_nothing_and_gets_403(other_lecturer_client, sub):
    assert (await other_lecturer_client.get(f"{URL}/pending")).json() == []
    assert (await other_lecturer_client.post(f"{URL}/{sub}/approve")).status_code == 403
    assert (await other_lecturer_client.post(f"{URL}/{sub}/reject", json={"reason": "no"})).status_code == 403
    assert (await other_lecturer_client.get(f"{URL}/{sub}/images/1")).status_code == 403


async def test_lecturer_of_another_class_of_the_same_course_may_review(other_lecturer_client, sub, classroom, db_session):
    from app.models.class_ import ClassOccurrence
    db_session.add(ClassOccurrence(course_id=classroom["course_id"], type="TUTORIAL", day_of_week="Wed",
                                   start_time="10:00", end_time="11:00",
                                   lecturer_id=classroom["other_lecturer_id"]))
    await db_session.commit()
    [item] = (await other_lecturer_client.get(f"{URL}/pending")).json()
    assert item["id"] == sub and item["courses"] == ["CS101"]


async def test_student_gets_403(student_client, sub):
    assert (await student_client.get(f"{URL}/pending")).status_code == 403
    assert (await student_client.post(f"{URL}/{sub}/approve")).status_code == 403


async def test_admin_sees_every_pending_submission(admin_client, users, db_session):
    # A student in no course at all is still visible to the admin fallback (FR-117).
    sid = await db_session.scalar(select(Student.id).where(Student.user_id == users["student"].id))
    sub = await _pending(db_session, sid)
    [item] = (await admin_client.get(f"{URL}/pending")).json()
    assert item["id"] == sub and item["courses"] == []


async def test_decided_submissions_are_not_listed(lecturer_client, sub, db_session):
    enrolment = await db_session.get(FaceEnrolment, sub)
    enrolment.status = "rejected"
    await db_session.commit()
    assert (await lecturer_client.get(f"{URL}/pending")).json() == []


async def test_unknown_submission_is_404(lecturer_client, classroom):
    assert (await lecturer_client.post(f"{URL}/999999/approve")).status_code == 404


# ── approve ──────────────────────────────────────────────────────────────────

async def test_lecturer_approves_stores_embedding_deletes_images_and_audits(
        lecturer_client, student_client, sub, classroom, users, db_session):
    sid = classroom["student_ids"][0]
    resp = await lecturer_client.post(f"{URL}/{sub}/approve")
    assert resp.status_code == 204, resp.text

    db_session.expire_all()
    [emb] = (await db_session.execute(select(FaceEmbedding).where(FaceEmbedding.student_id == sid))).scalars()
    assert np.allclose(np.array(emb.embedding), EMB, atol=1e-6)
    enrolment = await db_session.get(FaceEnrolment, sub)
    assert enrolment.status == "active" and enrolment.decided_at is not None
    assert enrolment.embedding is None and enrolment.ocr_lines is None
    assert await _count(db_session, FaceEnrolmentImage, FaceEnrolmentImage.enrolment_id == sub) == 0

    [log] = await _audit(db_session, "FACE_ENROL_APPROVE")
    assert log.actor_id == users["lecturer"].id and log.target_id == str(users["student"].id)
    assert json.loads(log.new_val) == {"enrolment_id": sub, "photos_deleted": 4}

    assert (await student_client.get("/student/me/face-enrolment")).json()["status"] == "active"


async def test_approve_replaces_older_embedding(lecturer_client, sub, classroom, db_session):
    sid = classroom["student_ids"][0]
    db_session.add(FaceEmbedding(student_id=sid, embedding=[0.0] * 511 + [1.0]))
    await db_session.commit()
    assert (await lecturer_client.post(f"{URL}/{sub}/approve")).status_code == 204
    assert await _count(db_session, FaceEmbedding, FaceEmbedding.student_id == sid) == 1


async def test_approve_without_consent_is_409_and_changes_nothing(lecturer_client, classroom, db_session):
    sid = classroom["student_ids"][0]
    sub = await _pending(db_session, sid, consent=False)
    assert (await lecturer_client.post(f"{URL}/{sub}/approve")).status_code == 409
    assert await _count(db_session, FaceEmbedding, FaceEmbedding.student_id == sid) == 0
    assert await _count(db_session, FaceEnrolmentImage, FaceEnrolmentImage.enrolment_id == sub) == 4


async def test_deciding_twice_is_409(lecturer_client, sub):
    assert (await lecturer_client.post(f"{URL}/{sub}/approve")).status_code == 204
    assert (await lecturer_client.post(f"{URL}/{sub}/approve")).status_code == 409
    assert (await lecturer_client.post(f"{URL}/{sub}/reject", json={"reason": "x"})).status_code == 409


# ── reject ───────────────────────────────────────────────────────────────────

async def test_lecturer_rejects_with_reason_student_sees_it_and_may_resubmit(
        lecturer_client, student_client, sub, classroom, users, db_session):
    resp = await lecturer_client.post(f"{URL}/{sub}/reject", json={"reason": "  The card is not yours  "})
    assert resp.status_code == 204, resp.text

    db_session.expire_all()
    enrolment = await db_session.get(FaceEnrolment, sub)
    assert enrolment.status == "rejected" and enrolment.reason == "The card is not yours"
    assert enrolment.embedding is None and enrolment.ocr_lines is None
    assert await _count(db_session, FaceEnrolmentImage, FaceEnrolmentImage.enrolment_id == sub) == 0
    assert await _count(db_session, FaceEmbedding, FaceEmbedding.student_id == classroom["student_ids"][0]) == 0

    [log] = await _audit(db_session, "FACE_ENROL_REJECT")
    assert log.actor_id == users["lecturer"].id and log.target_id == str(users["student"].id)
    assert json.loads(log.new_val) == {"enrolment_id": sub, "reason": "The card is not yours", "photos_deleted": 4}

    body = (await student_client.get("/student/me/face-enrolment")).json()
    assert body["status"] == "rejected" and body["reason"] == "The card is not yours"


@pytest.mark.parametrize("payload", [{}, {"reason": ""}, {"reason": "   "}])
async def test_reject_needs_a_reason(lecturer_client, sub, payload, db_session):
    assert (await lecturer_client.post(f"{URL}/{sub}/reject", json=payload)).status_code == 422
    assert await _count(db_session, FaceEnrolmentImage, FaceEnrolmentImage.enrolment_id == sub) == 4


# ── admin fallback (FR-117) ──────────────────────────────────────────────────

async def test_admin_can_approve_and_reject(admin_client, users, classroom, db_session):
    first = await _pending(db_session, classroom["student_ids"][1])
    second = await _pending(db_session, classroom["student_ids"][2])
    assert (await admin_client.post(f"{URL}/{first}/approve")).status_code == 204
    assert (await admin_client.post(f"{URL}/{second}/reject", json={"reason": "Blurry"})).status_code == 204
    actors = [log.actor_id for log in await _audit(db_session, "FACE_ENROL_APPROVE")]
    actors += [log.actor_id for log in await _audit(db_session, "FACE_ENROL_REJECT")]
    assert actors == [users["admin"].id] * 2
    assert await _count(db_session, FaceEnrolmentImage) == 0


async def test_admin_reset_deletes_embeddings_and_closes_pending(admin_client, sub, classroom, users, db_session):
    sid = classroom["student_ids"][0]
    db_session.add(FaceEmbedding(student_id=sid, embedding=EMB))
    await db_session.commit()

    resp = await admin_client.delete(f"/admin/students/{users['student'].id}/face-data")
    assert resp.status_code == 204, resp.text
    assert await _count(db_session, FaceEmbedding, FaceEmbedding.student_id == sid) == 0
    assert await _count(db_session, FaceEnrolmentImage, FaceEnrolmentImage.enrolment_id == sub) == 0
    db_session.expire_all()
    enrolment = await db_session.get(FaceEnrolment, sub)
    assert enrolment.status == "reset" and enrolment.embedding is None
    [log] = await _audit(db_session, "FACE_REMOVE")
    assert log.actor_id == users["admin"].id


async def test_admin_reset_with_only_a_pending_submission(admin_client, student_client, sub, users):
    assert (await admin_client.delete(f"/admin/students/{users['student'].id}/face-data")).status_code == 204
    assert (await student_client.get("/student/me/face-enrolment")).json()["status"] == "not_enrolled"


async def test_admin_reset_with_nothing_is_404(admin_client, users):
    assert (await admin_client.delete(f"/admin/students/{users['student'].id}/face-data")).status_code == 404


async def test_lecturer_cannot_reset(lecturer_client, users):
    assert (await lecturer_client.delete(f"/admin/students/{users['student'].id}/face-data")).status_code == 403
