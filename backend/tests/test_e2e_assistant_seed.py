"""T91: the E2E seed script gives the lecturer assistant flow a decidable material + trends."""
import pytest
from sqlalchemy import func, select

from app.models.ai_chat import ChatSession
from app.models.class_ import ClassOccurrence, Course
from app.models.knowledge import EMBEDDING_DIM, KbMaterial
from app.models.user import Lecturer, Student, User
from scripts.e2e_assistant import MATERIAL_TITLE, STUDENT_EMAILS, seed, teardown

pytestmark = pytest.mark.db

VEC = [1.0] + [0.0] * (EMBEDDING_DIM - 1)


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    async def embed_passages(texts):
        return [VEC for _ in texts]

    monkeypatch.setattr("app.services.kb.ingest.embed_passages", embed_passages)


async def _setup_course_and_students(db, users) -> int:
    course = Course(code="WIF3001", name="Software Testing")
    db.add(course)
    await db.flush()
    lecturer_id = await db.scalar(select(Lecturer.id).where(Lecturer.user_id == users["lecturer"].id))
    db.add(ClassOccurrence(course_id=course.id, type="LECTURE", day_of_week="Mon",
                           start_time="08:00", end_time="10:00", lecturer_id=lecturer_id))
    for i, email in enumerate(STUDENT_EMAILS, start=1):
        user = User(email=email, password_hash="x", role="student", name=f"E2E Student {i}",
                    status="active")
        db.add(user)
        await db.flush()
        db.add(Student(user_id=user.id, matric_no=f"S00000{i}"))
    await db.commit()
    return course.id


async def test_seeded_material_and_trends_are_visible(lecturer_client, users, db_session):
    course_id = await _setup_course_and_students(db_session, users)
    await seed(db_session, "WIF3001")

    materials = (await lecturer_client.get(f"/kb/courses/{course_id}/materials")).json()
    assert len(materials) == 1
    assert materials[0]["status"] == "indexed" and materials[0]["title"] == MATERIAL_TITLE

    trends = (await lecturer_client.get(f"/lecturer/assistant/trends/{course_id}")).json()
    assert {t["topic"] for t in trends["most_asked_topics"]} == {
        "Boundary value analysis", "Equivalence partitioning",
    }
    assert [m["title"] for m in trends["most_cited_materials"]] == [MATERIAL_TITLE]
    assert [t["topic"] for t in trends["topics_materials_dont_cover"]] == ["quantum entanglement"]


async def test_seed_is_idempotent_and_teardown_removes_everything(lecturer_client, users, db_session):
    course_id = await _setup_course_and_students(db_session, users)
    await seed(db_session, "WIF3001")
    await seed(db_session, "WIF3001")  # re-seeding keeps one material and one set of chats

    db_session.expire_all()
    material_count = await db_session.scalar(
        select(func.count()).select_from(KbMaterial).where(KbMaterial.course_id == course_id))
    assert material_count == 1

    await teardown(db_session, "WIF3001")

    db_session.expire_all()
    assert (await lecturer_client.get(f"/kb/courses/{course_id}/materials")).json() == []
    sessions = (await db_session.execute(
        select(ChatSession).where(ChatSession.course_id == course_id))).scalars().all()
    assert sessions == []


async def test_teardown_keeps_the_students_own_chats(lecturer_client, users, db_session):
    # 2026-11-13: teardown deleted every WIF3001 chat of student1-3, wiping Yew Sing's own test
    # chats on the dev DB. Only the chats the seed made may go.
    course_id = await _setup_course_and_students(db_session, users)
    student_id = await db_session.scalar(
        select(Student.id).join(User, User.id == Student.user_id).where(User.email == STUDENT_EMAILS[0]))
    db_session.add(ChatSession(student_id=student_id, course_id=course_id, title="my own chat"))
    await db_session.commit()

    await seed(db_session, "WIF3001")
    await teardown(db_session, "WIF3001")

    db_session.expire_all()
    titles = (await db_session.execute(
        select(ChatSession.title).where(ChatSession.course_id == course_id))).scalars().all()
    assert titles == ["my own chat"]
