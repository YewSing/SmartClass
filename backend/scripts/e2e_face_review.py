"""
Test data for the face verification queue E2E flows (T19): one pending face enrolment.

    python scripts/e2e_face_review.py seed  --student student8@example.com
    python scripts/e2e_face_review.py clean --student student8@example.com

`seed` gives the student current PDPA consent and a `pending_review` submission with generated
placeholder photos (no real faces or cards: PDPA) and a dummy embedding, so a lecturer of one of the
student's courses can approve or reject it. `clean` removes the student's face data, submissions and
consent records. Both reset that student's face enrolment, so use a Moodle seed test account only.
The student must exist in SmartClass already (a Moodle sync or login creates them).

Run from backend/ against the dev database (DATABASE_URL in .env).
"""
import argparse
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.consent import FaceConsent
from app.models.face import FaceEmbedding
from app.models.face_enrolment import FaceEnrolment, FaceEnrolmentImage
from app.models.user import Student, User

# A unit vector: approvable, but too unlike any real face embedding to ever match one.
DUMMY_EMBEDDING = [1.0] + [0.0] * 511


def _png(size: tuple[int, int], fill: str, label: str) -> bytes:
    img = Image.new("RGB", size, fill)
    draw = ImageDraw.Draw(img)
    w, h = size
    if w < h:  # selfie: a simple head-and-shoulders outline
        draw.ellipse((w * 0.3, h * 0.2, w * 0.7, h * 0.55), outline="black", width=4)
        draw.arc((w * 0.15, h * 0.6, w * 0.85, h * 1.1), 180, 360, fill="black", width=4)
    else:      # card: a photo box and text lines
        draw.rectangle((w * 0.05, h * 0.2, w * 0.3, h * 0.8), outline="black", width=4)
        for i in range(3):
            y = h * (0.3 + 0.15 * i)
            draw.line((w * 0.38, y, w * 0.9, y), fill="black", width=6)
    draw.text((10, 10), label, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def clean(db: AsyncSession, student_id: int) -> None:
    await db.execute(delete(FaceEmbedding).where(FaceEmbedding.student_id == student_id))
    await db.execute(delete(FaceEnrolment).where(FaceEnrolment.student_id == student_id))
    await db.execute(delete(FaceConsent).where(FaceConsent.student_id == student_id))
    await db.commit()


async def seed(db: AsyncSession, student_id: int) -> int:
    """A fresh pending submission for the student; returns its id."""
    await clean(db, student_id)
    student = await db.get(Student, student_id)
    db.add(FaceConsent(student_id=student_id, version=settings.FACE_CONSENT_VERSION))
    enrolment = FaceEnrolment(
        student_id=student_id, status="pending_review", check_reasons=["matric_mismatch", "glare"],
        face_score=0.52, ocr_matric="23009999", ocr_matric_confidence=0.91, name_score=1.0,
        quality_scores={"glare_fraction": 0.08}, ocr_lines=["UNIVERSITI MALAYA", "23009999"],
        embedding=DUMMY_EMBEDDING,
    )
    db.add(enrolment)
    await db.flush()
    colours = ["#cfe3ff", "#d8f5dd", "#ffe7c7"]
    db.add_all([
        FaceEnrolmentImage(enrolment_id=enrolment.id, kind="selfie", position=i, content_type="image/png",
                           data=_png((300, 400), colours[i], f"E2E selfie {i + 1}"))
        for i in range(3)
    ])
    db.add(FaceEnrolmentImage(enrolment_id=enrolment.id, kind="card", position=0, content_type="image/png",
                              data=_png((640, 404), "#f2f2f2", f"E2E card {student.matric_no}")))
    await db.commit()
    return enrolment.id


async def _main(action: str, email: str) -> None:
    async with AsyncSessionLocal() as db:
        student = (await db.execute(
            select(Student).join(User, User.id == Student.user_id).where(User.email == email)
        )).scalar_one_or_none()
        if student is None:
            sys.exit(f"No SmartClass student with email {email}. Sync Moodle or sign them in once first.")
        if action == "seed":
            print(f"pending submission {await seed(db, student.id)} for {email}")
        else:
            await clean(db, student.id)
            print(f"face enrolment data removed for {email}")
    await engine.dispose()  # before the loop closes, or Windows prints "Event loop is closed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["seed", "clean"])
    parser.add_argument("--student", required=True, help="the student's SmartClass email")
    args = parser.parse_args()
    asyncio.run(_main(args.action, args.student))
