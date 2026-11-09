"""T15: matric card verification service (FR-111) — face match, local OCR, photo quality.

Card photos are generated (tests/card_images.py): PIL-drawn card text + a face from
InsightFace's bundled sample photo. The `face` tests need insightface, buffalo_sc and
rapidocr; conftest skips them when those aren't installed.
"""
import numpy as np
import pytest

from app.core.config import settings
from app.services import face_verification as fv
from app.services.face_verification import OcrLine

MATRIC, NAME = "23004976", "Tan Yew Sing"


# ── OCR text parsing (no models needed) ──────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("23004976", ["23004976"]),
    ("MATRIC NO: 23004976", ["23004976"]),
    ("NO23004976", ["23004976"]),            # label stuck to the number
    ("23OO4976", ["23004976"]),              # O read for 0
    ("2300497I", ["23004971"]),              # I read for 1
    ("WIF180012", ["WIF180012"]),            # older UM format
    ("UNIVERSITI MALAYA", []),
    ("FACULTY OF COMPUTER SCIENCE", []),
    ("2023/2024", []),
])
def test_matric_candidates(text, expected):
    assert fv._matric_candidates(text) == expected


def test_read_card_matches_matric_and_name_without_spaces():
    lines = [OcrLine("UNIVERSITIMALAYA", 0.98), OcrLine("TANYEW SING", 0.95), OcrLine("23004976", 0.99)]
    card = fv.read_card(lines, MATRIC, NAME)
    assert (card.matric, card.matric_match, card.name_match) == (MATRIC, True, True)
    assert card.matric_confidence == 0.99 and card.name_score == 1.0


def test_read_card_wrong_matric_and_name():
    lines = [OcrLine("LIM AH KOW", 0.95), OcrLine("23009999", 0.99)]
    card = fv.read_card(lines, MATRIC, NAME)
    assert card.matric == "23009999"
    assert not card.matric_match and not card.name_match


def test_read_card_prefers_the_accounts_number_over_a_surer_other_number():
    lines = [OcrLine("12345678", 0.999), OcrLine("23004976", 0.90)]
    card = fv.read_card(lines, MATRIC, NAME)
    assert card.matric == MATRIC and card.matric_match and card.matric_confidence == 0.9


def test_read_card_nothing_read():
    card = fv.read_card([], MATRIC, NAME)
    assert card.matric is None and not card.matric_match and card.name_score == 0.0


def test_quality_problems_only_block_when_matric_is_not_read_confidently():
    grey = np.full((480, 640, 3), 120, np.uint8)       # no card, no detail → several reasons
    unread = fv.check_quality(grey, [], card_face_found=False)
    assert unread.reasons and unread.blocking
    unsure = fv.check_quality(grey, [OcrLine("23004976", settings.CARD_OCR_MIN_CONFIDENCE - 0.1)], False)
    assert unsure.blocking
    sure = fv.check_quality(grey, [OcrLine("23004976", settings.CARD_OCR_MIN_CONFIDENCE)], False)
    assert sure.reasons == unread.reasons and not sure.blocking


def test_every_reason_has_a_retake_message():
    for reason, message in fv.QUALITY_MESSAGES.items():
        assert "retake" in message.lower(), reason
    q = fv.QualityResult(reasons=["glare", "blurry"], blocking=True)
    assert q.message == fv.QUALITY_MESSAGES["glare"]
    assert fv.QualityResult(reasons=[], blocking=False).message is None


# ── generated card photos (InsightFace + RapidOCR) ───────────────────────────

@pytest.fixture(scope="module")
def face_app():
    from insightface.app import FaceAnalysis

    fa = FaceAnalysis(name=settings.INSIGHTFACE_MODEL, providers=["CPUExecutionProvider"])
    fa.prepare(ctx_id=-1, det_size=(640, 640))
    return fa


@pytest.fixture(scope="module")
def imgs(face_app):
    from tests import card_images

    people = card_images.people(face_app)
    assert len(people) >= 2
    return card_images, people, card_images.selfies(people[0])


def _verify(face_app, imgs, person=0, **card_kwargs):
    card_images, people, selfies = imgs
    card = card_images.card_photo(people[person] if person is not None else None, **card_kwargs)
    return fv.verify_card(face_app, selfies, card, MATRIC, NAME)


