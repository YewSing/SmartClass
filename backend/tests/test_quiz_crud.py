"""S40: quiz model and lecturer CRUD (FR-605, FR-606 settings, NFR-04).

A lecturer who teaches the course creates, reads, updates and deletes draft quizzes and their
settings; a game quiz always uses per-question timers; nobody else reaches them.
"""
import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.core.timezone import now_myt
from app.models.audit import AuditLog
from app.models.class_ import ClassOccurrence
from app.models.quiz import Quiz, QuizAnswer, QuizAttempt, QuizQuestion
from app.schemas.quiz import QuestionIn
from app.services import quiz_store

URL = "/lecturer/quizzes"


def graded(c, **over) -> dict:
    return {"course_id": c.course_id, "title": "Week 5", "type": "graded", **over}


def game(c, **over) -> dict:
    return graded(c, type="game", **over)


async def call(c, method, url, expect, *, uid=None, role="lecturer", **kw):
    async with c.client(uid or c.lecturer_user_id, role) as api:
        r = await api.request(method, url, **kw)
    assert r.status_code == expect, r.text
    return r.json() if r.content else None


async def create(c, body=None, expect=201, **kw):
    return await call(c, "POST", URL, expect, json=body or graded(c), **kw)


async def get(c, qid, expect=200, **kw):
    return await call(c, "GET", f"{URL}/{qid}", expect, **kw)


async def patch(c, qid, body, expect=200, **kw):
    return await call(c, "PATCH", f"{URL}/{qid}", expect, json=body, **kw)


async def delete(c, qid, expect=204, **kw):
    return await call(c, "DELETE", f"{URL}/{qid}", expect, **kw)


async def insert(*rows):
    async with AsyncSessionLocal() as db:
        db.add_all(rows)
        await db.commit()
        return [r.id for r in rows]


def question_row(quiz_id, position=0, **over) -> QuizQuestion:
    values = {"quiz_id": quiz_id, "position": position, "type": "mcq", "text": "2+2?",
              "options": ["3", "4"], "answer": 1, "topic": "Sums", "origin": "extended",
              "approved": False, "created_at": now_myt(), "updated_at": now_myt(), **over}
    return QuizQuestion(**values)


def attempt_row(quiz_id, student_id) -> QuizAttempt:
    return QuizAttempt(quiz_id=quiz_id, student_id=student_id, status="in_progress", started_at=now_myt())


async def set_status(quiz_id, status):
    async with AsyncSessionLocal() as db:
        (await db.get(Quiz, quiz_id)).status = status
        await db.commit()


async def count(model) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(model))


# ── create / read / list ─────────────────────────────────────────────────────

@pytest.mark.db
async def test_create_graded_with_defaults(shino_class):
    c = shino_class
    q = await create(c, graded(c, title="  Week 5  "))
    assert q["title"] == "Week 5" and q["type"] == "graded" and q["status"] == "draft"
    assert q["course_id"] == c.course_id and q["course_code"] == "SH101"
    assert q["timer_mode"] == "quiz" and q["timer_seconds"] == settings.QUIZ_DEFAULT_QUIZ_SECONDS
    assert q["opens_at"] is None and q["closes_at"] is None
    assert q["shuffle"] is False and q["speed_bonus"] is True
    assert q["release"] == "manual" and q["release_marks"] is True and q["release_answers"] is True
    assert q["question_count"] == 0 and q["approved_count"] == 0 and q["questions"] == []
    assert await get(c, q["id"]) == q


@pytest.mark.db
async def test_create_with_every_setting(shino_class):
    c = shino_class
    body = graded(c, timer_mode="question", timer_seconds=45, opens_at="2026-12-01T09:00:00",
                  closes_at="2026-12-02T09:00:00", shuffle=True, speed_bonus=False,
                  release="on_close", release_marks=True, release_answers=False)
    q = await create(c, body)
    assert {k: q[k] for k in body} == body


