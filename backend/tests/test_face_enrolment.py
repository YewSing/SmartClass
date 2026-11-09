"""T16: face self-enrolment endpoint (FR-110, FR-112, FR-115, NFR-01).

Most tests replace `verify_card` (T15, tested on its own) with a canned result so each path
is quick and exact; the last two run the real InsightFace + OCR on generated card photos.
"""
import cv2
import numpy as np
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.main import app
from app.models.audit import AuditLog
from app.models.consent import FaceConsent
from app.models.face import FaceEmbedding
from app.models.face_enrolment import FaceEnrolment, FaceEnrolmentImage
from app.models.user import Student
from app.services import face_verification as fv

pytestmark = pytest.mark.db

URL = "/student/me/face-enrolment"
EMB = np.ones(512) / np.sqrt(512)


def _png(seed: int = 0) -> bytes:
    img = np.random.default_rng(seed).integers(0, 255, (60, 80, 3), dtype=np.uint8)
    return cv2.imencode(".png", img)[1].tobytes()


def _files(n_selfies: int = 3, card: bytes | None = None):
    files = [("selfies", (f"s{i}.png", _png(i), "image/png")) for i in range(n_selfies)]
    files.append(("card", ("card.png", card if card is not None else _png(99), "image/png")))
    return files


def _result(*, face=True, matric=True, name=True, quality=(), blocking=False, selfie_emb=EMB,
            selfie_faces=3, selfie_count=3, consistency=0.9, um_card=True):
    return fv.CardVerification(
        quality=fv.QualityResult(reasons=list(quality), blocking=blocking, scores={"glare_fraction": 0.2}),
        face=fv.FaceMatch(passed=face, score=0.8 if face else 0.1, card_face_found=True,
                          selfie_embedding=selfie_emb,
                          selfie_faces=selfie_faces if selfie_emb is not None else 0,
                          selfie_count=selfie_count, selfie_consistency=consistency),
        card=fv.CardRead(matric="S0000001" if matric else "S0009999", matric_confidence=0.97,
                         matric_match=matric, name_score=1.0 if name else 0.0, name_match=name,
                         lines=["TEST STUDENT", "S0000001"], um_card=um_card),
    )


@pytest.fixture
def verify(monkeypatch):
    """Patch the model and verify_card; set `verify.result` per test, see calls in `verify.calls`."""
    class Fake:
        result = _result()
        calls: list = []

        def __call__(self, face_app, selfies, card, matric, name):
            self.calls.append((len(selfies), matric, name))
            return self.result

    fake = Fake()
    fake.calls = []
    monkeypatch.setattr(app.state, "face_app", object(), raising=False)
    monkeypatch.setattr(fv, "verify_card", fake)
    return fake


@pytest.fixture
async def sid(users, db_session) -> int:
    """The test student's id, with consent given."""
    student_id = await db_session.scalar(select(Student.id).where(Student.user_id == users["student"].id))
    db_session.add(FaceConsent(student_id=student_id, version=settings.FACE_CONSENT_VERSION))
    await db_session.commit()
    return student_id


async def _count(db, model, *where):
    db.expire_all()
    return await db.scalar(select(func.count()).select_from(model).where(*where))


async def _enrolments(db, student_id):
    db.expire_all()
    return (await db.execute(select(FaceEnrolment).where(FaceEnrolment.student_id == student_id)
                             .order_by(FaceEnrolment.id))).scalars().all()


# ── status ───────────────────────────────────────────────────────────────────

async def test_status_not_enrolled(student_client, sid):
    resp = await student_client.get(URL)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "not_enrolled"
    assert resp.json()["blocked_attempts"] == 0 and resp.json()["can_submit_anyway"] is False


async def test_status_active_when_enrolled_another_way(student_client, sid, db_session):
    db_session.add(FaceEmbedding(student_id=sid, embedding=[0.1] * 512))
    await db_session.commit()
    assert (await student_client.get(URL)).json()["status"] == "active"


async def test_status_rejected_shows_reason(student_client, sid, db_session):
    db_session.add(FaceEnrolment(student_id=sid, status="rejected", reason="Card photo is not yours",
                                 check_reasons=["face_mismatch"]))
    await db_session.commit()
    body = (await student_client.get(URL)).json()
    assert body["status"] == "rejected" and body["reason"] == "Card photo is not yours"


# ── auto-approve path (FR-112) ───────────────────────────────────────────────

