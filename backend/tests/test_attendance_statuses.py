"""T30: four attendance statuses (FR-302–FR-304).

Present / Late / Excused / Absent. A face recognition is Present, or Late when it comes more
than ATTENDANCE_LATE_AFTER_MINUTES after the session's effective start. Only the first
recognition counts. Excused is only ever set by a lecturer override.
"""
import csv
import importlib.util
import io
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.attendance import AttendanceRecord
from app.models.face import FaceEmbedding
from app.models.session import AttendanceSession
from app.services import attendance_service, session_schedule
from app.services.session_service import get_session_counts

pytestmark = pytest.mark.db

MON = date(2026, 11, 16)

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic" / "versions" / "b8c9d0e1f2a3_four_attendance_statuses.py"
)


def at(h: int, m: int, d: date = MON) -> datetime:
    return datetime(d.year, d.month, d.day, h, m)


@pytest.fixture
def fixed_clock(monkeypatch):
    def set_clock(t: datetime) -> None:
        monkeypatch.setattr(session_schedule, "clock", lambda: t)
    return set_clock


async def run_tick(now: datetime) -> session_schedule.TickReport:
    async with AsyncSessionLocal() as db:
        report = await session_schedule.tick(db, now)
        await db.commit()
    return report


async def rows_for(db, occurrence_id: int) -> list[AttendanceSession]:
    db.expire_all()
    return (await db.execute(
        select(AttendanceSession)
        .where(AttendanceSession.occurrence_id == occurrence_id)
        .order_by(AttendanceSession.id)
    )).scalars().all()


async def records_for(db, session_id: int) -> list[AttendanceRecord]:
    db.expire_all()
    return (await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.student_id)
    )).scalars().all()


async def recognise(client, db, session_id: int, student_id: int, now: datetime,
                    fixed_clock, dry_run: bool = False) -> dict:
    """Give the student a unique face embedding, then call the internal face-match endpoint."""
    result = await db.execute(select(FaceEmbedding).where(FaceEmbedding.student_id == student_id))
    emb = result.scalar_one_or_none()
    if emb is None:
        index = await db.scalar(select(func.count()).select_from(FaceEmbedding))
        vec = [0.0] * 512
        vec[index] = 1.0
        emb = FaceEmbedding(student_id=student_id, embedding=vec)
        db.add(emb)
        await db.commit()
    vec = [float(x) for x in emb.embedding]

    fixed_clock(now)
    resp = await client.post(
        "/internal/face-match",
        json={"embedding": vec, "session_id": session_id, "dry_run": dry_run},
        headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matched"] is True
    return body


# ── The clock rule (FR-302) ──────────────────────────────────────────────────

def test_status_for_recognition_boundaries():
    session = AttendanceSession(starts_at=at(8, 0), opened_at=at(7, 45))
    assert attendance_service.status_for_recognition(session, at(7, 50)) == "present"
    assert attendance_service.status_for_recognition(session, at(8, 0)) == "present"
    assert attendance_service.status_for_recognition(session, at(8, 15)) == "present"  # exactly 15 min
    assert attendance_service.status_for_recognition(session, datetime(2026, 11, 16, 8, 15, 1)) == "late"
    assert attendance_service.status_for_recognition(session, at(9, 30)) == "late"

    session = AttendanceSession(starts_at=None, opened_at=at(9, 0))  # fall back to opened_at
    assert attendance_service.status_for_recognition(session, at(9, 16)) == "late"
    assert attendance_service.status_for_recognition(session, at(9, 10)) == "present"

    session = AttendanceSession(starts_at=None, opened_at=None)
    assert attendance_service.status_for_recognition(session, at(9, 10)) == "present"


def test_late_after_setting_is_configurable(monkeypatch):
    monkeypatch.setattr(settings, "ATTENDANCE_LATE_AFTER_MINUTES", 5)
    session = AttendanceSession(starts_at=at(8, 0), opened_at=at(7, 45))
    assert attendance_service.status_for_recognition(session, at(8, 6)) == "late"
    assert attendance_service.status_for_recognition(session, at(8, 5)) == "present"


async def test_recognition_before_cutoff_is_present(
    client, classroom, db_session, fixed_clock
):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])

    await recognise(client, db_session, row.id, classroom["student_ids"][0], at(8, 10), fixed_clock)

    [rec] = await records_for(db_session, row.id)
    assert rec.status == "present"
    assert rec.detected_at == at(8, 10)


async def test_recognition_after_cutoff_is_late(
    client, lecturer_client, classroom, db_session, fixed_clock
):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    session_id = row.id

    await recognise(client, db_session, session_id, classroom["student_ids"][0], at(8, 20), fixed_clock)

    [rec] = await records_for(db_session, session_id)
    assert rec.status == "late"

    roster = (await lecturer_client.get(f"/lecturer/sessions/{session_id}/attendance")).json()
    by_student = {r["student_id"]: r["status"] for r in roster}
    assert by_student[classroom["student_ids"][0]] == "late"

    sessions = (await lecturer_client.get("/lecturer/sessions")).json()
    item = next(s for s in sessions if s["id"] == session_id)
    assert (item["late"], item["present"], item["absent"]) == (1, 0, 2)


