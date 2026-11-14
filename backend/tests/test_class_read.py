"""Tests for class-level trends + assessment (FR-704, FR-705, S42).

Covers: per-session attendance rate + participation series (trend), class assessment
by topic and by session, and NFR-04 access control. No schema change — reads via
attendance_read / interaction tables / quiz tables.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence
from app.models.interaction import InteractionSession
from app.models.interaction_live import InteractionIDUSignal, InteractionReaction
from app.models.interaction_poll import InteractionPoll, InteractionPollOption, InteractionPollVote
from app.models.interaction_question import InteractionQuestion
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt, QuizAnswer
from app.models.session import AttendanceSession
from app.services.class_read import (
    class_assessment_by_session,
    class_assessment_by_topic,
    class_trend_per_session,
)

pytestmark = pytest.mark.db


async def _setup(db_session, classroom):
    """One closed session with 3 students (2 present, 1 absent), one interaction
    session with a question+vote+reaction+idu, one published quiz with an mcq, one
    submitted attempt scored 1.0. Returns occurrence_id, course_id."""
    s1 = classroom["student_ids"][0]
    s2 = classroom["student_ids"][1]
    s3 = classroom["student_ids"][2]
    now = datetime.now()
    # closed attendance session
    occ = (
        await db_session.execute(
            select(ClassOccurrence).where(ClassOccurrence.id == classroom["occurrence_id"])
        )
    ).scalar_one()
    a_sess = AttendanceSession(
        occurrence_id=occ.id, lecturer_id=classroom["lecturer_id"],
        status="closed", opened_at=now, closed_at=now,
    )
    db_session.add(a_sess)
    await db_session.flush()
    for sid, st in ((s1, "present"), (s2, "present"), (s3, "absent")):
        db_session.add(AttendanceRecord(session_id=a_sess.id, student_id=sid, status=st))
    # interaction session (open) with question, vote, reaction, idu
    i_sess = InteractionSession(
        occurrence_id=occ.id, status="open", opened_by=classroom["lecturer_id"],
    )
    db_session.add(i_sess)
    await db_session.flush()
    db_session.add(InteractionQuestion(
        interaction_id=i_sess.id, student_id=s1, text="q", anonymous=False, answered=False,
    ))
    poll = InteractionPoll(
        interaction_id=i_sess.id, question="p", is_open=True, opened_by=classroom["lecturer_id"],
    )
    db_session.add(poll)
    await db_session.flush()
    opt = InteractionPollOption(poll_id=poll.id, option_text="A", position=0)
    db_session.add(opt)
    await db_session.flush()
    db_session.add(InteractionPollVote(poll_id=poll.id, option_id=opt.id, student_id=s1))
    db_session.add(InteractionReaction(
        interaction_id=i_sess.id, student_id=s2, reaction="confused",
    ))
    db_session.add(InteractionIDUSignal(interaction_id=i_sess.id, student_id=s3))
    # published quiz + mcq + submitted attempt by s1 scored 1.0
    quiz = Quiz(
        course_id=classroom["course_id"], title="Quiz 1",
        time_limit_minutes=30, opens_at=now, closes_at=now + timedelta(days=7),
        status="published", created_by=classroom["lecturer_id"],
    )
    db_session.add(quiz)
    await db_session.flush()
    mcq = QuizQuestion(
        quiz_id=quiz.id, course_id=classroom["course_id"], type="mcq",
        question="Capital?", options=["A", "B"], correct_answer="A",
        level="beginner", topic="geo", source_material_id=101, status="approved",
    )
    db_session.add(mcq)
    await db_session.flush()
    attempt = QuizAttempt(
        quiz_id=quiz.id, student_id=s1,
        started_at=now - timedelta(minutes=5),
        deadline=now + timedelta(minutes=25), status="submitted", score=1.0,
        submitted_at=now,
    )
    db_session.add(attempt)
    await db_session.flush()
    db_session.add(QuizAnswer(
        attempt_id=attempt.id, question_id=mcq.id, answer="A", score=1.0, auto_graded=True,
    ))
    await db_session.commit()
    return classroom["occurrence_id"], classroom["course_id"]


async def test_class_trend_per_session(db_session, classroom):
    occurrence_id, course_id = await _setup(db_session, classroom)
    rows = await class_trend_per_session(db_session, occurrence_id)
    assert len(rows) == 1
    r = rows[0]
    assert r["session"] == 1
    assert r["attendance_rate"] == 66.7   # 2 attended / 3 counted
    assert r["attended"] == 2
    assert r["counted_sessions"] == 3
    assert r["participation"] == 4   # 1 question + 1 vote + 1 reaction + 1 idu


async def test_class_assessment_by_topic(db_session, classroom):
    occurrence_id, course_id = await _setup(db_session, classroom)
    rows = await class_assessment_by_topic(db_session, course_id)
    assert len(rows) == 1
    assert rows[0]["topic"] == "geo"
    assert rows[0]["average_score"] == 1.0
    assert rows[0]["question_count"] == 1


async def test_class_assessment_by_session(db_session, classroom):
    occurrence_id, course_id = await _setup(db_session, classroom)
    rows = await class_assessment_by_session(db_session, occurrence_id)
    assert len(rows) == 1
    assert rows[0]["session"] == 1
    assert rows[0]["average_score"] == 1.0
    assert rows[0]["quiz_count"] == 1


async def test_class_trend_unknown_occurrence_empty(db_session, classroom):
    rows = await class_trend_per_session(db_session, 999999)
    assert rows == []


async def test_class_assessment_by_topic_unknown_course_empty(db_session, classroom):
    rows = await class_assessment_by_topic(db_session, 999999)
    assert rows == []
