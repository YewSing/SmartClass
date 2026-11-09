"""T19: the E2E seed script gives the lecturer flows a real, decidable pending submission."""
import io

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.models.consent import FaceConsent
from app.models.face import FaceEmbedding
from app.models.face_enrolment import FaceEnrolment, FaceEnrolmentImage
from scripts.e2e_face_review import clean, seed

pytestmark = pytest.mark.db

URL = "/face-verification"


async def _count(db, model, *where):
    db.expire_all()
    return await db.scalar(select(func.count()).select_from(model).where(*where))


async def test_seeded_submission_is_listed_with_real_photos_and_can_be_approved(lecturer_client, classroom, db_session):
    student_id = classroom["student_ids"][0]
    sub_id = await seed(db_session, student_id)

    [item] = (await lecturer_client.get(f"{URL}/pending")).json()
    assert item["id"] == sub_id
    assert [i["kind"] for i in item["images"]] == ["selfie", "selfie", "selfie", "card"]
    assert item["check_reasons"] == ["matric_mismatch", "glare"]
    photo = await lecturer_client.get(item["images"][0]["url"])
    assert photo.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(photo.content)).size == (300, 400)

    assert (await lecturer_client.post(f"{URL}/{sub_id}/approve")).status_code == 204
    assert await _count(db_session, FaceEmbedding, FaceEmbedding.student_id == student_id) == 1


async def test_seeding_again_replaces_the_old_submission_and_clean_removes_everything(classroom, db_session):
    student_id = classroom["student_ids"][0]
    await seed(db_session, student_id)
    second = await seed(db_session, student_id)
    assert await _count(db_session, FaceEnrolment, FaceEnrolment.student_id == student_id) == 1
    assert await _count(db_session, FaceConsent, FaceConsent.student_id == student_id) == 1
    assert await _count(db_session, FaceEnrolmentImage, FaceEnrolmentImage.enrolment_id == second) == 4

    db_session.add(FaceEmbedding(student_id=student_id, embedding=[1.0] + [0.0] * 511))
    await db_session.commit()
    await clean(db_session, student_id)
    for model in (FaceEnrolment, FaceConsent, FaceEmbedding):
        assert await _count(db_session, model, model.student_id == student_id) == 0