async def test_only_first_recognition_counts(client, classroom, db_session, fixed_clock):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    session_id = row.id
    first_student, second_student = classroom["student_ids"][:2]

    first = await recognise(client, db_session, session_id, first_student, at(8, 10), fixed_clock)
    assert first["already_present"] is False
    again = await recognise(client, db_session, session_id, first_student, at(8, 40), fixed_clock)
    assert again["already_present"] is True

    [rec] = await records_for(db_session, session_id)
    assert rec.status == "present"
    assert rec.detected_at == at(8, 10)  # the first recognition is kept

    # A dry run for a Late student also reports already_present.
    await recognise(client, db_session, session_id, second_student, at(8, 40), fixed_clock)
    dry = await recognise(client, db_session, session_id, second_student, at(8, 45), fixed_clock, dry_run=True)
    assert dry["already_present"] is True

    assert len(await records_for(db_session, session_id)) == 2


async def test_late_uses_effective_start_after_time_change(
    client, lecturer_client, classroom, db_session, fixed_clock
):
    fixed_clock(at(7, 0))
    resp = await lecturer_client.put(
        f"/lecturer/classes/{classroom['occurrence_id']}/dates/{MON.isoformat()}",
        json={"start_time": "09:00", "end_time": "11:00"},
    )
    assert resp.status_code == 200, resp.text

    await run_tick(at(8, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.starts_at == at(9, 0)

    await recognise(client, db_session, row.id, classroom["student_ids"][0], at(9, 10), fixed_clock)

    [rec] = await records_for(db_session, row.id)
    assert rec.status == "present"  # would be Late against the original 08:00 start


async def test_start_now_late_clock_starts_at_start_now(
    client, lecturer_client, classroom, db_session, fixed_clock
):
    fixed_clock(at(11, 0))
    resp = await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["id"]
    first_student, second_student = classroom["student_ids"][:2]

    await recognise(client, db_session, session_id, first_student, at(11, 20), fixed_clock)
    await recognise(client, db_session, session_id, second_student, at(11, 10), fixed_clock)

    by_student = {r.student_id: r.status for r in await records_for(db_session, session_id)}
    assert by_student == {first_student: "late", second_student: "present"}


async def test_close_marks_absent_never_excused(client, classroom, db_session, fixed_clock):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    first_student, second_student, third_student = classroom["student_ids"]

    await recognise(client, db_session, row.id, first_student, at(8, 5), fixed_clock)
    await recognise(client, db_session, row.id, second_student, at(8, 30), fixed_clock)

    await run_tick(at(10, 0))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "closed"

    by_student = {r.student_id: r.status for r in await records_for(db_session, row.id)}
    assert by_student == {
        first_student: "present",
        second_student: "late",
        third_student: "absent",
    }
    assert "excused" not in by_student.values()


# ── Overrides ────────────────────────────────────────────────────────────────

async def test_override_accepts_four_statuses(lecturer_client, classroom, db_session):
    resp = await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["id"]
    first_student, second_student = classroom["student_ids"][:2]

    record = AttendanceRecord(session_id=session_id, student_id=first_student, status="absent")
    db_session.add(record)
    await db_session.commit()
    record_id = record.id

    for status_value in ("late", "excused", "present", "absent"):
        resp = await lecturer_client.put(
            f"/attendance/{record_id}/override", json={"status": status_value}
        )
        assert resp.status_code == 200, (status_value, resp.text)
        db_session.expire_all()
        assert (await db_session.get(AttendanceRecord, record_id)).status == status_value

    resp = await lecturer_client.put(
        f"/lecturer/sessions/{session_id}/attendance/override",
        json={"student_id": second_student, "status": "excused"},
    )
    assert resp.status_code == 200, resp.text
    created = (await db_session.execute(select(AttendanceRecord).where(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.student_id == second_student,
    ))).scalar_one()
    assert created.status == "excused"


async def test_override_rejects_unknown_status(lecturer_client, classroom, db_session):
    resp = await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["id"]
    first_student, second_student = classroom["student_ids"][:2]

    record = AttendanceRecord(session_id=session_id, student_id=first_student, status="absent")
    db_session.add(record)
    await db_session.commit()
    record_id = record.id

    for bad_status in ("unidentified", "not_recorded", ""):
        resp = await lecturer_client.put(
            f"/attendance/{record_id}/override", json={"status": bad_status}
        )
        assert resp.status_code == 400, (bad_status, resp.text)
        resp = await lecturer_client.put(
            f"/lecturer/sessions/{session_id}/attendance/override",
            json={"student_id": second_student, "status": bad_status},
        )
        assert resp.status_code == 400, (bad_status, resp.text)

    db_session.expire_all()
    assert (await db_session.get(AttendanceRecord, record_id)).status == "absent"
    count = await db_session.scalar(select(func.count()).select_from(AttendanceRecord).where(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.student_id == second_student,
    ))
    assert count == 0


async def test_db_rejects_other_status(lecturer_client, classroom, db_session):
    resp = await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )
    session_id = resp.json()["id"]
    db_session.add(AttendanceRecord(
        session_id=session_id, student_id=classroom["student_ids"][0], status="unidentified",
    ))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# ── Counts and exports ───────────────────────────────────────────────────────

async def test_counts_include_late_and_excused(lecturer_client, classroom, db_session):
    resp = await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )
    session_id = resp.json()["id"]
    first_student, second_student, third_student = classroom["student_ids"]
    db_session.add_all([
        AttendanceRecord(session_id=session_id, student_id=first_student, status="present"),
        AttendanceRecord(session_id=session_id, student_id=second_student, status="late"),
        AttendanceRecord(session_id=session_id, student_id=third_student, status="excused"),
    ])
    await db_session.commit()

    counts = await get_session_counts(session_id, db_session)
    assert counts == {"present": 1, "late": 1, "excused": 1, "absent": 0, "unid": 0}


