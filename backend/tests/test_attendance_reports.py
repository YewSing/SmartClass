"""T33: attendance reports + CSV export for a course/date range (FR-310)."""
import csv
import io
from datetime import date, datetime

import pytest
from sqlalchemy import delete, update

from app.models.attendance import AttendanceRecord
from app.models.session import AttendanceSession

pytestmark = pytest.mark.db

EXPORT = "/lecturer/occurrences/{occ}/attendance/export"
REPORT = "/lecturer/classes/{occ}/attendance/report"


async def _open(c, classroom) -> int:
    resp = await c.post("/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _records(db, session_id, classroom, statuses) -> None:
    """One record per student in classroom["student_ids"] order; None means no record."""
    for student_id, status in zip(classroom["student_ids"], statuses):
        if status is None:
            continue
        db.add(AttendanceRecord(session_id=session_id, student_id=student_id, status=status))
    await db.commit()


async def _date(db, session_id, d: date, hh: int = 8) -> None:
    sess = await db.get(AttendanceSession, session_id)
    sess.class_date = d
    sess.starts_at = datetime(d.year, d.month, d.day, hh, 0)
    await db.commit()


async def _close(c, session_id: int) -> None:
    resp = await c.put(f"/lecturer/sessions/{session_id}/close")
    assert resp.status_code == 200, resp.text


async def _closed_session(c, db, classroom, d: date, statuses) -> int:
    session_id = await _open(c, classroom)
    await _records(db, session_id, classroom, statuses)
    await _date(db, session_id, d)
    await _close(c, session_id)
    return session_id


def _csv(resp) -> list[list[str]]:
    return list(csv.reader(io.StringIO(resp.text)))


# ── Session CSV ──────────────────────────────────────────────────────────────

async def test_session_csv_closed_session_rows(lecturer_client, classroom, db_session):
    session_id = await _open(lecturer_client, classroom)
    await _records(db_session, session_id, classroom, ("late", None, None))
    override = await lecturer_client.put(
        f"/lecturer/sessions/{session_id}/attendance/override",
        json={"student_id": classroom["student_ids"][1], "status": "excused", "reason": "Medical leave"},
    )
    assert override.status_code == 200, override.text
    await _close(lecturer_client, session_id)

    resp = await lecturer_client.get(f"/lecturer/sessions/{session_id}/export")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    rows = _csv(resp)
    assert rows[0] == ["Matric No", "Name", "Status", "Detected At", "Overridden"]
    assert [(r[0], r[1], r[2], r[4]) for r in rows[1:]] == [
        ("S0000001", "Test Student", "late", "No"),
        ("S0000002", "Student 2", "excused", "Yes"),
        ("S0000003", "Student 3", "absent", "No"),
    ]


async def test_session_csv_open_session_marks_missing_not_recorded(lecturer_client, classroom, db_session):
    session_id = await _open(lecturer_client, classroom)
    await _records(db_session, session_id, classroom, ("present", None, None))

    resp = await lecturer_client.get(f"/lecturer/sessions/{session_id}/export")
    assert resp.status_code == 200, resp.text
    assert [r[2] for r in _csv(resp)[1:]] == ["present", "not_recorded", "not_recorded"]


async def test_session_csv_filename_uses_class_date(lecturer_client, classroom, db_session):
    session_id = await _open(lecturer_client, classroom)
    await _date(db_session, session_id, date(2026, 10, 5))

    resp = await lecturer_client.get(f"/lecturer/sessions/{session_id}/export")
    assert resp.status_code == 200, resp.text
    assert "attendance_CS101_20261005.csv" in resp.headers["content-disposition"]


# ── Class CSV ────────────────────────────────────────────────────────────────

async def test_class_csv_all_four_statuses_and_rate(lecturer_client, classroom, db_session):
    await _closed_session(lecturer_client, db_session, classroom, date(2026, 10, 5),
                          ("present", "late", "excused"))
    await _closed_session(lecturer_client, db_session, classroom, date(2026, 10, 12),
                          ("absent", "excused", "excused"))

    url = EXPORT.format(occ=classroom["occurrence_id"])
    resp = await lecturer_client.get(url)
    assert resp.status_code == 200, resp.text
    assert "attendance_report_CS101_20261005_20261012.csv" in resp.headers["content-disposition"]
    rows = _csv(resp)
    assert rows[0] == [
        "Matric No", "Name", "2026-10-05 08:00", "2026-10-12 08:00",
        "Present", "Late", "Excused", "Absent", "Total", "Rate",
    ]
    assert rows[1] == ["S0000001", "Test Student", "P", "A", "1", "0", "0", "1", "1/2", "50.0%"]
    assert rows[2] == ["S0000002", "Student 2", "L", "E", "0", "1", "1", "0", "1/1", "100.0%"]
    # Every session excused → nothing counts → blank rate, never 0.0%.
    assert rows[3] == ["S0000003", "Student 3", "E", "E", "0", "0", "2", "0", "0/0", ""]


async def test_class_csv_missing_record_in_closed_session_is_absent(lecturer_client, classroom, db_session):
    session_id = await _closed_session(lecturer_client, db_session, classroom, date(2026, 10, 5),
                                       ("present", None, None))
    # Closing through the API writes Absent rows for everyone; delete them so the report's own
    # missing-record rule (absent in a closed session) is what is tested.
    await db_session.execute(delete(AttendanceRecord).where(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.status == "absent",
    ))
    await db_session.commit()

    resp = await lecturer_client.get(EXPORT.format(occ=classroom["occurrence_id"]))
    assert resp.status_code == 200, resp.text
    rows = _csv(resp)
    assert [r[2] for r in rows[1:]] == ["P", "A", "A"]


async def test_class_csv_from_to_is_inclusive_by_class_date(lecturer_client, classroom, db_session):
    for d in (date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19)):
        await _closed_session(lecturer_client, db_session, classroom, d,
                              ("present", "present", "present"))

    url = EXPORT.format(occ=classroom["occurrence_id"])

    def session_columns(rows: list[list[str]]) -> list[str]:
        return rows[0][2:-6]

    rows = _csv(await lecturer_client.get(url, params={"from": "2026-10-12", "to": "2026-10-12"}))
    assert session_columns(rows) == ["2026-10-12 08:00"]

    rows = _csv(await lecturer_client.get(url, params={"from": "2026-10-12"}))
    assert session_columns(rows) == ["2026-10-12 08:00", "2026-10-19 08:00"]

    rows = _csv(await lecturer_client.get(url, params={"to": "2026-10-05"}))
    assert session_columns(rows) == ["2026-10-05 08:00"]

    new_names = _csv(await lecturer_client.get(
        url, params={"from": "2026-10-12", "to": "2026-10-19"}))
    old_names = _csv(await lecturer_client.get(
        url, params={"from_date": "2026-10-12", "to_date": "2026-10-19"}))
    assert session_columns(new_names) == session_columns(old_names)


