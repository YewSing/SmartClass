"""T18b: face enrolment fixes from the T14–T18 checkpoint review.

Selfies must each show a face and look alike (no proxy enrolment with a friend's selfies), the
card must be a UM card, enrolment needs the current consent notice, stored photo types come from
the bytes, the card's matric number is cleared after a decision, and face data stored without
consent is deleted by a migration.
"""
import importlib.util
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.main import app
from app.models.consent import FaceConsent
from app.models.face import FaceEmbedding
from app.models.face_enrolment import FaceEnrolment, FaceEnrolmentImage
from app.models.user import Student
from app.routers.student_face import _image_content_type
from app.services import face_verification as fv
from app.services.face_verification import OcrLine
from tests.test_face_enrolment import _files, _result

URL = "/student/me/face-enrolment"


# ── UM card text (no models) ─────────────────────────────────────────────────

@pytest.mark.parametrize("lines, um", [
    (["UNIVERSITI MALAYA", "TAN YEW SING"], True),
    (["UNIVERSITIMALAYA"], True),                       # OCR drops spaces
    (["UNIVERSITY OF", "MALAYA"], True),                # English name split over two lines
    (["Universiti Malaya"], True),
    (["RAPID KL", "TOUCH N GO", "TAN YEW SING", "23004976"], False),
    # T23a: any one UM word counts, so UNIVERSITI alone does; another university's card is
    # still stopped by the matric check (test_another_universitys_card_is_not_auto_approved).
    (["UNIVERSITI TEKNOLOGI MALAYSIA"], True),
    (["MALAYSIA AIRLINES"], False),                     # MALAYSIA is 2 edits from MALAYA
    ([], False),
])
def test_um_card_text(lines, um):
    card = fv.read_card([OcrLine(t, 0.95) for t in lines], "23004976", "Tan Yew Sing")
    assert card.um_card is um


def test_um_card_words_come_from_config(monkeypatch):
    monkeypatch.setattr(settings, "CARD_UM_KEYWORDS", "TESTUNI")
    assert fv.read_card([OcrLine("TESTUNI", 0.9)], None, None).um_card
    assert not fv.read_card([OcrLine("UNIVERSITI MALAYA", 0.9)], None, None).um_card


def test_um_card_extra_pattern_comes_from_config(monkeypatch):
    monkeypatch.setattr(settings, "CARD_UM_KEYWORDS", "")
    assert not fv.read_card([OcrLine("TEST UNI", 0.9)], None, None).um_card
    monkeypatch.setattr(settings, "CARD_UM_TEXT_REGEX", "TESTUNI")
    assert fv.read_card([OcrLine("TEST UNI", 0.9)], None, None).um_card


# Real OCR of the MySiswa card (T21 photos): words split over lines, in either order, misread.
@pytest.mark.parametrize("lines", [
    ["UNIVERSITI", "MALAYA"],
    ["MALAYA", "UNIVERSITI"],
    ["UNTVERSIT", "YONG YEW SING"],      # misread, and MALAYA not read at all
    ["RHB", "MySISWA", "YONE VEW SNe"],  # read neither, but read MySISWA
    ["MIyEISWA"],
    ["MiySISWA"],
    ["UNIVERSITY OF", "MALAYA"],
])
def test_um_card_text_survives_real_ocr_splits_and_misreads(lines):
    assert fv.read_card([OcrLine(t, 0.9) for t in lines], None, None).um_card


@pytest.mark.parametrize("lines", [
    ["MYRAPID", "TOUCH N GO", "TAN YEW SING"],
    ["MYDEBIT", "VISA"],
    ["MALAYSIA"],
    ["UNIVERSAL STUDIOS"],
])
def test_um_card_text_rejects_look_alikes(lines):
    assert not fv.read_card([OcrLine(t, 0.9) for t in lines], None, None).um_card


def test_another_universitys_card_is_not_auto_approved():
    lines = [OcrLine("UNIVERSITI TEKNOLOGI MALAYSIA", 0.95), OcrLine("TAN YEW SING", 0.95),
             OcrLine("22001234", 0.98)]
    card = fv.read_card(lines, "23004976", "Tan Yew Sing")
    assert card.um_card and card.name_match
    assert card.matric == "22001234" and not card.matric_match


def test_a_transport_card_without_a_matric_number_is_not_auto_approved():
    # A myrapid card with the student's name and photo has no matric number to match.
    lines = [OcrLine("myrapid", 0.97), OcrLine("TOUCH N GO", 0.95), OcrLine("TAN YEW SING", 0.96)]
    card = fv.read_card(lines, "23004976", "Tan Yew Sing")
    assert card.matric is None and not card.matric_match and not card.um_card


