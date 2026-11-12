"""T23c: admin accounts show each student's face enrolment status, including a submission waiting for review (FR-115, FR-117)."""
import pytest
from sqlalchemy import event, select

from app.core.database import engine
from app.models.face import FaceEmbedding
from app.models.face_enrolment import FaceEnrolment
from app.models.user import Student, User
from app.services.face_enrolment_service import enrolment_status, enrolment_statuses

pytestmark = pytest.mark.db


async def _student_id(db_session, user_id: int) -> int:
    return (await db_session.execute(
        select(Student.id).where(Student.user_id == user_id))).scalar_one()


async def _face_status(admin_client) -> dict[str, str | None]:
    resp = await admin_client.get("/admin/users", params={"limit": 100})
    assert resp.status_code == 200
    return {u["email"]: u["face_status"] for u in resp.json()["items"]}


async def test_list_shows_each_face_status(admin_client, classroom, users, db_session):
    pending, rejected, active = classroom["student_ids"]
    db_session.add_all([
        FaceEnrolment(student_id=pending, status="pending_review", check_reasons=["face_mismatch"]),
        FaceEnrolment(student_id=rejected, status="rejected", check_reasons=[], reason="Blurry"),
        FaceEmbedding(student_id=active, embedding=[0.1] * 512),
        FaceEnrolment(student_id=active, status="active", check_reasons=[]),
    ])
    blank = User(email="student9@siswa.um.edu.my", role="student", name="Student 9", status="active")
    db_session.add(blank)
    await db_session.flush()
    db_session.add(Student(user_id=blank.id, matric_no="S0000009", programme="Software Engineering"))
    await db_session.commit()

    faces = await _face_status(admin_client)
    assert faces[users["student"].email] == "pending_review"
    assert faces["student2@siswa.um.edu.my"] == "rejected"
    assert faces["student3@siswa.um.edu.my"] == "active"
    assert faces["student9@siswa.um.edu.my"] == "not_enrolled"
    assert faces[users["admin"].email] is None
    assert faces[users["lecturer"].email] is None


async def test_latest_non_blocked_submission_counts(admin_client, users, db_session):
    sid = await _student_id(db_session, users["student"].id)
    db_session.add(FaceEnrolment(student_id=sid, status="rejected", check_reasons=[], reason="Blurry"))
    await db_session.commit()
    assert (await _face_status(admin_client))[users["student"].email] == "rejected"

    db_session.add(FaceEnrolment(student_id=sid, status="blocked", check_reasons=["card_unreadable"]))
    await db_session.commit()
    assert (await _face_status(admin_client))[users["student"].email] == "rejected"

    db_session.add(FaceEnrolment(student_id=sid, status="pending_review", check_reasons=["face_mismatch"]))
    await db_session.commit()
    assert (await _face_status(admin_client))[users["student"].email] == "pending_review"

    db_session.add(FaceEmbedding(student_id=sid, embedding=[0.1] * 512))
    await db_session.commit()
    assert (await _face_status(admin_client))[users["student"].email] == "active"


async def test_reset_or_withdrawn_submission_is_not_enrolled(admin_client, users, db_session):
    sid = await _student_id(db_session, users["student"].id)
    db_session.add(FaceEnrolment(student_id=sid, status="reset", check_reasons=[]))
    await db_session.commit()
    assert (await _face_status(admin_client))[users["student"].email] == "not_enrolled"


async def test_batch_matches_enrolment_status(users, db_session):
    cases = []

    users_created = []
    for i in range(6):
        user = User(email=f"parity{i}@x.my", role="student", name=f"Parity {i}", status="active")
        db_session.add(user)
        users_created.append(user)
    await db_session.flush()
    students = [Student(user_id=u.id, matric_no=f"P000000{i}") for i, u in enumerate(users_created)]
    db_session.add_all(students)
    await db_session.flush()

    for i, student in enumerate(students):
        if i == 1:
            db_session.add(FaceEnrolment(student_id=student.id, status="pending_review", check_reasons=[]))
        elif i == 2:
            db_session.add(FaceEnrolment(student_id=student.id, status="rejected", check_reasons=[]))
        elif i == 3:
            db_session.add(FaceEnrolment(student_id=student.id, status="rejected", check_reasons=[]))
            await db_session.flush()
            db_session.add(FaceEnrolment(student_id=student.id, status="blocked", check_reasons=[]))
        elif i == 4:
            db_session.add(FaceEmbedding(student_id=student.id, embedding=[0.1] * 512))
            db_session.add(FaceEnrolment(student_id=student.id, status="active", check_reasons=[]))
        elif i == 5:
            db_session.add(FaceEmbedding(student_id=student.id, embedding=[0.1] * 512))
        cases.append((student.id, student))

    await db_session.commit()

    sids = [sid for sid, _ in cases]
    batch = await enrolment_statuses(db_session, sids)
    assert set(batch) == set(sids)
    for sid, _ in cases:
        assert batch[sid] == (await enrolment_status(db_session, sid)).status


async def test_user_detail_has_face_status(admin_client, users, db_session):
    sid = await _student_id(db_session, users["student"].id)
    db_session.add(FaceEnrolment(student_id=sid, status="pending_review", check_reasons=["face_mismatch"]))
    await db_session.commit()

    body = (await admin_client.get(f"/admin/users/{users['student'].id}")).json()
    assert body["face_status"] == "pending_review"
    assert body["face_enrolled"] is False

    body = (await admin_client.get(f"/admin/users/{users['lecturer'].id}")).json()
    assert body["face_status"] is None


async def test_list_reads_face_statuses_in_one_query(admin_client, classroom, users, db_session):
    for sid in classroom["student_ids"]:
        db_session.add(FaceEnrolment(student_id=sid, status="pending_review", check_reasons=["face_mismatch"]))
    await db_session.commit()

    seen = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    try:
        resp = await admin_client.get("/admin/users", params={"limit": 100})
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _record)

    assert resp.status_code == 200
    items = resp.json()["items"]
    three = [u for u in items if u["email"] in (users["student"].email,
                                                "student2@siswa.um.edu.my", "student3@siswa.um.edu.my")]
    assert len(three) == 3
    assert all(u["face_status"] == "pending_review" for u in three)
    # The 3 students must not cost 3 queries (the per-user embedding query says face_embeddings, not face_enrolments)
    assert sum("face_enrolments" in s for s in seen) == 1


async def test_empty_page_needs_no_face_query(db_session):
    assert await enrolment_statuses(db_session, []) == {}
