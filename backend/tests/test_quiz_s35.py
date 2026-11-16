"""Tests for the S35 quiz endpoints: quiz list, draft sets, publish-to-classes,
manual questions, quick-add, attempts_allowed and review_visible.

No real LLM: quick-add monkeypatches `parse_quick_add` + `generate_questions`.
"""

import pytest

pytestmark = pytest.mark.db


def _question(course_id: int, qtype: str = "mcq", status: str = "approved",
              question: str = "Q?") -> dict:
    from app.models.quiz import QuizQuestion
    q = QuizQuestion(
        course_id=course_id, type=qtype, question=question, level="beginner",
        options=["a", "b"] if qtype == "mcq" else None,
        correct_answer="a" if qtype == "mcq" else None,
        suggested_answer="ideal" if qtype == "short_answer" else None,
        topic="t", status=status,
    )
    return q


async def _seed_questions(db_session, classroom, n=2, approved=True):
    ids = []
    for i in range(n):
        q = _question(classroom["course_id"],
                      status="approved" if approved else "draft",
                      question=f"q{i}")
        db_session.add(q)
        await db_session.flush()
        ids.append(q.id)
    await db_session.commit()
    return ids


# ── quiz list ────────────────────────────────────────────────────────────────

async def test_list_course_quizzes(lecturer_client, classroom, db_session):
    ids = await _seed_questions(db_session, classroom, n=2)
    resp = await lecturer_client.post("/lecturer/quizzes/draft", json={
        "question_ids": ids, "title": "Week 1 quiz",
    })
    assert resp.status_code == 201, resp.text

    resp = await lecturer_client.get(f"/lecturer/courses/{classroom['course_id']}/quizzes")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "draft"
    assert body[0]["title"] == "Week 1 quiz"
    assert body[0]["question_count"] == 2
    assert body[0]["attempts_allowed"] == 1
    assert body[0]["review_visible"] is True


async def test_list_course_quizzes_other_lecturer_403(other_lecturer_client, classroom):
    resp = await other_lecturer_client.get(f"/lecturer/courses/{classroom['course_id']}/quizzes")
    assert resp.status_code == 403, resp.text


# ── draft sets ───────────────────────────────────────────────────────────────