@pytest.mark.db
async def test_list_is_newest_first_and_filtered_by_course(shino_class):
    c = shino_class
    first, second = await create(c), await create(c, game(c, title="Game"))
    await insert(question_row(first["id"], 0, approved=True), question_row(first["id"], 1))
    rows = (await call(c, "GET", URL, 200))["quizzes"]
    assert [r["id"] for r in rows] == [second["id"], first["id"]]
    assert (rows[1]["question_count"], rows[1]["approved_count"]) == (2, 1)
    assert (rows[0]["question_count"], rows[0]["approved_count"]) == (0, 0)
    assert "questions" not in rows[0]
    filtered = (await call(c, "GET", URL, 200, params={"course_id": c.course_id}))["quizzes"]
    assert [r["id"] for r in filtered] == [second["id"], first["id"]]
    # the other lecturer sees none of them
    assert (await call(c, "GET", URL, 200, uid=c.other_lecturer_user_id))["quizzes"] == []
    await call(c, "GET", URL, 403, uid=c.other_lecturer_user_id, params={"course_id": c.course_id})


@pytest.mark.db
async def test_read_gives_the_questions_in_order(shino_class):
    c = shino_class
    q = await create(c)
    await insert(
        question_row(q["id"], 1, type="short", text="Why?", options=None, answer=None,
                     suggested_answer="Because", topic=None),
        question_row(q["id"], 0, origin="from_material", source_file="w5.pdf", source_type="slide",
                     source_page=3, explanation="See slide 3", approved=True))
    got = (await get(c, q["id"]))["questions"]
    assert [x["position"] for x in got] == [0, 1]
    assert got[0]["options"] == ["3", "4"] and got[0]["answer"] == 1 and got[0]["suggested_answer"] is None
    assert (got[0]["source_file"], got[0]["source_type"], got[0]["source_page"]) == ("w5.pdf", "slide", 3)
    assert got[0]["origin"] == "from_material" and got[0]["approved"] is True
    assert got[0]["explanation"] == "See slide 3" and got[0]["topic"] == "Sums"
    assert got[1]["type"] == "short" and got[1]["suggested_answer"] == "Because" and got[1]["options"] is None


# ── validation ───────────────────────────────────────────────────────────────

@pytest.mark.db
@pytest.mark.parametrize("over", [
    {"title": "   "},
    {"title": "x" * 201},
    {"title": "a\x00b"},
    {"title": None},
    {"type": "survey"},
    {"type": None},
    {"timer_mode": "none"},
    {"timer_seconds": 0},
    {"timer_mode": "question", "timer_seconds": 4},
    {"timer_mode": "question", "timer_seconds": 601},
    {"timer_mode": "quiz", "timer_seconds": 59},
    {"timer_mode": "quiz", "timer_seconds": 14401},
    {"type": "game", "timer_seconds": 601},
    {"opens_at": "2026-12-02T09:00:00", "closes_at": "2026-12-02T09:00:00"},
    {"opens_at": "2026-12-02T09:00:00", "closes_at": "2026-12-01T09:00:00"},
    # the same instant written in two offsets is not an open window
    {"opens_at": "2026-12-02T09:00:00", "closes_at": "2026-12-02T01:00:00Z"},
    {"opens_at": "9999-12-31T23:59:59-12:00"},
    {"release": "now"},
    {"release": "on_close", "release_marks": False, "release_answers": False},
    {"status": "published"},
    {"points": 5},
])
async def test_create_validation(shino_class, over):
    await create(shino_class, graded(shino_class, **over), expect=422)
    assert await count(Quiz) == 0


@pytest.mark.db
@pytest.mark.parametrize("missing", ["course_id", "title", "type"])
async def test_create_needs_course_title_and_type(shino_class, missing):
    body = graded(shino_class)
    del body[missing]
    await create(shino_class, body, expect=422)