@pytest.mark.face
def test_match_auto_approves(face_app, imgs):
    r = _verify(face_app, imgs)
    assert r.quality.reasons == [] and not r.quality.blocking
    assert r.face.passed and r.face.score >= settings.CARD_FACE_MATCH_THRESHOLD
    assert r.card.matric == MATRIC and r.card.matric_match and r.card.name_match
    assert r.passed


@pytest.mark.face
def test_wrong_face_is_not_approved(face_app, imgs):
    r = _verify(face_app, imgs, person=1)
    assert r.card.matric_match and not r.quality.blocking   # the card itself is fine
    assert not r.face.passed and r.face.score < settings.CARD_FACE_MATCH_THRESHOLD
    assert not r.passed


@pytest.mark.face
def test_wrong_matric_number_is_not_approved(face_app, imgs):
    r = _verify(face_app, imgs, matric="23009999")
    assert r.face.passed and not r.quality.blocking
    assert r.card.matric == "23009999" and not r.card.matric_match
    assert not r.passed


@pytest.mark.face
def test_unreadable_card_is_blocked(face_app, imgs):
    r = _verify(face_app, imgs, blur=8)
    assert r.card.matric is None
    assert "blurry" in r.quality.reasons and r.quality.blocking
    assert not r.passed


@pytest.mark.face
def test_blurry_but_readable_card_is_flagged_not_blocked(face_app, imgs):
    r = _verify(face_app, imgs, blur=4)
    assert "blurry" in r.quality.reasons
    assert r.card.matric_match and not r.quality.blocking


@pytest.mark.face
def test_glare_present_but_text_readable_is_accepted(face_app, imgs):
    r = _verify(face_app, imgs, glare="corner")
    assert "glare" in r.quality.reasons
    assert r.quality.scores["glare_fraction"] > settings.CARD_GLARE_MAX_FRACTION
    assert not r.quality.blocking and r.passed


@pytest.mark.face
def test_glare_over_the_details_blocks_with_the_glare_message(face_app, imgs):
    r = _verify(face_app, imgs, glare="text")
    assert r.quality.reasons == ["glare"] and r.quality.blocking
    assert r.quality.message.startswith("Glare is covering your card details")
    assert not r.passed


@pytest.mark.face
def test_dark_card_reports_too_dark_first(face_app, imgs):
    r = _verify(face_app, imgs, brightness=0.2)
    assert r.quality.reasons[0] == "too_dark"
    assert r.quality.scores["brightness"] <= settings.CARD_DARK_MAX_MEAN
    assert r.quality.message == fv.QUALITY_MESSAGES["too_dark"]


@pytest.mark.face
def test_dark_and_unreadable_card_is_blocked(face_app, imgs):
    r = _verify(face_app, imgs, brightness=0.2, blur=8)
    assert r.quality.reasons[0] == "too_dark" and r.quality.blocking


@pytest.mark.face
def test_card_too_small_and_angled(face_app, imgs):
    small = _verify(face_app, imgs, scale=0.4)
    assert small.quality.reasons == ["card_too_small"]
    angled = _verify(face_app, imgs, angle=25)
    assert angled.quality.reasons == ["angled"]
    straight_enough = _verify(face_app, imgs, angle=5)
    assert straight_enough.quality.reasons == []


@pytest.mark.face
def test_no_face_on_card(face_app, imgs):
    r = _verify(face_app, imgs, person=None)
    assert r.quality.reasons == ["no_face_on_card"]
    assert r.face.reason == "no_face_on_card" and r.face.score is None
    assert not r.passed


@pytest.mark.face
def test_not_an_image_is_blocked(face_app, imgs):
    _, _, selfies = imgs
    r = fv.verify_card(face_app, selfies, b"not an image", MATRIC, NAME)
    assert r.quality.reasons == ["no_card_found"] and r.quality.blocking and not r.passed


@pytest.mark.face
def test_face_threshold_comes_from_config(face_app, imgs, monkeypatch):
    monkeypatch.setattr(settings, "CARD_FACE_MATCH_THRESHOLD", 0.999)
    r = _verify(face_app, imgs)
    assert not r.face.passed and not r.passed