def test_a_non_um_card_is_not_auto_approved():
    r = _result(um_card=False)
    assert not r.passed
    assert _result().passed


# ── selfie consistency (no models: a fake face detector) ─────────────────────

def _unit(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=512)
    return v / np.linalg.norm(v)


class _FakeFaceApp:
    """Returns one face per image; the image's top-left pixel says whose (0 = no face)."""

    def __init__(self, people: dict[int, np.ndarray]):
        self.people = people

    def get(self, img):
        who = int(img[0, 0, 0])
        if who == 0:
            return []
        return [SimpleNamespace(normed_embedding=self.people[who], bbox=[0, 0, 10, 10])]


def _img(who: int) -> np.ndarray:
    img = np.zeros((20, 20, 3), np.uint8)
    img[0, 0, 0] = who
    return img


def _near(v: np.ndarray, seed: int, noise: float = 0.2) -> np.ndarray:
    w = v + noise * _unit(seed)
    return w / np.linalg.norm(w)


def test_same_person_selfies_are_consistent():
    me = _unit(1)
    fa = _FakeFaceApp({1: me, 2: _near(me, 2), 3: _near(me, 3), 9: me})
    m = fv.match_faces(fa, [_img(1), _img(2), _img(3)], _img(9))
    assert m.selfie_faces == 3 and m.selfie_count == 3
    assert m.selfie_consistency >= settings.FACE_SELFIE_CONSISTENCY_THRESHOLD
    assert m.selfies_consistent and m.passed


def test_a_friends_selfie_makes_the_set_inconsistent():
    me, friend = _unit(1), _unit(7)
    fa = _FakeFaceApp({1: me, 2: _near(me, 2), 3: friend, 9: me})
    m = fv.match_faces(fa, [_img(1), _img(2), _img(3)], _img(9))
    assert m.selfie_consistency < settings.FACE_SELFIE_CONSISTENCY_THRESHOLD
    assert not m.selfies_consistent


def test_a_selfie_without_a_face_is_counted():
    me = _unit(1)
    fa = _FakeFaceApp({1: me, 2: _near(me, 2), 3: _near(me, 3), 9: me})
    m = fv.match_faces(fa, [_img(1), _img(2), _img(3), _img(0)], _img(9))
    assert m.selfie_faces == 3 and m.selfie_count == 4
    assert not m.selfies_consistent  # every selfie must contain a face


def test_consistency_is_measured_even_without_a_card_face():
    me = _unit(1)
    fa = _FakeFaceApp({1: me, 2: _near(me, 2), 3: _near(me, 3)})
    m = fv.match_faces(fa, [_img(1), _img(2), _img(3)], _img(0))
    assert m.reason == "no_face_on_card" and m.selfie_faces == 3 and m.selfies_consistent


def test_consistency_threshold_comes_from_config(monkeypatch):
    me = _unit(1)
    fa = _FakeFaceApp({1: me, 2: _near(me, 2), 3: _near(me, 3), 9: me})
    m = fv.match_faces(fa, [_img(1), _img(2), _img(3)], _img(9))
    monkeypatch.setattr(settings, "FACE_SELFIE_CONSISTENCY_THRESHOLD", 0.9999)
    assert not m.selfies_consistent


# ── photo type from bytes ────────────────────────────────────────────────────

def test_image_content_type_comes_from_the_bytes():
    img = np.zeros((8, 8, 3), np.uint8)
    assert _image_content_type(cv2.imencode(".jpg", img)[1].tobytes()) == "image/jpeg"
    assert _image_content_type(cv2.imencode(".png", img)[1].tobytes()) == "image/png"
    assert _image_content_type(cv2.imencode(".webp", img)[1].tobytes()) == "image/webp"
    assert _image_content_type(b"<html>not a photo</html>") == "application/octet-stream"


# ── endpoint (db) ────────────────────────────────────────────────────────────

@pytest.fixture
def verify(monkeypatch):
    class Fake:
        result = _result()
        calls: list = []

        def __call__(self, face_app, selfies, card, matric, name):
            self.calls.append(len(selfies))
            return self.result

    fake = Fake()
    fake.calls = []
    monkeypatch.setattr(app.state, "face_app", object(), raising=False)
    monkeypatch.setattr(fv, "verify_card", fake)
    return fake


@pytest.fixture
async def sid(users, db_session) -> int:
    student_id = await db_session.scalar(select(Student.id).where(Student.user_id == users["student"].id))
    db_session.add(FaceConsent(student_id=student_id, version=settings.FACE_CONSENT_VERSION))
    await db_session.commit()
    return student_id


