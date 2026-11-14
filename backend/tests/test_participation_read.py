"""Tests for the participation read interface (FR-509, S24).

Exercises app.services.participation_read against seeded interaction data: per-student
per-course, per-student per-session, class-level per-session, session listing, and the
cheap existence check. No permission checks are inside the service (callers enforce NFR-04);
these tests call the service directly.
"""

import pytest

from app.models.interaction import InteractionSession
from app.models.interaction_live import (
    InteractionIDUSignal,
    InteractionLiveQuestion,
    InteractionLiveQuestionResponse,
    InteractionReaction,
)
from app.models.interaction_poll import InteractionPoll, InteractionPollOption, InteractionPollVote
from app.models.interaction_question import InteractionQuestion
from app.models.user import Lecturer, Student
from app.services import participation_read

pytestmark = pytest.mark.db


async def _open_interaction(db_session, lecturer, occurrence_id: int) -> int:
    sess = InteractionSession(
        occurrence_id=occurrence_id,
        status="open",
        opened_by=lecturer.id,
    )
    db_session.add(sess)
    await db_session.commit()
    await db_session.refresh(sess)
    return sess.id


async def _seed_full_participation(db_session, classroom, lecturer, student) -> int:
    """One open interaction with a poll (2 options), a live question, a reaction and an IDU."""
    interaction_id = await _open_interaction(
        db_session, lecturer, classroom["occurrence_id"]
    )
    # poll + vote
    poll = InteractionPoll(
        interaction_id=interaction_id,
        question="Ready?",
        is_open=True,
        opened_by=lecturer.id,
    )
    db_session.add(poll)
    await db_session.flush()
    opt_a = InteractionPollOption(poll_id=poll.id, option_text="A", position=0)
    opt_b = InteractionPollOption(poll_id=poll.id, option_text="B", position=1)
    db_session.add_all([opt_a, opt_b])
    await db_session.flush()
    db_session.add(
        InteractionPollVote(poll_id=poll.id, option_id=opt_a.id, student_id=student.id)
    )
    # live question + response
    live_q = InteractionLiveQuestion(
        interaction_id=interaction_id,
        question="Following?",
        asked_by=lecturer.id,
        is_active=True,
    )
    db_session.add(live_q)
    await db_session.flush()
    db_session.add(
        InteractionLiveQuestionResponse(
            live_question_id=live_q.id,
            student_id=student.id,
            response="yes",
        )
    )
    # reaction + idu
    db_session.add(
        InteractionReaction(
            interaction_id=interaction_id,
            student_id=student.id,
            reaction="confused",
        )
    )
    db_session.add(
        InteractionIDUSignal(
            interaction_id=interaction_id,
            student_id=student.id,
        )
    )
    # a named question too
    db_session.add(
        InteractionQuestion(
            interaction_id=interaction_id,
            student_id=student.id,
            text="q1",
            anonymous=False,
        )
    )
    await db_session.commit()
    return interaction_id


async def _lecturer_and_student(db_session, classroom):
    # classroom fixture gives us lecturer_id (lecturers.id), not user.
    lecturer = await db_session.get(Lecturer, classroom["lecturer_id"])
    student = await db_session.get(Student, classroom["student_ids"][0])
    return lecturer, student


# ── per student per course ──────────────────────────────────────────────────

async def test_student_participation_per_course(db_session, classroom):
    lecturer, student = await _lecturer_and_student(db_session, classroom)
    await _seed_full_participation(db_session, classroom, lecturer, student)

    summary = await participation_read.get_student_participation_per_course(
        db_session, student.id, classroom["course_id"]
    )
    assert summary["student_id"] == student.id
    assert summary["course_id"] == classroom["course_id"]
    assert summary["questions"] >= 1
    assert summary["votes"] >= 1
    assert summary["responses"] >= 1
    assert summary["reactions"] >= 1
    assert summary["idu_signals"] >= 1
    assert summary["idu_students"] >= 1


