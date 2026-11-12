"""T37: read interface for Module 7 (FR-313)."""
import dataclasses
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.session import AttendanceSession
from app.services.attendance_read import (
    absence_streak,
    consecutive_absences,
    course_rates,
    course_records,
    student_rates,
    student_records,
)
from app.services.attendance_stats import student_course_history

pytestmark = pytest.mark.db

MON = date(2026, 11, 16)


def day(offset: int) -> date:
    return MON + timedelta(days=offset)


async def make_session(
    occ_id: int,
    lecturer_id: int,
    day: date,
    status: str = "closed",
    records: dict[int, str] | None = None,
    hour: int = 8,
) -> int:
    """One attendance session for `occ_id`, with optional {student_id: status} records."""
    async with AsyncSessionLocal() as db:
        start = datetime(day.year, day.month, day.day, hour, 0)
        end = start + timedelta(hours=2)
        sess = AttendanceSession(
            occurrence_id=occ_id,
            lecturer_id=lecturer_id,
            status=status,
            source="manual",
            class_date=day,
            opened_at=None if status == "scheduled" else start,
            starts_at=start,
            ends_at=end,
            closed_at=end if status == "closed" else None,
        )
        db.add(sess)
        await db.flush()
        for student_id, record_status in (records or {}).items():
            db.add(AttendanceRecord(
                session_id=sess.id,
                student_id=student_id,
                status=record_status,
                detected_at=start if record_status in ("present", "late") else None,
            ))
        await db.commit()
        return sess.id


async def add_occurrence(
    course_id: int,
    lecturer_id: int,
    student_ids: list[int],
    type_: str = "TUTORIAL",
    label: str = "Tutorial Group 1",
) -> int:
    """A class of `course_id` with the given students enrolled; returns the occurrence id."""
    async with AsyncSessionLocal() as db:
        occ = ClassOccurrence(
            course_id=course_id,
            type=type_,
            day_of_week="Wed",
            start_time="14:00",
            end_time="15:00",
            room="DK3",
            lecturer_id=lecturer_id,
            label=label,
        )
        db.add(occ)
        await db.flush()
        for student_id in student_ids:
            db.add(Enrollment(student_id=student_id, occurrence_id=occ.id))
        await db.commit()
        return occ.id


async def enrol(student_id: int, occurrence_id: int) -> None:
    async with AsyncSessionLocal() as db:
        db.add(Enrollment(student_id=student_id, occurrence_id=occurrence_id))
        await db.commit()


# ── Pure helper ──────────────────────────────────────────────────────────────

def test_absence_streak_pure():
    assert absence_streak([]) == (0, 0)
    assert absence_streak(["present", "absent", "excused", "absent", "absent"]) == (3, 3)
    assert absence_streak(["absent", "absent", "present", "absent", "late"]) == (0, 2)
    assert absence_streak(["excused", "excused"]) == (0, 0)
    assert absence_streak(["absent", "late", "absent"]) == (1, 1)


# ── Records ──────────────────────────────────────────────────────────────────

async def test_course_records_closed_only_missing_is_absent(classroom):
    s0, s1, s2 = classroom["student_ids"]
    occ = classroom["occurrence_id"]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]

    closed_id = await make_session(occ, lec, day(1), records={s0: "present", s1: "late"})
    await make_session(occ, lec, day(2), status="open", records={s0: "present"})
    await make_session(occ, lec, day(3), status="cancelled")
    await make_session(occ, lec, day(4), status="needs_confirmation")

    async with AsyncSessionLocal() as db:
        rows = await course_records(db, course)

    assert len(rows) == 3
    assert all(row.session_id == closed_id for row in rows)
    assert [row.matric_no for row in rows] == ["S0000001", "S0000002", "S0000003"]
    assert [row.status for row in rows] == ["present", "late", "absent"]
    assert all(row.course_code == "CS101" for row in rows)
    assert all(row.class_type == "LECTURE" for row in rows)
    assert all(row.date == day(1) for row in rows)
    assert all(row.overridden is False for row in rows)
    assert rows[2].student_id == s2
    assert rows[2].detected_at is None