async def test_both_checks_pass_auto_approves_and_keeps_no_images(student_client, users, sid, verify, db_session):
    resp = await student_client.post(URL, files=_files(4))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "active" and body["submitted_at"] and body["decided_at"]
    assert verify.calls == [(4, "S0000001", "Test Student")]  # checked against the account

    [emb] = (await db_session.execute(select(FaceEmbedding).where(FaceEmbedding.student_id == sid))).scalars()
    assert np.allclose(np.array(emb.embedding), EMB, atol=1e-6)
    [enrolment] = await _enrolments(db_session, sid)
    assert enrolment.status == "active" and enrolment.embedding is None and enrolment.ocr_lines is None
    assert await _count(db_session, FaceEnrolmentImage) == 0  # NFR-01: photos never stored
    [log] = (await db_session.execute(select(AuditLog).where(AuditLog.action == "FACE_ENROL_AUTO_APPROVE"))).scalars()
    assert log.actor_id == users["student"].id
    assert (await student_client.get(URL)).json()["status"] == "active"


# ── pending review path (FR-113) ─────────────────────────────────────────────

@pytest.mark.parametrize("kwargs, reason", [
    ({"face": False}, "face_mismatch"),
    ({"matric": False}, "matric_mismatch"),
    ({"name": False}, "name_mismatch"),
])
async def test_a_failed_check_goes_to_review_with_images_kept(student_client, sid, verify, db_session, kwargs, reason):
    verify.result = _result(**kwargs)
    resp = await student_client.post(URL, files=_files(3))
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending_review"

    assert await _count(db_session, FaceEmbedding, FaceEmbedding.student_id == sid) == 0
    [enrolment] = await _enrolments(db_session, sid)
    assert enrolment.status == "pending_review" and reason in enrolment.check_reasons
    assert enrolment.embedding is not None and enrolment.ocr_lines == ["TEST STUDENT", "S0000001"]
    kinds = (await db_session.execute(
        select(FaceEnrolmentImage.kind).where(FaceEnrolmentImage.enrolment_id == enrolment.id)
        .order_by(FaceEnrolmentImage.id))).scalars().all()
    assert kinds == ["selfie", "selfie", "selfie", "card"]
    assert await _count(db_session, AuditLog, AuditLog.action == "FACE_ENROL_SUBMIT") == 1
    assert (await student_client.get(URL)).json()["status"] == "pending_review"


async def test_no_face_on_card_still_goes_to_review_with_selfie_embedding(student_client, sid, verify, db_session):
    r = _result()
    r.face = fv.FaceMatch(passed=False, score=None, reason="no_face_on_card", selfie_embedding=EMB,
                          selfie_faces=3, selfie_count=3, selfie_consistency=0.9)
    verify.result = r
    assert (await student_client.post(URL, files=_files())).json()["status"] == "pending_review"
    [enrolment] = await _enrolments(db_session, sid)
    assert "no_face_on_card" in enrolment.check_reasons and enrolment.embedding is not None


async def test_cannot_submit_again_while_pending_or_active(student_client, sid, verify, db_session):
    verify.result = _result(face=False)
    assert (await student_client.post(URL, files=_files())).status_code == 201
    assert (await student_client.post(URL, files=_files())).status_code == 409

    await db_session.execute(FaceEnrolment.__table__.update().values(status="rejected", reason="x"))
    await db_session.commit()
    verify.result = _result()
    assert (await student_client.post(URL, files=_files())).status_code == 201  # rejected may resubmit (FR-114)
    assert (await student_client.post(URL, files=_files())).status_code == 409  # now active


async def test_withdrawing_consent_deletes_pending_images_and_embedding(student_client, sid, verify, db_session):
    verify.result = _result(matric=False)
    assert (await student_client.post(URL, files=_files())).status_code == 201
    assert await _count(db_session, FaceEnrolmentImage) == 4

    assert (await student_client.delete("/student/me/face-consent")).status_code == 204
    assert await _count(db_session, FaceEnrolmentImage) == 0
    [enrolment] = await _enrolments(db_session, sid)
    assert enrolment.status == "withdrawn" and enrolment.embedding is None and enrolment.ocr_lines is None
    assert (await student_client.get(URL)).json()["status"] == "not_enrolled"


# ── quality block (422) and "submit anyway" ──────────────────────────────────

async def test_blocking_quality_returns_422_with_reason_and_stores_nothing(student_client, sid, verify, db_session):
    verify.result = _result(matric=False, quality=["glare", "blurry"], blocking=True)
    resp = await student_client.post(URL, files=_files())
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["reasons"] == ["glare", "blurry"]
    assert detail["message"] == fv.QUALITY_MESSAGES["glare"]
    assert detail["blocked_attempts"] == 1 and detail["can_submit_anyway"] is False

    assert await _count(db_session, FaceEmbedding) == 0
    assert await _count(db_session, FaceEnrolmentImage) == 0
    [attempt] = await _enrolments(db_session, sid)
    assert attempt.status == "blocked" and attempt.embedding is None and attempt.ocr_lines is None
    assert (await student_client.get(URL)).json()["status"] == "not_enrolled"