async def test_save_draft_and_update(lecturer_client, classroom, db_session):
    ids = await _seed_questions(db_session, classroom, n=1, approved=False)
    resp = await lecturer_client.post("/lecturer/quizzes/draft", json={
        "question_ids": ids, "title": "Draft set",
        "time_limit_minutes": 15, "attempts_allowed": 2, "review_visible": False,
    })
    assert resp.status_code == 201, resp.text
    quiz = resp.json()
    assert quiz["status"] == "draft"
    assert quiz["attempts_allowed"] == 2
    assert quiz["review_visible"] is False

    resp = await lecturer_client.put(f"/lecturer/quizzes/{quiz['id']}", json={
        "title": "Renamed", "time_limit_minutes": 20,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Renamed"
    assert resp.json()["time_limit_minutes"] == 20

    # published quizzes cannot be edited
    resp2 = await lecturer_client.post(f"/lecturer/quizzes/{quiz['id']}/publish", json={})
    assert resp2.status_code == 200
    resp = await lecturer_client.put(f"/lecturer/quizzes/{quiz['id']}", json={"title": "x"})
    assert resp.status_code == 409


async def test_publish_draft_to_multiple_courses(lecturer_client, classroom, db_session):
    ids = await _seed_questions(db_session, classroom, n=2)
    resp = await lecturer_client.post("/lecturer/quizzes/draft", json={
        "question_ids": ids, "title": "Multi",
    })
    quiz = resp.json()

    # the lecturer only teaches CS101 — CS202 belongs to the other lecturer
    resp = await lecturer_client.post(f"/lecturer/quizzes/{quiz['id']}/publish", json={
        "course_ids": [classroom["course_id"], 999999],
    })
    assert resp.status_code == 403, resp.text

    resp = await lecturer_client.post(f"/lecturer/quizzes/{quiz['id']}/publish", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "published"

    # double publish is 409
    resp = await lecturer_client.post(f"/lecturer/quizzes/{quiz['id']}/publish", json={})
    assert resp.status_code == 409


async def test_publish_draft_extra_course_must_be_taught(lecturer_client, classroom, db_session):
    """course_ids entries the lecturer doesn't teach are rejected; own-course entries
    don't create a self-clone."""
    from sqlalchemy import select
    from app.models.quiz import Quiz

    ids = await _seed_questions(db_session, classroom, n=1)
    resp = await lecturer_client.post("/lecturer/quizzes/draft", json={"question_ids": ids})
    quiz_id = resp.json()["id"]

    resp = await lecturer_client.post(f"/lecturer/quizzes/{quiz_id}/publish", json={
        "course_ids": [classroom["course_id"], 999999],
    })
    assert resp.status_code == 403, resp.text

    resp = await lecturer_client.post(f"/lecturer/quizzes/{quiz_id}/publish", json={
        "course_ids": [classroom["course_id"]],
    })
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1  # no self-clone
    quizzes = (await db_session.execute(select(Quiz))).scalars().all()
    assert len(quizzes) == 1


async def test_publish_request_multi_course_creates_clones(lecturer_client, classroom, db_session):
    """POST /lecturer/quizzes with course_ids clones the questions into each target."""
    from sqlalchemy import select
    from app.models.quiz import QuizQuestion

    # a second course taught by the same lecturer
    from app.models.class_ import Course
    course2 = Course(code="CS303", name="Third Course")
    db_session.add(course2)
    await db_session.flush()
    occ = __import__("app.models.class_", fromlist=["ClassOccurrence"]).ClassOccurrence(
        course_id=course2.id, type="LECTURE", day_of_week="Thu",
        start_time="09:00", end_time="11:00", room="CK1",
        lecturer_id=classroom["lecturer_id"])
    db_session.add(occ)
    await db_session.commit()

    ids = await _seed_questions(db_session, classroom, n=1)
    resp = await lecturer_client.post("/lecturer/quizzes", json={
        "question_ids": ids, "title": "Cloned", "course_ids": [course2.id],
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body) == 2
    assert {b["course_id"] for b in body} == {classroom["course_id"], course2.id}
    assert all(b["status"] == "published" for b in body)

    copies = (await db_session.execute(
        select(QuizQuestion).where(QuizQuestion.course_id == course2.id)
    )).scalars().all()
    assert len(copies) == 1
    assert copies[0].question == (await db_session.get(QuizQuestion, ids[0])).question


# ── manual question add ──────────────────────────────────────────────────────

async def test_create_manual_question(lecturer_client, other_lecturer_client,
                                      classroom, db_session):
    resp = await lecturer_client.post("/lecturer/quizzes/questions", json={
        "course_id": classroom["course_id"], "type": "mcq",
        "question": "Manual?", "options": ["a", "b", "c"], "correct_answer": "b",
        "level": "beginner", "topic": "manual",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "draft"

    resp = await lecturer_client.post("/lecturer/quizzes/questions", json={
        "course_id": classroom["course_id"], "type": "mcq",
        "question": "No options?", "level": "beginner",
    })
    assert resp.status_code == 422, resp.text

    resp = await other_lecturer_client.post("/lecturer/quizzes/questions", json={
        "course_id": classroom["course_id"], "type": "short_answer",
        "question": "x?", "level": "beginner",
    })
    assert resp.status_code == 403


# ── quick-add (LLM faked) ────────────────────────────────────────────────────

class _FakeQuestion:
    def __init__(self, i, course_id, qtype):
        self.id = 1000 + i
        self.course_id = course_id
        self.type = qtype
        self.question = f"generated {qtype} {i}"
        self.options = ["a", "b"] if qtype == "mcq" else None
        self.correct_answer = "a" if qtype == "mcq" else None
        self.suggested_answer = None if qtype == "mcq" else "ideal"
        self.level = "intermediate"
        self.source_material_id = 1
        self.topic = "gen"
        self.status = "draft"
        self.quiz_id = None


async def test_quick_add_creates_draft_quiz(lecturer_client, classroom, db_session, monkeypatch):
    from app.services import quiz_service

    async def fake_parse(prompt):
        from app.schemas.quiz import QuickAddSpec
        return QuickAddSpec(title="Quick quiz", mcq_count=2, short_answer_count=1,
                            time_limit_minutes=15, valid_days=2)

    async def fake_generate(course_id, material_ids, qtype, level, count, query=None):
        from app.core.database import AsyncSessionLocal
        from app.models.quiz import QuizQuestion
        out = []
        async with AsyncSessionLocal() as db:
            for i in range(count):
                q = QuizQuestion(
                    course_id=course_id, type=qtype, question=f"generated {qtype} {i}",
                    level="intermediate", topic="gen", status="draft",
                    options=["a", "b"] if qtype == "mcq" else None,
                    correct_answer="a" if qtype == "mcq" else None,
                )
                db.add(q)
                out.append(q)
            await db.commit()
            for q in out:
                await db.refresh(q)
        return out

    monkeypatch.setattr(quiz_service, "parse_quick_add", fake_parse)
    monkeypatch.setattr(quiz_service, "generate_questions", fake_generate)

    resp = await lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/quick-add",
        json={"prompt": "create 2 mcq, 1 short answer, duration 15min, valid two days from now",
              "material_ids": [1]},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["title"] == "Quick quiz"
    assert body["time_limit_minutes"] == 15
    assert body["question_count"] == 3
    assert body["closes_at"] is not None  # valid two days from now


async def test_quick_add_zero_counts_defaults_to_mcq(lecturer_client, classroom,
                                                     db_session, monkeypatch):
    """A natural message without explicit counts ("make me a quiz about chapter 3")
    parses to 0/0 — the service defaults to 3 MCQs instead of 422-ing."""
    from app.services import quiz_service

    async def fake_parse(prompt):
        from app.schemas.quiz import QuickAddSpec
        return QuickAddSpec(title="Chapter 3 quiz")  # no counts at all

    async def fake_generate(course_id, material_ids, qtype, level, count, query=None):
        from app.core.database import AsyncSessionLocal
        from app.models.quiz import QuizQuestion
        out = []
        async with AsyncSessionLocal() as db:
            for i in range(count):
                q = QuizQuestion(
                    course_id=course_id, type=qtype, question=f"default mcq {i}",
                    level=level, topic="ch3", status="draft",
                    options=["a", "b"], correct_answer="a",
                )
                db.add(q)
                out.append(q)
            await db.commit()
            for q in out:
                await db.refresh(q)
        return out

    monkeypatch.setattr(quiz_service, "parse_quick_add", fake_parse)
    monkeypatch.setattr(quiz_service, "generate_questions", fake_generate)

    resp = await lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/quick-add",
        json={"prompt": "make me a quiz about chapter 3", "material_ids": [1]},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["question_count"] == 3  # the default kicked in
    assert body["title"] == "Chapter 3 quiz"


async def test_quick_add_grounding_empty_falls_back_to_prompt(lecturer_client, classroom,
                                                              db_session, monkeypatch):
    """Selected materials with no retrievable text → grounded generation yields nothing →
    the service falls back to prompt-only drafting instead of 422 (seen live after a
    Moodle re-sync left kb_materials pointing at a stale course)."""
    from app.services import quiz_service

    async def fake_parse(prompt):
        from app.schemas.quiz import QuickAddSpec
        return QuickAddSpec(title="Fallback", mcq_count=1)

    async def fake_generate(course_id, material_ids, qtype, level, count, query=None):
        return []  # grounding produced nothing

    async def fake_generate_from_instruction(course_id, instruction, qtype, level, count):
        from app.core.database import AsyncSessionLocal
        from app.models.quiz import QuizQuestion
        out = []
        async with AsyncSessionLocal() as db:
            for i in range(count):
                q = QuizQuestion(
                    course_id=course_id, type=qtype, question=f"fallback {qtype} {i}",
                    level=level, topic="prompt", status="draft",
                    options=["a", "b"] if qtype == "mcq" else None,
                    correct_answer="a" if qtype == "mcq" else None,
                )
                db.add(q)
                out.append(q)
            await db.commit()
            for q in out:
                await db.refresh(q)
        return out

    monkeypatch.setattr(quiz_service, "parse_quick_add", fake_parse)
    monkeypatch.setattr(quiz_service, "generate_questions", fake_generate)
    monkeypatch.setattr(quiz_service, "generate_questions_from_instruction",
                        fake_generate_from_instruction)

    resp = await lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/quick-add",
        json={"prompt": "create 1 mcq", "material_ids": [1]},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["question_count"] == 1
    assert body["title"] == "Fallback"


async def test_quick_add_without_materials_uses_prompt_only(lecturer_client, classroom,
                                                            db_session, monkeypatch):
    """No material selected and no indexed course materials → the questions are drafted
    from the prompt + level alone (ungrounded), with no source material attached."""
    from app.services import quiz_service

    async def fake_parse(prompt):
        from app.schemas.quiz import QuickAddSpec
        return QuickAddSpec(mcq_count=1)

    async def fake_generate_from_instruction(course_id, instruction, qtype, level, count):
        from app.core.database import AsyncSessionLocal
        from app.models.quiz import QuizQuestion
        out = []
        async with AsyncSessionLocal() as db:
            for i in range(count):
                q = QuizQuestion(
                    course_id=course_id, type=qtype, question=f"prompt-only {qtype} {i}",
                    level=level, topic="prompt", status="draft",
                    options=["a", "b"] if qtype == "mcq" else None,
                    correct_answer="a" if qtype == "mcq" else None,
                )
                db.add(q)
                out.append(q)
            await db.commit()
            for q in out:
                await db.refresh(q)
        return out

    monkeypatch.setattr(quiz_service, "parse_quick_add", fake_parse)
    monkeypatch.setattr(quiz_service, "generate_questions_from_instruction",
                        fake_generate_from_instruction)
    resp = await lecturer_client.post(
        f"/lecturer/courses/{classroom['course_id']}/quizzes/quick-add",
        json={"prompt": "create 1 mcq about recursion"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["question_count"] == 1


# ── attempts_allowed + review_visible in taking/results ──────────────────────

async def _publish_and_start(lecturer_client, student_client, classroom, db_session,
                             attempts_allowed=1, review_visible=True):
    ids = await _seed_questions(db_session, classroom, n=1)
    resp = await lecturer_client.post("/lecturer/quizzes", json={
        "question_ids": ids, "attempts_allowed": attempts_allowed,
        "review_visible": review_visible, "title": "T", "time_limit_minutes": 30,
    })
    assert resp.status_code == 201, resp.text
    quiz_id = resp.json()[0]["id"]

    resp = await student_client.get("/student/quizzes")
    assert resp.status_code == 200, resp.text
    row = next(q for q in resp.json() if q["id"] == quiz_id)
    assert row["attempts_allowed"] == attempts_allowed

    resp = await student_client.post(f"/student/quizzes/{quiz_id}/attempt")
    assert resp.status_code == 201, resp.text
    attempt_id = resp.json()["attempt_id"]

    resp = await student_client.post(
        f"/student/quizzes/attempts/{attempt_id}/submit",
        json={"answers": [{"question_id": ids[0], "answer": "a"}]},
    )
    assert resp.status_code == 200, resp.text
    return quiz_id, attempt_id, ids[0]


async def test_second_attempt_blocked_when_one_allowed(lecturer_client, student_client,
                                                       classroom, db_session):
    quiz_id, attempt_id, qid = await _publish_and_start(
        lecturer_client, student_client, classroom, db_session, attempts_allowed=1)
    resp = await student_client.post(f"/student/quizzes/{quiz_id}/attempt")
    assert resp.status_code == 409, resp.text


async def test_second_attempt_allowed_when_two(lecturer_client, student_client,
                                               classroom, db_session):
    quiz_id, attempt_id, qid = await _publish_and_start(
        lecturer_client, student_client, classroom, db_session, attempts_allowed=2)
    resp = await student_client.post(f"/student/quizzes/{quiz_id}/attempt")
    assert resp.status_code == 201, resp.text


async def test_review_visible_false_hides_results(lecturer_client, student_client,
                                                  classroom, db_session):
    quiz_id, attempt_id, qid = await _publish_and_start(
        lecturer_client, student_client, classroom, db_session,
        review_visible=False)
    resp = await student_client.get(f"/student/quizzes/attempts/{attempt_id}/result")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["grading_complete"] is True
    assert body["review_visible"] is False
    for a in body["answers"]:
        assert a["question"] is None
        assert a["suggested_answer"] is None


# ── quiz detail for taking (S36) ─────────────────────────────────────────────

async def test_student_quiz_detail_strips_answers(lecturer_client, student_client,
                                                  classroom, db_session):
    ids = await _seed_questions(db_session, classroom, n=1)
    resp = await lecturer_client.post("/lecturer/quizzes", json={
        "question_ids": ids, "title": "Detail", "time_limit_minutes": 30,
    })
    quiz_id = resp.json()[0]["id"]

    resp = await student_client.get(f"/student/quizzes/{quiz_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Detail"
    assert len(body["questions"]) == 1
    q = body["questions"][0]
    assert q["question"] == "q0"
    assert q["options"] == ["a", "b"]
    # answers are never exposed to the taking student
    assert "correct_answer" not in q
    assert "suggested_answer" not in q


async def test_student_quiz_detail_not_enrolled_403(student_client, db_session):
    from app.models.class_ import ClassOccurrence, Course
    course = Course(code="CS404", name="Not enrolled")
    db_session.add(course)
    await db_session.flush()
    occ = ClassOccurrence(course_id=course.id, type="LECTURE", day_of_week="Fri",
                          start_time="09:00", end_time="10:00", room="X1",
                          lecturer_id=1)
    db_session.add(occ)
    await db_session.flush()
    from app.models.quiz import Quiz
    quiz = Quiz(course_id=course.id, title="Hidden", status="published", created_by=1,
                time_limit_minutes=10)
    db_session.add(quiz)
    await db_session.commit()

    resp = await student_client.get(f"/student/quizzes/{quiz.id}")
    assert resp.status_code == 403, resp.text