async def test_course_records_overridden_flag(classroom, users):
    s0 = classroom["student_ids"][0]
    occ = classroom["occurrence_id"]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]

    session_id = await make_session(occ, lec, day(1), records={s0: "present"})

    async with AsyncSessionLocal() as db:
        rec = (await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.student_id == s0,
            )
        )).scalar_one()
        rec.override_by = users["lecturer"].id
        rec.override_at = datetime(day(1).year, day(1).month, day(1).day, 9, 0)
        await db.commit()

    async with AsyncSessionLocal() as db:
        rows = await course_records(db, course)

    row = next(r for r in rows if r.student_id == s0)
    assert row.overridden is True


async def test_course_records_tutorial_lists_only_its_group(classroom):
    s0 = classroom["student_ids"][0]
    occ = classroom["occurrence_id"]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]

    tutorial_id = await add_occurrence(course, lec, [s0])
    await make_session(occ, lec, day(1))
    await make_session(tutorial_id, lec, day(2))

    async with AsyncSessionLocal() as db:
        rows = await course_records(db, course)

    assert len(rows) == 4
    assert sum(1 for row in rows if row.date == day(1)) == 3
    tutorial_rows = [row for row in rows if row.date == day(2)]
    assert len(tutorial_rows) == 1
    row = tutorial_rows[0]
    assert row.student_id == s0
    assert row.class_type == "TUTORIAL"
    assert row.class_label == "Tutorial Group 1"
    assert row.status == "absent"
    assert [row.date for row in rows] == [day(1), day(1), day(1), day(2)]


async def test_course_records_date_range_inclusive(classroom):
    occ = classroom["occurrence_id"]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]

    await make_session(occ, lec, day(1))
    await make_session(occ, lec, day(3))
    await make_session(occ, lec, day(5))

    async with AsyncSessionLocal() as db:
        rows = await course_records(db, course, from_date=day(3), to_date=day(5))

    assert len(rows) == 6
    assert {row.date for row in rows} == {day(3), day(5)}

    async with AsyncSessionLocal() as db:
        with pytest.raises(ValueError):
            await course_records(db, course, from_date=day(5), to_date=day(1))


async def test_student_records_filters_by_student_and_course(classroom):
    s0, s1 = classroom["student_ids"][:2]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]
    other_occ = classroom["other_occurrence_id"]

    await enrol(s0, other_occ)
    await make_session(classroom["occurrence_id"], lec, day(1), records={s0: "late", s1: "present"})
    await make_session(
        other_occ, classroom["other_lecturer_id"], day(2), records={s0: "absent"},
    )

    async with AsyncSessionLocal() as db:
        rows = await student_records(db, s0)

    assert len(rows) == 2
    assert all(row.student_id == s0 for row in rows)
    assert [row.course_code for row in rows] == ["CS101", "CS202"]

    async with AsyncSessionLocal() as db:
        rows = await student_records(db, s0, course_id=course)

    assert len(rows) == 1
    assert rows[0].status == "late"


# ── Rates ────────────────────────────────────────────────────────────────────

async def test_course_rates_formula_and_no_sessions(classroom):
    s0, s1, _ = classroom["student_ids"]
    occ = classroom["occurrence_id"]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]

    async with AsyncSessionLocal() as db:
        empty = await course_rates(db, course)

    assert len(empty) == 3
    assert all(r.closed_sessions == 0 for r in empty)
    assert all(r.rate is None for r in empty)

    await make_session(occ, lec, day(1), records={s0: "present"})
    await make_session(occ, lec, day(2), records={s0: "late"})
    await make_session(occ, lec, day(3), records={s0: "excused"})
    await make_session(occ, lec, day(4), records={s0: "absent"})
    await make_session(occ, lec, day(5))

    async with AsyncSessionLocal() as db:
        rates = await course_rates(db, course)

    assert [r.matric_no for r in rates] == ["S0000001", "S0000002", "S0000003"]
    first = rates[0]
    assert first.student_id == s0
    assert (first.present, first.late, first.excused, first.absent) == (1, 1, 1, 2)
    assert first.closed_sessions == 5
    assert first.counted_sessions == 4
    assert first.rate == 50.0
    assert first.course_name == "Intro to Testing"
    assert rates[1].student_id == s1
    assert rates[1].rate == 0.0