async def test_submit_anyway_only_after_two_blocked_attempts(student_client, sid, verify, db_session):
    verify.result = _result(matric=False, quality=["glare"], blocking=True)

    first = await student_client.post(URL, files=_files(), data={"submit_anyway": "true"})
    assert first.status_code == 422  # too early: the flag is ignored
    second = await student_client.post(URL, files=_files())
    assert second.status_code == 422 and second.json()["detail"]["can_submit_anyway"] is True
    status = (await student_client.get(URL)).json()
    assert status["blocked_attempts"] == 2 and status["can_submit_anyway"] is True

    assert (await student_client.post(URL, files=_files())).status_code == 422  # a third retake is allowed
    resp = await student_client.post(URL, files=_files(), data={"submit_anyway": "true"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending_review" and resp.json()["blocked_attempts"] == 0

    enrolment = (await _enrolments(db_session, sid))[-1]
    assert enrolment.submitted_anyway and "submitted_anyway" in enrolment.check_reasons
    assert "glare" in enrolment.check_reasons
    assert await _count(db_session, FaceEnrolmentImage, FaceEnrolmentImage.enrolment_id == enrolment.id) == 4


async def test_no_face_in_selfies_is_a_retake(student_client, sid, verify, db_session):
    verify.result = _result(selfie_emb=None)
    resp = await student_client.post(URL, files=_files())
    assert resp.status_code == 422 and resp.json()["detail"]["reasons"] == ["no_face_in_selfies"]
    assert await _enrolments(db_session, sid) == []


async def test_photo_that_is_not_an_image_is_a_retake(student_client, sid, verify, db_session):
    resp = await student_client.post(URL, files=_files(card=b"not an image"))
    assert resp.status_code == 422 and resp.json()["detail"]["reasons"] == ["not_an_image"]
    assert verify.calls == [] and await _enrolments(db_session, sid) == []


# ── input and access rules ───────────────────────────────────────────────────

async def test_refused_without_consent(student_client, users, verify, db_session):
    resp = await student_client.post(URL, files=_files())
    assert resp.status_code == 409 and "consent" in resp.json()["detail"]
    assert verify.calls == []


@pytest.mark.parametrize("n", [2, 6])
async def test_needs_three_to_five_selfies(student_client, sid, verify, n):
    assert (await student_client.post(URL, files=_files(n))).status_code == 422
    assert verify.calls == []


async def test_photo_too_large_is_413(student_client, sid, verify, monkeypatch):
    monkeypatch.setattr(settings, "FACE_ENROL_MAX_IMAGE_BYTES", 100)
    assert (await student_client.post(URL, files=_files())).status_code == 413
    assert verify.calls == []


async def test_model_not_loaded_is_503(student_client, sid, monkeypatch):
    monkeypatch.setattr(app.state, "face_app", None, raising=False)
    assert (await student_client.post(URL, files=_files())).status_code == 503


async def test_student_only(lecturer_client, admin_client, users):
    for c in (lecturer_client, admin_client):
        assert (await c.get(URL)).status_code == 403
        assert (await c.post(URL, files=_files())).status_code == 403


# ── real models on generated card photos ─────────────────────────────────────

@pytest.fixture(scope="module")
def real_face():
    from insightface.app import FaceAnalysis

    from tests import card_images

    fa = FaceAnalysis(name=settings.INSIGHTFACE_MODEL, providers=["CPUExecutionProvider"])
    fa.prepare(ctx_id=-1, det_size=(640, 640))
    people = card_images.people(fa)
    return fa, card_images, people


def _real_files(card_images, selfies, card):
    files = [("selfies", (f"s{i}.png", s, "image/png")) for i, s in enumerate(selfies)]
    return files + [("card", ("card.png", card, "image/png"))]


@pytest.mark.face
async def test_real_genuine_card_auto_approves(student_client, sid, real_face, monkeypatch, db_session):
    fa, card_images, people = real_face
    monkeypatch.setattr(app.state, "face_app", fa, raising=False)
    card = card_images.card_photo(people[0], name="TEST STUDENT", matric="S0000001")
    resp = await student_client.post(URL, files=_real_files(card_images, card_images.selfies(people[0]), card))
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "active"
    assert await _count(db_session, FaceEmbedding, FaceEmbedding.student_id == sid) == 1
    assert await _count(db_session, FaceEnrolmentImage) == 0


@pytest.mark.face
async def test_real_someone_elses_card_goes_to_review(student_client, sid, real_face, monkeypatch, db_session):
    fa, card_images, people = real_face
    monkeypatch.setattr(app.state, "face_app", fa, raising=False)
    card = card_images.card_photo(people[1], name="TEST STUDENT", matric="S0000001")
    resp = await student_client.post(URL, files=_real_files(card_images, card_images.selfies(people[0]), card))
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending_review"
    [enrolment] = await _enrolments(db_session, sid)
    assert enrolment.check_reasons == ["face_mismatch"]
    assert await _count(db_session, FaceEmbedding) == 0