async def test_student_participation_per_course_other_student_is_zero(
    db_session, classroom
):
    lecturer, student = await _lecturer_and_student(db_session, classroom)
    await _seed_full_participation(db_session, classroom, lecturer, student)
    other_student_id = classroom["student_ids"][1]

    summary = await participation_read.get_student_participation_per_course(
        db_session, other_student_id, classroom["course_id"]
    )
    assert summary["questions"] == 0
    assert summary["votes"] == 0
    assert summary["responses"] == 0
    assert summary["reactions"] == 0
    assert summary["idu_signals"] == 0
    assert summary["idu_students"] == 0


# ── per student per session ─────────────────────────────────────────────────

async def test_student_participation_per_session(db_session, classroom):
    lecturer, student = await _lecturer_and_student(db_session, classroom)
    await _seed_full_participation(db_session, classroom, lecturer, student)

    summary = await participation_read.get_student_participation_per_session(
        db_session, student.id, classroom["occurrence_id"]
    )
    assert summary["student_id"] == student.id
    assert summary["occurrence_id"] == classroom["occurrence_id"]
    assert summary["questions"] == 1
    assert summary["votes"] == 1
    assert summary["responses"] == 1
    assert summary["reactions"] == 1
    assert summary["idu_signals"] == 1


# ── class level per session ─────────────────────────────────────────────────

async def test_class_participation_per_session_counts_distinct_idu_students(
    db_session, classroom
):
    lecturer, student = await _lecturer_and_student(db_session, classroom)
    interaction_id = await _open_interaction(
        db_session, lecturer, classroom["occurrence_id"]
    )
    # Two distinct students signal IDU → distinct = 2.
    stu2_id = classroom["student_ids"][1]
    for sid in (student.id, stu2_id):
        db_session.add(InteractionIDUSignal(interaction_id=interaction_id, student_id=sid))
    await db_session.commit()

    counts = await participation_read.get_class_participation_per_session(
        db_session, classroom["occurrence_id"]
    )
    assert counts["occurrence_id"] == classroom["occurrence_id"]
    assert counts["idu_signals"] == 2
    assert counts["idu_students"] == 2  # distinct students, not clicks


async def test_class_participation_per_session_aggregates_all_types(
    db_session, classroom
):
    lecturer, student = await _lecturer_and_student(db_session, classroom)
    await _seed_full_participation(db_session, classroom, lecturer, student)

    counts = await participation_read.get_class_participation_per_session(
        db_session, classroom["occurrence_id"]
    )
    assert counts["questions"] == 1
    assert counts["votes"] == 1
    assert counts["responses"] == 1
    assert counts["reactions"] == 1
    assert counts["idu_signals"] == 1
    assert counts["idu_students"] == 1


# ── session listing ─────────────────────────────────────────────────────────

async def test_list_class_sessions_with_counts(db_session, classroom):
    lecturer, student = await _lecturer_and_student(db_session, classroom)
    await _seed_full_participation(db_session, classroom, lecturer, student)

    sessions = await participation_read.list_class_sessions_with_counts(
        db_session, classroom["course_id"]
    )
    assert len(sessions) >= 1
    cs101 = [s for s in sessions if s["occurrence_id"] == classroom["occurrence_id"]]
    assert cs101
    entry = cs101[0]
    assert entry["questions"] == 1
    assert entry["label"] is not None


# ── existence check ─────────────────────────────────────────────────────────

async def test_student_has_participated_in_course(db_session, classroom):
    lecturer, student = await _lecturer_and_student(db_session, classroom)
    await _seed_full_participation(db_session, classroom, lecturer, student)

    assert await participation_read.student_has_participated_in_course(
        db_session, student.id, classroom["course_id"]
    ) is True
    assert await participation_read.student_has_participated_in_course(
        db_session, classroom["student_ids"][1], classroom["course_id"]
    ) is False


async def test_no_participation_returns_zeros(db_session, classroom):
    lecturer, student = await _lecturer_and_student(db_session, classroom)
    # open an interaction but write nothing
    await _open_interaction(db_session, lecturer, classroom["occurrence_id"])

    summary = await participation_read.get_student_participation_per_course(
        db_session, student.id, classroom["course_id"]
    )
    assert summary["questions"] == 0
    assert summary["votes"] == 0
    assert summary["responses"] == 0
    assert summary["reactions"] == 0
    assert summary["idu_signals"] == 0

    counts = await participation_read.get_class_participation_per_session(
        db_session, classroom["occurrence_id"]
    )
    assert counts["questions"] == 0