async def test_occurrence_export_letters_and_rate(lecturer_client, classroom, db_session):
    first_student, second_student, third_student = classroom["student_ids"]

    async def add_records(session_id: int, statuses: tuple[str, str, str]) -> None:
        db_session.add_all([
            AttendanceRecord(session_id=session_id, student_id=first_student, status=statuses[0]),
            AttendanceRecord(session_id=session_id, student_id=second_student, status=statuses[1]),
            AttendanceRecord(session_id=session_id, student_id=third_student, status=statuses[2]),
        ])
        await db_session.commit()

    first = (await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )).json()["id"]
    await add_records(first, ("late", "excused", "absent"))
    assert (await lecturer_client.put(f"/lecturer/sessions/{first}/close")).status_code == 200

    second = (await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )).json()["id"]
    await add_records(second, ("present", "present", "absent"))
    assert (await lecturer_client.put(f"/lecturer/sessions/{second}/close")).status_code == 200

    resp = await lecturer_client.get(
        f"/lecturer/occurrences/{classroom['occurrence_id']}/attendance/export"
    )
    assert resp.status_code == 200, resp.text
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[0][:2] == ["Matric No", "Name"] and rows[0][-2:] == ["Total", "Rate"]
    assert rows[1][2:] == ["L", "P", "2/2", "100.0%"]
    assert rows[2][2:] == ["E", "P", "1/1", "100.0%"]
    assert rows[3][2:] == ["A", "A", "0/2", "0.0%"]


async def test_low_attendance_alert_counts_late(
    client, classroom, db_session, fixed_clock, monkeypatch
):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])

    calls = []

    async def fake_alert(session_id, present, db):
        calls.append((session_id, present))

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(attendance_service, "check_low_attendance_alert", fake_alert)
    monkeypatch.setattr(attendance_service.manager, "broadcast", noop)

    await recognise(client, db_session, row.id, classroom["student_ids"][0], at(8, 20), fixed_clock)

    assert calls == [(row.id, 1)]  # one Late student counts as one attended


# ── Data migration ──────────────────────────────────────────────────────────

async def test_migration_maps_unidentified_to_absent(lecturer_client, classroom, db_session):
    resp = await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )
    session_id = resp.json()["id"]
    student_id = classroom["student_ids"][0]

    await db_session.execute(text("ALTER TABLE attendance_records DROP CONSTRAINT ck_attendance_records_status"))
    await db_session.commit()
    try:
        await db_session.execute(
            text("INSERT INTO attendance_records (session_id, student_id, status) "
                 "VALUES (:session_id, :student_id, 'unidentified')"),
            {"session_id": session_id, "student_id": student_id},
        )
        await db_session.commit()

        spec = importlib.util.spec_from_file_location("migration_four_statuses", MIGRATION_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        await db_session.execute(module.MAP_UNKNOWN_TO_ABSENT)
        await db_session.commit()

        status = await db_session.scalar(
            text("SELECT status FROM attendance_records WHERE session_id = :session_id "
                 "AND student_id = :student_id"),
            {"session_id": session_id, "student_id": student_id},
        )
        assert status == "absent"
    finally:
        await db_session.execute(text(
            "ALTER TABLE attendance_records ADD CONSTRAINT ck_attendance_records_status "
            "CHECK (status IN ('present','late','excused','absent'))"
        ))
        await db_session.commit()