@pytest.mark.db
@pytest.mark.parametrize("over", [
    {"timer_mode": "question", "timer_seconds": 5}, {"timer_mode": "question", "timer_seconds": 600},
    {"timer_mode": "quiz", "timer_seconds": 60}, {"timer_mode": "quiz", "timer_seconds": 14400},
    {"title": "x" * 200},
])
async def test_limits_are_allowed(shino_class, over):
    q = await create(shino_class, graded(shino_class, **over))
    assert {k: q[k] for k in over} == over


@pytest.mark.db
async def test_times_with_an_offset_are_stored_as_malaysia_time(shino_class):
    c = shino_class
    q = await create(c, graded(c, opens_at="2026-12-01T01:00:00Z", closes_at="2026-12-01T12:00:00+09:00"))
    assert q["opens_at"] == "2026-12-01T09:00:00" and q["closes_at"] == "2026-12-01T11:00:00"


# ── game quizzes always use per-question timers (FR-606) ─────────────────────

@pytest.mark.db
async def test_game_forces_per_question_timer(shino_class):
    c = shino_class
    default = settings.QUIZ_DEFAULT_QUESTION_SECONDS
    q = await create(c, game(c))
    assert (q["timer_mode"], q["timer_seconds"]) == ("question", default)
    q = await create(c, game(c, timer_seconds=20))
    assert (q["timer_mode"], q["timer_seconds"]) == ("question", 20)
    # a whole-quiz time is not reused as a per-question time
    q = await create(c, game(c, timer_mode="quiz", timer_seconds=1800))
    assert (q["timer_mode"], q["timer_seconds"]) == ("question", default)
    # nor can an update bring it back
    q = await patch(c, q["id"], {"timer_seconds": 45})
    q = await patch(c, q["id"], {"timer_mode": "quiz", "timer_seconds": 900})
    assert (q["timer_mode"], q["timer_seconds"]) == ("question", 45)


@pytest.mark.db
async def test_changing_a_graded_quiz_to_a_game_changes_its_timer(shino_class):
    c = shino_class
    q = await create(c, graded(c, timer_mode="quiz", timer_seconds=600))
    q = await patch(c, q["id"], {"type": "game"})
    assert (q["type"], q["timer_mode"]) == ("game", "question")
    assert q["timer_seconds"] == settings.QUIZ_DEFAULT_QUESTION_SECONDS
    # back to graded: the per-question timer stays until the lecturer changes it
    q = await patch(c, q["id"], {"type": "graded"})
    assert (q["type"], q["timer_mode"]) == ("graded", "question")
    q = await patch(c, q["id"], {"timer_mode": "quiz"})
    assert (q["timer_mode"], q["timer_seconds"]) == ("quiz", settings.QUIZ_DEFAULT_QUIZ_SECONDS)
    q = await patch(c, q["id"], {"type": "game", "timer_seconds": 15})
    assert (q["timer_mode"], q["timer_seconds"]) == ("question", 15)


@pytest.mark.db
async def test_database_refuses_a_game_with_a_whole_quiz_timer(shino_class):
    q = await create(shino_class, game(shino_class))
    async with AsyncSessionLocal() as db:
        with pytest.raises(IntegrityError):
            await db.execute(text("UPDATE m6_quizzes SET timer_mode='quiz', timer_seconds=600 WHERE id=:i"),
                             {"i": q["id"]})


# ── update ───────────────────────────────────────────────────────────────────

@pytest.mark.db
async def test_update_changes_only_the_given_fields(shino_class):
    c = shino_class
    q = await create(c, graded(c, opens_at="2026-12-01T09:00:00", closes_at="2026-12-02T09:00:00"))
    got = await patch(c, q["id"], {"title": " New ", "shuffle": True, "opens_at": None})
    expected = {**q, "title": "New", "shuffle": True, "opens_at": None, "updated_at": got["updated_at"]}
    assert got == expected and got["updated_at"] >= q["updated_at"]
    assert await get(c, q["id"]) == got
    assert (await patch(c, q["id"], {}))["title"] == "New"      # nothing to change