async def test_course_rates_every_session_excused_is_none(classroom):
    s0 = classroom["student_ids"][0]
    occ = classroom["occurrence_id"]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]

    await make_session(occ, lec, day(1), records={s0: "excused"})
    await make_session(occ, lec, day(2), records={s0: "excused"})

    async with AsyncSessionLocal() as db:
        rates = await course_rates(db, course)

    first = next(r for r in rates if r.student_id == s0)
    assert first.excused == 2
    assert first.counted_sessions == 0
    assert first.rate is None


async def test_rates_match_student_app(classroom):
    s0 = classroom["student_ids"][0]
    occ = classroom["occurrence_id"]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]

    await make_session(occ, lec, day(1), records={s0: "present"})
    await make_session(occ, lec, day(2), records={s0: "late"})
    await make_session(occ, lec, day(3), records={s0: "excused"})
    await make_session(occ, lec, day(4), records={s0: "absent"})
    await make_session(occ, lec, day(5))
    tutorial_id = await add_occurrence(course, lec, [s0])
    await make_session(tutorial_id, lec, day(6), records={s0: "late"})

    async with AsyncSessionLocal() as db:
        rate = (await student_rates(db, s0))[0]
        counts = (await student_course_history(db, s0))[0]["counts"]

    assert rate.present == counts.present
    assert rate.late == counts.late
    assert rate.excused == counts.excused
    assert rate.absent == counts.absent
    assert rate.closed_sessions == counts.closed_sessions
    assert rate.counted_sessions == counts.counted_sessions
    assert rate.rate == counts.rate


async def test_student_rates_per_course_sorted(classroom):
    s0 = classroom["student_ids"][0]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]

    await enrol(s0, classroom["other_occurrence_id"])
    await make_session(classroom["occurrence_id"], lec, day(1), records={s0: "present"})

    async with AsyncSessionLocal() as db:
        rates = await student_rates(db, s0)

    assert [r.course_code for r in rates] == ["CS101", "CS202"]
    assert rates[0].course_id == course
    assert rates[0].rate == 100.0
    assert rates[1].course_code == "CS202"
    assert rates[1].closed_sessions == 0
    assert rates[1].rate is None


# ── Streaks ──────────────────────────────────────────────────────────────────

async def test_consecutive_absences(classroom):
    s0, s1, s2 = classroom["student_ids"]
    occ = classroom["occurrence_id"]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]

    await make_session(occ, lec, day(1), records={s0: "present", s1: "absent"})
    await make_session(occ, lec, day(2), records={s0: "absent", s1: "absent"})
    await make_session(occ, lec, day(3), records={s0: "excused", s1: "present"})
    await make_session(occ, lec, day(4), records={s0: "absent", s1: "absent"})
    await make_session(occ, lec, day(5), records={s1: "late"})

    async with AsyncSessionLocal() as db:
        streaks = await consecutive_absences(db, course)

    assert [s.student_id for s in streaks] == [s2, s0, s1]
    first = streaks[0]
    assert (first.current, first.longest, first.last_attended) == (5, 5, None)
    second = streaks[1]
    assert (second.current, second.longest, second.last_attended) == (3, 3, day(1))
    third = streaks[2]
    assert (third.current, third.longest, third.last_attended) == (0, 2, day(5))
    assert all(s.course_code == "CS101" for s in streaks)

    async with AsyncSessionLocal() as db:
        streaks = await consecutive_absences(db, course, min_current=3)

    assert [s.student_id for s in streaks] == [s2, s0]


# ── Edge cases ───────────────────────────────────────────────────────────────

async def test_unknown_course_or_student_is_empty(classroom):
    async with AsyncSessionLocal() as db:
        assert await course_records(db, 999999) == []
        assert await course_rates(db, 999999) == []
        assert await consecutive_absences(db, 999999) == []
        assert await student_rates(db, 999999) == []
        assert await student_records(db, 999999) == []


async def test_rows_are_frozen(classroom):
    occ = classroom["occurrence_id"]
    lec = classroom["lecturer_id"]
    course = classroom["course_id"]

    await make_session(occ, lec, day(1), records={classroom["student_ids"][0]: "present"})

    async with AsyncSessionLocal() as db:
        row = (await course_records(db, course))[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        row.status = "present"