async def _enrolments(db, student_id):
    db.expire_all()
    return (await db.execute(select(FaceEnrolment).where(FaceEnrolment.student_id == student_id)
                             .order_by(FaceEnrolment.id))).scalars().all()


async def _embeddings(db, student_id=None):
    db.expire_all()
    q = select(func.count()).select_from(FaceEmbedding)
    if student_id is not None:
        q = q.where(FaceEmbedding.student_id == student_id)
    return await db.scalar(q)


@pytest.mark.db
async def test_fewer_than_three_selfies_with_a_face_is_a_retake(student_client, sid, verify, db_session):
    verify.result = _result(selfie_faces=2, selfie_count=3)
    resp = await student_client.post(URL, files=_files(3))
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["reasons"] == ["no_face_in_selfies"]
    assert await _enrolments(db_session, sid) == [] and await _embeddings(db_session) == 0


@pytest.mark.db
async def test_a_selfie_without_a_face_goes_to_review(student_client, sid, verify, db_session):
    verify.result = _result(selfie_faces=3, selfie_count=4)
    resp = await student_client.post(URL, files=_files(4))
    assert resp.status_code == 201 and resp.json()["status"] == "pending_review"
    [enrolment] = await _enrolments(db_session, sid)
    assert "selfie_without_face" in enrolment.check_reasons
    assert await _embeddings(db_session) == 0


@pytest.mark.db
async def test_inconsistent_selfies_go_to_review(student_client, sid, verify, db_session):
    verify.result = _result(consistency=0.1)
    resp = await student_client.post(URL, files=_files(3))
    assert resp.status_code == 201 and resp.json()["status"] == "pending_review"
    [enrolment] = await _enrolments(db_session, sid)
    assert enrolment.check_reasons == ["selfies_inconsistent"]
    assert await _embeddings(db_session) == 0


@pytest.mark.db
async def test_a_card_without_um_text_goes_to_review(student_client, sid, verify, db_session):
    verify.result = _result(um_card=False)
    resp = await student_client.post(URL, files=_files(3))
    assert resp.status_code == 201 and resp.json()["status"] == "pending_review"
    [enrolment] = await _enrolments(db_session, sid)
    assert enrolment.check_reasons == ["not_um_card"]
    assert await _embeddings(db_session) == 0


@pytest.mark.db
async def test_enrolment_needs_the_current_consent_version(student_client, users, verify, db_session):
    student_id = await db_session.scalar(select(Student.id).where(Student.user_id == users["student"].id))
    db_session.add(FaceConsent(student_id=student_id, version="2020-01-old"))
    await db_session.commit()
    resp = await student_client.post(URL, files=_files(3))
    assert resp.status_code == 409 and "accept again" in resp.json()["detail"]
    assert verify.calls == [] and await _enrolments(db_session, student_id) == []


@pytest.mark.db
async def test_stored_photo_type_comes_from_the_bytes_not_the_client(student_client, sid, verify, db_session):
    verify.result = _result(matric=False)
    png = cv2.imencode(".png", np.zeros((40, 40, 3), np.uint8))[1].tobytes()
    files = [("selfies", (f"s{i}.jpg", png, "image/jpeg; " + "x" * 80)) for i in range(3)]
    files.append(("card", ("card.jpg", png, "text/html")))
    resp = await student_client.post(URL, files=files)
    assert resp.status_code == 201, resp.text  # an over-long client type no longer breaks the insert
    db_session.expire_all()
    types = (await db_session.execute(select(FaceEnrolmentImage.content_type))).scalars().all()
    assert types == ["image/png"] * 4


@pytest.mark.db
@pytest.mark.parametrize("decision", ["approve", "reject"])
async def test_card_matric_is_cleared_after_a_decision(
        student_client, admin_client, sid, verify, db_session, decision):
    verify.result = _result(matric=False)  # someone else's number read from the card
    assert (await student_client.post(URL, files=_files(3))).status_code == 201
    [enrolment] = await _enrolments(db_session, sid)
    assert enrolment.ocr_matric == "S0009999"

    body = {"reason": "Not your card"} if decision == "reject" else None
    resp = await admin_client.post(f"/face-verification/{enrolment.id}/{decision}", json=body)
    assert resp.status_code == 204, resp.text
    [enrolment] = await _enrolments(db_session, sid)
    assert enrolment.ocr_matric is None and enrolment.ocr_lines is None