@pytest.mark.db
@pytest.mark.parametrize("body", [
    {"title": None}, {"title": " "}, {"type": None}, {"timer_seconds": None}, {"shuffle": None},
    {"release": None}, {"course_id": 2}, {"status": "published"},
    {"timer_seconds": 30},                              # too short for its whole-quiz timer
    {"closes_at": "2026-11-30T09:00:00"},               # before the stored opening time
    {"release": "on_close", "release_marks": False},    # with the stored release_answers=False
    {"type": "game", "timer_seconds": 601},
])
async def test_update_validation_against_the_stored_settings(shino_class, body):
    c = shino_class
    q = await create(c, graded(c, opens_at="2026-12-01T09:00:00", release_answers=False))
    await patch(c, q["id"], body, expect=422)
    assert await get(c, q["id"]) == q


# ── delete and the draft-only rule ───────────────────────────────────────────

@pytest.mark.db
async def test_delete_draft_removes_its_questions_and_is_audited(shino_class):
    c = shino_class
    q, kept = await create(c), await create(c, graded(c, title="Kept"))
    await insert(question_row(q["id"]), question_row(kept["id"]))
    await delete(c, q["id"])
    await get(c, q["id"], expect=403)                  # like any unknown id
    assert await count(Quiz) == 1 and await count(QuizQuestion) == 1
    async with AsyncSessionLocal() as db:
        logs = list((await db.execute(select(AuditLog).where(AuditLog.action == "QUIZ_DELETE"))).scalars())
    assert [(x.actor_id, x.target_id) for x in logs] == [(c.lecturer_user_id, str(q["id"]))]


@pytest.mark.db
@pytest.mark.parametrize("status", ["published", "closed"])
async def test_only_drafts_can_be_changed_or_deleted(shino_class, status):
    c = shino_class
    q = await create(c)
    await set_status(q["id"], status)
    await patch(c, q["id"], {"title": "New"}, expect=409)
    await delete(c, q["id"], expect=409)
    got = await get(c, q["id"])
    assert got["title"] == "Week 5" and got["status"] == status


@pytest.mark.db
async def test_draft_with_attempts_cannot_be_changed_or_deleted(shino_class):
    c = shino_class
    q = await create(c)
    await insert(attempt_row(q["id"], c.student_ids[0]))
    await patch(c, q["id"], {"type": "game"}, expect=409)
    await delete(c, q["id"], expect=409)
    assert (await get(c, q["id"]))["type"] == "graded" and await count(QuizAttempt) == 1


# ── access matrix (NFR-04) ───────────────────────────────────────────────────

@pytest.mark.db
async def test_access_matrix(shino_class, users):
    c = shino_class
    q = await create(c)
    outsiders = [(c.student_user_ids[0], "student"), (c.outsider_user_id, "student"),
                 (c.other_lecturer_user_id, "lecturer"), (users["lecturer"].id, "lecturer"),
                 (users["admin"].id, "admin")]
    for uid, role in outsiders:
        await create(c, expect=403, uid=uid, role=role)
        await get(c, q["id"], expect=403, uid=uid, role=role)
        await patch(c, q["id"], {"title": "Hacked"}, expect=403, uid=uid, role=role)
        await delete(c, q["id"], expect=403, uid=uid, role=role)
    await call(c, "GET", URL, 403, uid=c.student_user_ids[0], role="student")
    await call(c, "GET", URL, 403, uid=users["admin"].id, role="admin")
    assert (await call(c, "GET", URL, 200, uid=users["lecturer"].id))["quizzes"] == []
    async with c.client() as api:
        for method, url in [("GET", URL), ("POST", URL), ("GET", f"{URL}/{q['id']}"),
                            ("PATCH", f"{URL}/{q['id']}"), ("DELETE", f"{URL}/{q['id']}")]:
            assert (await api.request(method, url, json={})).status_code in (401, 403)
    assert await get(c, q["id"]) == q and await count(Quiz) == 1


