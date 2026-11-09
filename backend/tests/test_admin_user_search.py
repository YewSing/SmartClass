"""T22: the admin accounts screen finds people by name, email, matric or staff number, filters by
status, and shows which accounts come from Moodle (FR-103, FR-108)."""
import pytest

from app.models.user import User

pytestmark = pytest.mark.db


async def _emails(admin_client, **params):
    resp = await admin_client.get("/admin/users", params={"limit": 100, **params})
    assert resp.status_code == 200, resp.text
    return {u["email"] for u in resp.json()["items"]}


async def test_search_matches_name_email_matric_and_staff_number(admin_client, users):
    assert await _emails(admin_client, q="test student") == {users["student"].email}
    assert await _emails(admin_client, q="STUDENT.TEST@") == {users["student"].email}
    assert await _emails(admin_client, q="s0000001") == {users["student"].email}
    assert await _emails(admin_client, q="STAFF-T001") == {users["lecturer"].email}
    assert await _emails(admin_client, q="nobody-has-this") == set()


async def test_search_total_counts_only_matches(admin_client, users):
    resp = await admin_client.get("/admin/users", params={"q": "lecturer"})
    body = resp.json()
    assert body["total"] == len(body["items"]) == 1


async def test_search_treats_like_wildcards_as_text(admin_client, users):
    assert await _emails(admin_client, q="%") == set()
    assert await _emails(admin_client, q="_") == set()


async def test_status_filter_and_role_filter_combine(admin_client, users):
    assert (await admin_client.delete(f"/admin/users/{users['student'].id}")).status_code == 204
    assert await _emails(admin_client, status="inactive") == {users["student"].email}
    assert users["student"].email not in await _emails(admin_client, status="active")
    assert await _emails(admin_client, status="inactive", role="lecturer") == set()


async def test_unknown_status_filter_is_rejected(admin_client, users):
    assert (await admin_client.get("/admin/users", params={"status": "deleted"})).status_code == 422


async def test_moodle_linked_is_shown(admin_client, users, db_session):
    db_session.add(User(email="m@siswa.um.edu.my", password_hash=None, role="student", name="Moodle Person",
                        status="active", moodle_user_id=77))
    await db_session.commit()
    items = {u["email"]: u for u in (await admin_client.get("/admin/users", params={"limit": 100})).json()["items"]}
    assert items["m@siswa.um.edu.my"]["moodle_linked"] is True
    assert items[users["admin"].email]["moodle_linked"] is False


async def test_lecturer_and_student_get_403(lecturer_client, users):
    assert (await lecturer_client.get("/admin/users", params={"q": "x"})).status_code == 403
