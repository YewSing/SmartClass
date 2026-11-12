"""Test data for the lecturer AI-assistant E2E flow (T91): one indexed material and
question trends for WIF3001.

    python scripts/e2e_assistant.py seed  --course WIF3001
    python scripts/e2e_assistant.py teardown --course WIF3001

`seed` indexes one small, synthetic (copyright-free) PDF into the course so the materials
list has an "Indexed" entry, and gives three Moodle-seeded students a question history so the
lecturer trends endpoint returns all three lists. `teardown` removes the synthetic material and
those students' chats again. No real course material or face data is touched.

Run from backend/ against the dev database (DATABASE_URL in .env).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select  # noqa: E402

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.models.ai_chat import ChatMessage, ChatSession  # noqa: E402
from app.models.class_ import Course  # noqa: E402
from app.models.knowledge import KbMaterial  # noqa: E402
from app.models.user import Student, User  # noqa: E402
from app.services.kb.ingest import MaterialMeta, ingest_file  # noqa: E402

MATERIAL_SOURCE_KEY = "e2e:testing-notes"
MATERIAL_TITLE = "Testing notes (E2E)"

# Three Moodle-seeded students (from backend/moodle/seed_config.json) enrolled in WIF3001.
STUDENT_EMAILS = ["student1@example.com", "student2@example.com", "student3@example.com"]

TOPICS = [
    # (topic, source_type, cited_material_title or None)
    ("Boundary value analysis", "course", MATERIAL_TITLE),
    ("Equivalence partitioning", "course", MATERIAL_TITLE),
    ("quantum entanglement", "general", None),
]


def _make_pdf(pages: list[str]) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


async def _course(db, code: str) -> Course:
    course = (await db.execute(select(Course).where(Course.code == code))).scalar_one_or_none()
    if course is None:
        sys.exit(f"No course {code}. Run scripts/seed.py first.")
    return course


async def seed(db, code: str) -> None:
    course = await _course(db, code)

    # 1. One synthetic indexed material (local source, so a Moodle sync never deletes it).
    meta = MaterialMeta(
        source_key=MATERIAL_SOURCE_KEY, source="local", file_name="testing-notes-e2e.pdf",
        title=MATERIAL_TITLE, section_name="Week 1",
    )
    material = await ingest_file(
        db, course.id, meta,
        _make_pdf([
            "Boundary value analysis tests the values at the edges of a range.",
            "Equivalence partitioning splits input values into classes that behave the same.",
        ]),
    )
    await db.commit()
    material_id = material.id

    # 2. Question history for three students, so every trend list has a topic at >= 3 students.
    students = (await db.execute(
        select(Student).join(User, User.id == Student.user_id).where(User.email.in_(STUDENT_EMAILS))
    )).scalars().all()
    for student in students:
        for topic, source, cited_title in TOPICS:
            session = ChatSession(student_id=student.id, course_id=course.id)
            db.add(session)
            await db.flush()
            db.add(ChatMessage(session_id=session.id, role="user", content=f"question about {topic}"))
            citations = [{"material_id": material_id, "title": cited_title}] if cited_title else []
            db.add(ChatMessage(session_id=session.id, role="assistant", content="answer",
                               source_type=source, topic=topic, citations=citations))
    await db.commit()
    print(f"seeded material + {len(students)} students' questions for {code}")


async def teardown(db, code: str) -> None:
    course = await _course(db, code)
    await db.execute(delete(KbMaterial).where(
        KbMaterial.course_id == course.id, KbMaterial.source_key == MATERIAL_SOURCE_KEY))
    student_ids = (await db.execute(
        select(Student.id).join(User, User.id == Student.user_id).where(User.email.in_(STUDENT_EMAILS))
    )).scalars().all()
    if student_ids:
        await db.execute(delete(ChatSession).where(
            ChatSession.course_id == course.id, ChatSession.student_id.in_(student_ids)))
    await db.commit()
    print(f"removed E2E material + chats for {code}")


async def _main(action: str, code: str) -> None:
    async with AsyncSessionLocal() as db:
        if action == "seed":
            await seed(db, code)
        else:
            await teardown(db, code)
    await engine.dispose()  # before the loop closes, or Windows prints "Event loop is closed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["seed", "teardown"])
    parser.add_argument("--course", default="WIF3001")
    args = parser.parse_args()
    asyncio.run(_main(args.action, args.course))