@pytest.mark.db
async def test_unknown_ids_look_like_someone_elses(shino_class):
    c = shino_class
    await create(c, {**graded(c), "course_id": 99999}, expect=403)
    await get(c, 99999, expect=403)
    await patch(c, 99999, {"title": "x"}, expect=403)
    await delete(c, 99999, expect=403)


@pytest.mark.db
async def test_another_lecturer_of_the_same_course_shares_its_quizzes(shino_class):
    """Quizzes belong to the course: a second lecturer gets access by teaching a class of it, and
    loses it when no longer assigned."""
    c = shino_class
    q = await create(c)
    [occ_id] = await insert(ClassOccurrence(course_id=c.course_id, type="TUTORIAL", label="T1",
                                            lecturer_id=c.other_lecturer_id))
    got = await patch(c, q["id"], {"title": "Shared"}, uid=c.other_lecturer_user_id)
    assert got["title"] == "Shared"
    # the two classes the lecturer teaches don't list it twice
    await insert(ClassOccurrence(course_id=c.course_id, type="TUTORIAL", label="T2",
                                 lecturer_id=c.other_lecturer_id))
    rows = (await call(c, "GET", URL, 200, uid=c.other_lecturer_user_id))["quizzes"]
    assert [r["id"] for r in rows] == [q["id"]]
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE class_occurrences SET lecturer_id = NULL WHERE course_id = :c "
                              "AND lecturer_id = :l"), {"c": c.course_id, "l": c.other_lecturer_id})
        await db.commit()
    await get(c, q["id"], expect=403, uid=c.other_lecturer_user_id)