async def test_class_csv_only_closed_sessions(lecturer_client, classroom, db_session):
    await _closed_session(lecturer_client, db_session, classroom, date(2026, 10, 5),
                          ("present", "present", "present"))

    cancelled = await _open(lecturer_client, classroom)
    await db_session.execute(update(AttendanceSession).where(AttendanceSession.id == cancelled).values(
        status="cancelled",
        class_date=date(2026, 10, 6),
        starts_at=datetime(2026, 10, 6, 8, 0),
    ))
    await db_session.commit()

    needs_confirmation = await _open(lecturer_client, classroom)
    await db_session.execute(update(AttendanceSession).where(
        AttendanceSession.id == needs_confirmation).values(
        status="needs_confirmation",
        class_date=date(2026, 10, 7),
        starts_at=datetime(2026, 10, 7, 8, 0),
    ))
    await db_session.commit()

    await _open(lecturer_client, classroom)  # left open

    resp = await lecturer_client.get(EXPORT.format(occ=classroom["occurrence_id"]))
    assert resp.status_code == 200, resp.text
    assert _csv(resp)[0][2:-6] == ["2026-10-05 08:00"]


async def test_class_csv_no_sessions(lecturer_client, classroom):
    resp = await lecturer_client.get(EXPORT.format(occ=classroom["occurrence_id"]))
    assert resp.status_code == 200, resp.text
    rows = _csv(resp)
    assert rows[0] == ["Matric No", "Name", "Present", "Late", "Excused", "Absent", "Total", "Rate"]
    assert len(rows) == 4
    for row in rows[1:]:
        assert row[2:] == ["0", "0", "0", "0", "0/0", ""]


async def test_from_after_to_is_422(lecturer_client, classroom):
    params = {"from": "2026-10-12", "to": "2026-10-05"}

    resp = await lecturer_client.get(EXPORT.format(occ=classroom["occurrence_id"]), params=params)
    assert resp.status_code == 422, resp.text

    resp = await lecturer_client.get(REPORT.format(occ=classroom["occurrence_id"]), params=params)
    assert resp.status_code == 422, resp.text


# ── JSON report ──────────────────────────────────────────────────────────────

async def test_report_json_matches_csv(lecturer_client, classroom, db_session):
    await _closed_session(lecturer_client, db_session, classroom, date(2026, 10, 5),
                          ("present", "late", "excused"))
    await _closed_session(lecturer_client, db_session, classroom, date(2026, 10, 12),
                          ("absent", "excused", "excused"))
    occ = classroom["occurrence_id"]

    resp = await lecturer_client.get(REPORT.format(occ=occ))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [s["label"] for s in body["sessions"]] == ["2026-10-05 08:00", "2026-10-12 08:00"]

    first = body["students"][0]
    assert first["statuses"] == ["present", "absent"]
    assert first["rate"] == 50.0
    assert body["students"][2]["rate"] is None
    assert body["students"][2]["excused"] == 2

    rates = (await lecturer_client.get(f"/lecturer/classes/{occ}/attendance/rates")).json()
    by_id = {s["student_id"]: s for s in rates["students"]}
    fields = ("present", "late", "excused", "absent", "closed_sessions", "counted_sessions", "rate")
    for student in body["students"]:
        expected = by_id[student["student_id"]]
        assert {f: student[f] for f in fields} == {f: expected[f] for f in fields}


async def test_report_json_date_range_echoed(lecturer_client, classroom, db_session):
    await _closed_session(lecturer_client, db_session, classroom, date(2026, 10, 5),
                          ("present", "present", "present"))
    await _closed_session(lecturer_client, db_session, classroom, date(2026, 10, 12),
                          ("present", "present", "present"))

    resp = await lecturer_client.get(
        REPORT.format(occ=classroom["occurrence_id"]), params={"from": "2026-10-12"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["from_date"] == "2026-10-12"
    assert body["to_date"] is None
    assert [s["label"] for s in body["sessions"]] == ["2026-10-12 08:00"]


async def test_report_access(
    lecturer_client, other_lecturer_client, admin_client, classroom
):
    occ = classroom["occurrence_id"]
    assert (await lecturer_client.get(REPORT.format(occ=999999))).status_code == 404
    assert (await other_lecturer_client.get(REPORT.format(occ=occ))).status_code == 403
    assert (await admin_client.get(REPORT.format(occ=occ))).status_code == 403