@pytest.mark.db
async def test_review_photos_are_served_with_nosniff(student_client, admin_client, sid, verify, db_session):
    verify.result = _result(matric=False)
    assert (await student_client.post(URL, files=_files(3))).status_code == 201
    [item] = (await admin_client.get("/face-verification/pending")).json()
    image_id = (await db_session.scalar(select(FaceEnrolmentImage.id).limit(1)))
    resp = await admin_client.get(f"/face-verification/{item['id']}/images/{image_id}")
    assert resp.status_code == 200
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["content-type"] == "image/png"


# ── migration: face data without consent is deleted ──────────────────────────

def _migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "f7a8b9c0d1e2_delete_face_data_without_consent.py"
    spec = importlib.util.spec_from_file_location("t18b_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.db
async def test_migration_deletes_embeddings_of_students_without_active_consent(classroom, db_session):
    never, withdrawn, consented = classroom["student_ids"]
    # The withdrawn student accepted once and then withdrew; the consented one still agrees.
    db_session.add(FaceConsent(student_id=withdrawn, version=settings.FACE_CONSENT_VERSION,
                               withdrawn_at=datetime(2026, 11, 9, 12, 0)))
    db_session.add(FaceConsent(student_id=consented, version=settings.FACE_CONSENT_VERSION))
    for student_id in (never, never, withdrawn, consented):
        db_session.add(FaceEmbedding(student_id=student_id, embedding=[0.1] * 512))
    await db_session.commit()

    await db_session.execute(_migration().DELETE_WITHOUT_CONSENT)
    await db_session.commit()

    assert await _embeddings(db_session, never) == 0
    assert await _embeddings(db_session, withdrawn) == 0
    assert await _embeddings(db_session, consented) == 1


def test_migration_follows_the_enrolment_migration():
    m = _migration()
    assert (m.revision, m.down_revision) == ("f7a8b9c0d1e2", "e6f7a8b9c0d1")


# ── real models on generated photos ──────────────────────────────────────────

@pytest.fixture(scope="module")
def real_face():
    from insightface.app import FaceAnalysis

    from tests import card_images

    fa = FaceAnalysis(name=settings.INSIGHTFACE_MODEL, providers=["CPUExecutionProvider"])
    fa.prepare(ctx_id=-1, det_size=(640, 640))
    return fa, card_images, card_images.people(fa)


def _real_files(selfies, card):
    files = [("selfies", (f"s{i}.png", s, "image/png")) for i, s in enumerate(selfies)]
    return files + [("card", ("card.png", card, "image/png"))]


@pytest.mark.face
@pytest.mark.db
async def test_real_mixed_faces_are_not_auto_approved(student_client, sid, real_face, monkeypatch, db_session):
    fa, card_images, people = real_face
    monkeypatch.setattr(app.state, "face_app", fa, raising=False)
    mine, friends = card_images.selfies(people[0]), card_images.selfies(people[1])
    selfies = [mine[0], mine[1], friends[2]]  # a friend's face slipped in
    card = card_images.card_photo(people[0], name="TEST STUDENT", matric="S0000001")

    resp = await student_client.post(URL, files=_real_files(selfies, card))
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending_review"
    [enrolment] = await _enrolments(db_session, sid)
    assert "selfies_inconsistent" in enrolment.check_reasons
    assert await _embeddings(db_session) == 0


@pytest.mark.face
def test_real_same_person_selfies_pass_and_mixed_ones_do_not(real_face):
    fa, card_images, people = real_face
    decode = fv.decode_image
    mine = [decode(b) for b in card_images.selfies(people[0])]
    friend = decode(card_images.selfies(people[1])[0])
    card = decode(card_images.card_photo(people[0]))

    same = fv.match_faces(fa, mine, card)
    assert same.selfies_consistent, same.selfie_consistency
    mixed = fv.match_faces(fa, [mine[0], mine[1], friend], card)
    assert not mixed.selfies_consistent, mixed.selfie_consistency


@pytest.mark.face
@pytest.mark.db
async def test_real_card_without_um_text_is_not_auto_approved(student_client, sid, real_face, monkeypatch, db_session):
    fa, card_images, people = real_face
    monkeypatch.setattr(app.state, "face_app", fa, raising=False)
    card = card_images.card_photo(people[0], name="TEST STUDENT", matric="S0000001", header="RAPID KL TRANSIT")

    resp = await student_client.post(URL, files=_real_files(card_images.selfies(people[0]), card))
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending_review"
    [enrolment] = await _enrolments(db_session, sid)
    assert enrolment.check_reasons == ["not_um_card"]
    assert await _embeddings(db_session) == 0