@pytest.mark.db
async def test_a_token_claiming_lecturer_does_not_help_a_student(shino_class):
    c = shino_class
    q = await create(c)
    forged = create_access_token(c.student_user_ids[0], "lecturer")
    async with c.client() as api:
        r = await api.get(f"{URL}/{q['id']}", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 403


# ── the tables ───────────────────────────────────────────────────────────────

@pytest.mark.db
@pytest.mark.parametrize("over", [
    {"type": "essay"},
    {"options": None},                                         # an MCQ needs options
    {"answer": None},                                          # ...and an answer
    {"answer": 2},                                             # ...that is one of them
    {"answer": -1},
    {"options": ["only"], "answer": 0},
    {"type": "short", "options": None, "answer": None},        # a short answer needs a suggestion
    {"type": "short", "suggested_answer": "x"},                # ...and no options
    {"origin": "made_up"},
    {"origin": "from_material"},                               # needs its source (NFR-48)
    {"origin": "from_material", "source_file": "a.pdf"},
    {"text": ""},
])
async def test_question_table_constraints(shino_class, over):
    q = await create(shino_class)
    with pytest.raises(IntegrityError):
        await insert(question_row(q["id"], **over))
    assert await count(QuizQuestion) == 0


@pytest.mark.db
async def test_question_positions_are_unique_but_can_be_swapped(shino_class):
    q = await create(shino_class)
    a, b = await insert(question_row(q["id"], 0), question_row(q["id"], 1))
    with pytest.raises(IntegrityError):
        await insert(question_row(q["id"], 1))
    async with AsyncSessionLocal() as db:
        for qid, pos in ((a, 1), (b, 0)):
            await db.execute(text("UPDATE m6_questions SET position=:p WHERE id=:i"), {"p": pos, "i": qid})
        await db.commit()


@pytest.mark.db
async def test_one_attempt_per_student_and_one_answer_per_question(shino_class):
    c = shino_class
    q = await create(c)
    [qn] = await insert(question_row(q["id"]))
    [att] = await insert(attempt_row(q["id"], c.student_ids[0]))
    await insert(attempt_row(q["id"], c.student_ids[1]))
    with pytest.raises(IntegrityError):
        await insert(attempt_row(q["id"], c.student_ids[0]))
    await insert(QuizAnswer(attempt_id=att, question_id=qn, option_index=1, answered_at=now_myt()))
    with pytest.raises(IntegrityError):
        await insert(QuizAnswer(attempt_id=att, question_id=qn, option_index=0, answered_at=now_myt()))


@pytest.mark.db
async def test_models_and_migration_agree(shino_class):
    """The migrated m6_ tables have exactly the models' columns, nullability, checks and indexes."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import inspect

    from app.core.database import Base, engine

    tables = ("m6_quizzes", "m6_questions", "m6_attempts", "m6_answers")

    def check(conn):
        ctx = MigrationContext.configure(conn, opts={
            "compare_type": True,
            "include_object": lambda o, name, kind, *_: (
                name in tables if kind == "table" else o.table.name in tables)})
        diff = compare_metadata(ctx, Base.metadata)
        checks = {t: {k["name"] for k in inspect(conn).get_check_constraints(t)} for t in tables}
        return diff, checks

    async with engine.connect() as conn:
        diff, checks = await conn.run_sync(check)
    assert diff == []
    for t in tables:
        model = {k.name for k in Base.metadata.tables[t].constraints if isinstance(k, CheckConstraint)}
        assert model and checks[t] == model


# ── settings rules and the question schema (no database) ─────────────────────

def test_resolve_settings_does_not_change_its_inputs():
    current = {**quiz_store.DEFAULTS, "title": "t", "type": "graded", "timer_mode": "quiz", "timer_seconds": 600}
    before, changes = dict(current), {"type": "game"}
    out = quiz_store.resolve_settings(current, changes)
    assert current == before and changes == {"type": "game"} and out["timer_mode"] == "question"


def mcq(**over):
    return {"type": "mcq", "text": "2+2?", "options": ["3", "4"], "answer": 1, **over}


def short(**over):
    return {"type": "short", "text": "Why?", "suggested_answer": "Because", **over}


SOURCE = {"origin": "from_material", "source_file": "w5.pdf", "source_type": "slide", "source_page": 3}


@pytest.mark.parametrize("body", [
    mcq(), short(), mcq(options=list("abcdef"), answer=5), mcq(**SOURCE, topic="Sums", explanation="w5.pdf, slide 3"),
])
def test_question_schema_accepts(body):
    q = QuestionIn(**body)
    assert q.type == body["type"] and q.origin == body.get("origin", "extended")


def test_question_schema_trims_and_blanks_become_null():
    q = QuestionIn(**mcq(text="  2+2? ", options=[" 3", "4 "], topic="  ", explanation=" "))
    assert (q.text, q.options, q.topic, q.explanation) == ("2+2?", ["3", "4"], None, None)


@pytest.mark.parametrize("body", [
    mcq(type="essay"), mcq(text="  "), mcq(text="x" * 1001), mcq(text="a\x00"),
    mcq(options=None), mcq(options=["one"], answer=0), mcq(options=list("abcdefg")),
    mcq(options=["a", "A "]), mcq(options=["a", " "]), mcq(options=["a", "x" * 301]),
    mcq(answer=None), mcq(answer=2), mcq(answer=-1), mcq(answer=True), mcq(answer="1"),
    mcq(suggested_answer="4"),
    short(suggested_answer=None), short(suggested_answer=" "), short(suggested_answer="x" * 2001),
    short(options=["a", "b"]), short(answer=0),
    mcq(origin="other"), mcq(origin="from_material"), mcq(**{**SOURCE, "source_page": None}),
    mcq(**{**SOURCE, "source_file": " "}), mcq(**{**SOURCE, "source_page": 0}),
    mcq(**{**SOURCE, "source_type": None}), mcq(**{**SOURCE, "source_type": "chapter"}),
    mcq(approved=True), mcq(points=2),
])
def test_question_schema_refuses(body):
    with pytest.raises(ValidationError):
        QuestionIn(**body)
