import pytest
from sqlalchemy import select

from app.models.notification import Notification
from app.services.notification_service import deliver, event_content


def test_policy_and_stable_attendance_subject():
    first = event_content("attendance.recorded", {"session_id": 12, "status": "late", "message": "Recorded"})
    second = event_content("attendance.recorded", {"session_id": 12, "status": "late", "message": "Different copy"})
    assert first["event_key"] == second["event_key"]
    assert first["priority"] == "general"
    assert first["link"] == "/attendance/sessions/12"
    assert event_content("confusion.spike", {"event_id": 7})["priority"] == "urgent"
    assert event_content("face_enrolment.result", {"enrolment_id": 3})["priority"] == "important"


def test_external_notification_link_is_rejected():
    with pytest.raises(ValueError):
        event_content("quiz.published", {"quiz_id": 1, "link": "//untrusted.example"})


def test_recurring_events_and_custom_title():
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 11, 20, 8, tzinfo=timezone.utc)
    for event in ("quiz.deadline_reminder", "confusion.spike"):
        first = event_content(event, {"quiz_id": 1}, now)
        assert first["event_key"] == event_content(event, {"quiz_id": 1}, now)["event_key"]
        assert first["event_key"] != event_content(event, {"quiz_id": 1}, now + timedelta(hours=1))["event_key"]
    assert event_content("quiz.published", {"quiz_id": 1, "title": "Week 5 quiz"})["title"] == "Week 5 quiz"


@pytest.mark.db
async def test_feed_deduplicates_and_isolates_recipients(users, student_client, lecturer_client, db_session):
    payload = {"session_id": 42, "status": "present", "message": "Attendance recorded"}
    await deliver("attendance.recorded", [users["student"].id] * 2, payload)
    await deliver("attendance.recorded", [users["student"].id], payload)
    notes = (await student_client.get("/notifications")).json()
    assert len(notes) == 1
    assert notes[0]["message"] == "Attendance recorded"
    assert notes[0]["read_at"] is None
    assert (await lecturer_client.get("/notifications")).json() == []
    assert (await lecturer_client.post(f'/notifications/{notes[0]["id"]}/read')).status_code == 404
    response = await student_client.post(f'/notifications/{notes[0]["id"]}/read')
    assert response.status_code == 200
    assert response.json()["read_at"] is not None
    assert len((await db_session.scalars(select(Notification))).all()) == 1


@pytest.mark.db
async def test_read_all_only_changes_caller(users, student_client, lecturer_client):
    await deliver("quiz.published", [users["student"].id, users["lecturer"].id], {"quiz_id": 9})
    assert (await student_client.post("/notifications/read-all")).status_code == 204
    assert (await student_client.get("/notifications")).json()[0]["read_at"] is not None
    assert (await lecturer_client.get("/notifications")).json()[0]["read_at"] is None


@pytest.mark.db
async def test_dashboard_role_and_priority_scope(users, student_client, lecturer_client):
    await deliver("quiz.published", [users["student"].id], {"quiz_id": 9})
    await deliver("attendance.recorded", [users["student"].id], {"session_id": 3})
    response = await student_client.get("/student/me/dashboard")
    assert response.status_code == 200
    assert [n["event_type"] for n in response.json()["notifications"]] == ["quiz.published"]
    assert (await lecturer_client.get("/lecturer/dashboard")).json()["notifications"] == []
    assert (await student_client.get("/lecturer/dashboard")).status_code == 403
    assert (await lecturer_client.get("/student/me/dashboard")).status_code == 403


@pytest.mark.db
async def test_dashboard_student_status_and_lecturer_counts(classroom, student_client, lecturer_client, db_session):
    from app.core.timezone import now_myt
    from app.models.attendance import AttendanceRecord
    from app.models.class_ import ClassOccurrence
    from app.models.session import AttendanceSession

    now = now_myt()
    occurrence = await db_session.get(ClassOccurrence, classroom["occurrence_id"])
    occurrence.day_of_week = None  # an extra class without a weekly slot still belongs to today
    session = AttendanceSession(occurrence_id=occurrence.id, lecturer_id=classroom["lecturer_id"],
                                status="open", opened_at=now, class_date=now.date())
    db_session.add(session)
    await db_session.commit()
    body = (await student_client.get("/student/me/dashboard")).json()
    assert body["session"]["attendance_status"] == "not_recorded"
    assert body["session"]["counts"] is None
    assert body["live_sessions"] == [{
        "id": session.id, "occurrence_id": occurrence.id, "status": "open", "ends_at": None,
        "course_code": "CS101", "course_name": "Intro to Testing",
    }]
    assert body["today_classes"][0]["attendance_status"] == "not_recorded"
    db_session.add(AttendanceRecord(session_id=session.id, student_id=classroom["student_ids"][0], status="late"))
    await db_session.commit()
    body = (await student_client.get("/student/me/dashboard")).json()
    assert body["session"]["attendance_status"] == "late"
    lecturer_body = (await lecturer_client.get("/lecturer/dashboard")).json()
    assert lecturer_body["session"]["counts"]["late"] == 1
    assert lecturer_body["session"]["attendance_status"] is None
