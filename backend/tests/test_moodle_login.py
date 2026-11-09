"""T10: POST /auth/moodle-login (FR-101, FR-102, FR-106, NFR-05).

Moodle is mocked with respx; the `moodle` tests at the bottom use the local SPeCTRUM simulation.
"""
import json
import logging
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.user import Lecturer, Student, User

PASSWORD = "S3cret-Moodle-Pass!"


def _url(path: str) -> str:
    return f"{settings.MOODLE_URL.rstrip('/')}{path}"


def mock_moodle(*, user_id=42, username="23004001", fullname="Ali Hassan", email="ali@siswa.um.edu.my",
                idnumber="", department="FSKTM", roles=("student",), token_body=None):
    """Mock token.php + the four web-service calls for one Moodle user enrolled in one course."""
    respx.post(_url("/login/token.php")).mock(
        return_value=httpx.Response(200, json=token_body or {"token": "user-token", "privatetoken": None}))

    def ws(request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        assert form["wstoken"] == "user-token"
        fn = form["wsfunction"]
        if fn == "core_webservice_get_site_info":
            return httpx.Response(200, json={"userid": user_id, "username": username, "fullname": fullname})
        if fn == "core_user_get_users_by_field":
            return httpx.Response(200, json=[{"id": user_id, "username": username, "fullname": fullname,
                                              "email": email, "idnumber": idnumber, "department": department}])
        if fn == "core_enrol_get_users_courses":
            return httpx.Response(200, json=[{"id": 7, "shortname": "WIF3001"}])
        if fn == "core_enrol_get_enrolled_users":
            return httpx.Response(200, json=[
                {"id": 99, "roles": [{"shortname": "editingteacher"}]},
                {"id": user_id, "roles": [{"shortname": r} for r in roles]},
            ])
        raise AssertionError(f"unexpected wsfunction {fn}")

    respx.post(_url("/webservice/rest/server.php")).mock(side_effect=ws)


async def _login(client, username="23004001", password=PASSWORD):
    return await client.post("/auth/moodle-login", json={"username": username, "password": password})


# ── unit tests (respx) ────────────────────────────────────────────────────────

@pytest.mark.db
@respx.mock
async def test_first_login_creates_student_and_returns_login_shape(client, db_session):
    mock_moodle(idnumber="23004001")
    resp = await _login(client)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"access_token", "refresh_token", "token_type", "user"}
    assert body["token_type"] == "bearer"
    user = body["user"]
    assert user["role"] == "student"
    assert user["email"] == "ali@siswa.um.edu.my"
    assert user["name"] == "Ali Hassan"
    assert user["student"]["matric_no"] == "23004001"
    assert user["lecturer"] is None

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["id"] == user["id"]
    refreshed = await client.post("/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert refreshed.status_code == 200

    row = (await db_session.execute(select(User).where(User.id == user["id"]))).scalar_one()
    assert row.moodle_user_id == 42
    assert row.password_hash is None  # NFR-05: no Moodle password stored, not even hashed


@pytest.mark.db
@respx.mock
async def test_teacher_role_in_any_course_makes_a_lecturer(client):
    mock_moodle(user_id=50, username="aminah", fullname="Aminah Rahman", email="aminah@um.edu.my",
                idnumber="STAFF123", roles=("editingteacher",))
    resp = await _login(client, username="aminah")
    assert resp.status_code == 200, resp.text
    user = resp.json()["user"]
    assert user["role"] == "lecturer"
    assert user["lecturer"]["staff_id"] == "STAFF123"
    assert user["lecturer"]["dept"] == "FSKTM"
    assert user["student"] is None


@pytest.mark.db
@respx.mock
async def test_second_login_updates_the_same_account(client, db_session):
    mock_moodle(idnumber="23004001")
    first = (await _login(client)).json()["user"]

    respx.reset()
    mock_moodle(fullname="Ali bin Hassan", email="ali.new@siswa.um.edu.my", idnumber="23004001")
    resp = await _login(client)
    assert resp.status_code == 200, resp.text
    second = resp.json()["user"]
    assert second["id"] == first["id"]
    assert second["name"] == "Ali bin Hassan"
    assert second["email"] == "ali.new@siswa.um.edu.my"
    assert (await db_session.execute(select(func.count(User.id)))).scalar_one() == 1
    assert (await db_session.execute(select(func.count(Student.id)))).scalar_one() == 1


@pytest.mark.db
@respx.mock
async def test_existing_account_with_same_email_is_linked_not_duplicated(client, db_session, users):
    # conftest `users` has student.test@siswa.um.edu.my with matric S0000001
    mock_moodle(email="Student.Test@siswa.um.edu.my", idnumber="")
    resp = await _login(client)
    assert resp.status_code == 200, resp.text
    user = resp.json()["user"]
    assert user["id"] == users["student"].id
    assert user["student"]["matric_no"] == "S0000001"  # no Moodle idnumber: the real matric is kept
    assert (await db_session.execute(select(func.count(Student.id)))).scalar_one() == 1


@pytest.mark.db
@respx.mock
async def test_no_idnumber_uses_username_as_matric(client):
    mock_moodle(username="student1", idnumber="")
    resp = await _login(client, username="student1")
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["student"]["matric_no"] == "student1"


@pytest.mark.db
@respx.mock
async def test_student_who_starts_teaching_becomes_lecturer(client, db_session):
    mock_moodle(idnumber="23004001")
    first = (await _login(client)).json()["user"]
    respx.reset()
    mock_moodle(idnumber="23004001", roles=("teacher",))
    resp = await _login(client)
    assert resp.status_code == 200, resp.text
    user = resp.json()["user"]
    assert user["id"] == first["id"] and user["role"] == "lecturer"
    assert user["lecturer"]["staff_id"] == "23004001"
    assert user["student"] is None  # only the current role's profile is shown
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {resp.json()['access_token']}"})
    assert me.json()["student"] is None and me.json()["lecturer"] is not None
    assert (await db_session.execute(select(func.count(Lecturer.id)))).scalar_one() == 1

    logs = (await db_session.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all()
    assert [log.action for log in logs] == ["MOODLE_ACCOUNT_CREATE", "MOODLE_ROLE_CHANGE"]
    change = logs[1]
    assert change.actor_id == user["id"] and change.target_id == str(user["id"])
    assert json.loads(change.old_val) == {"role": "student"} and json.loads(change.new_val) == {"role": "lecturer"}


@pytest.mark.db
@respx.mock
async def test_first_login_is_audited_and_relogin_without_changes_is_not(client, db_session):
    mock_moodle()
    user = (await _login(client)).json()["user"]
    assert (await _login(client)).status_code == 200
    logs = (await db_session.execute(select(AuditLog))).scalars().all()
    assert [(log.action, log.actor_id) for log in logs] == [("MOODLE_ACCOUNT_CREATE", user["id"])]
    assert json.loads(logs[0].new_val)["role"] == "student"


@pytest.mark.db
@respx.mock
async def test_wrong_credentials_give_generic_401(client, users):
    respx.post(_url("/login/token.php")).mock(return_value=httpx.Response(
        200, json={"error": "Invalid login, please try again", "errorcode": "invalidlogin"}))
    resp = await _login(client, password="wrong")
    local = await client.post("/auth/login", json={"email": "nobody@um.edu.my", "password": "x"})
    assert resp.status_code == 401
    assert resp.json() == local.json()  # same generic message as local login


@pytest.mark.db
@respx.mock
async def test_suspended_moodle_account_gives_401(client):
    respx.post(_url("/login/token.php")).mock(return_value=httpx.Response(
        200, json={"error": "Your account has been suspended", "errorcode": "suspended"}))
    assert (await _login(client)).status_code == 401


@pytest.mark.db
@respx.mock
@pytest.mark.parametrize("token_response", [
    httpx.ConnectError("connection refused"),
    httpx.ReadTimeout("timed out"),
    httpx.Response(500, text="Internal Server Error"),
    httpx.Response(200, text="<html>maintenance</html>"),
    httpx.Response(200, json={"error": "Web services are not enabled", "errorcode": "enablewsdescription"}),
])
async def test_moodle_down_gives_503(client, db_session, token_response):
    route = respx.post(_url("/login/token.php"))
    if isinstance(token_response, Exception):
        route.mock(side_effect=token_response)
    else:
        route.mock(return_value=token_response)
    resp = await _login(client)
    assert resp.status_code == 503
    assert PASSWORD not in resp.text
    assert (await db_session.execute(select(func.count(User.id)))).scalar_one() == 0


@pytest.mark.db
@respx.mock
async def test_moodle_failing_after_token_gives_503_and_creates_nothing(client, db_session):
    respx.post(_url("/login/token.php")).mock(return_value=httpx.Response(200, json={"token": "user-token"}))
    respx.post(_url("/webservice/rest/server.php")).mock(return_value=httpx.Response(
        200, json={"exception": "webservice_access_exception", "errorcode": "accessexception", "message": "no"}))
    resp = await _login(client)
    assert resp.status_code == 503
    assert (await db_session.execute(select(func.count(User.id)))).scalar_one() == 0


@pytest.mark.db
@respx.mock
async def test_password_is_sent_only_to_token_endpoint_and_never_logged(client, caplog):
    caplog.set_level(logging.DEBUG)
    mock_moodle()
    resp = await _login(client)
    assert resp.status_code == 200, resp.text
    token_calls = [c for c in respx.calls if c.request.url.path.endswith("/login/token.php")]
    assert len(token_calls) == 1
    assert PASSWORD.encode() not in token_calls[0].request.url.query  # POST body, not the URL
    for call in respx.calls:
        if not call.request.url.path.endswith("/login/token.php"):
            assert PASSWORD.encode() not in call.request.content
    assert PASSWORD not in caplog.text
    assert PASSWORD not in resp.text

    # also on the failure path
    caplog.clear()
    respx.reset()
    respx.post(_url("/login/token.php")).mock(side_effect=httpx.ConnectError("refused"))
    assert (await _login(client)).status_code == 503
    assert PASSWORD not in caplog.text


@pytest.mark.db
@respx.mock
async def test_admin_account_cannot_sign_in_through_moodle(client, users):
    mock_moodle(email="admin@um.edu.my")
    resp = await _login(client)
    assert resp.status_code == 401


@pytest.mark.db
@respx.mock
async def test_deactivated_account_cannot_sign_in_through_moodle(client, db_session):
    db_session.add(User(email="gone@siswa.um.edu.my", password_hash=hash_password("x"), role="student",
                        name="Gone", status="inactive", moodle_user_id=42))
    await db_session.commit()
    mock_moodle(email="gone@siswa.um.edu.my")
    resp = await _login(client)
    assert resp.status_code == 403
    assert "deactivated" in resp.json()["detail"]
    row = (await db_session.execute(select(User).where(User.moodle_user_id == 42))).scalar_one()
    await db_session.refresh(row)
    assert row.status == "inactive" and row.name == "Gone"


@pytest.mark.db
async def test_moodle_account_cannot_use_local_login(client, db_session):
    db_session.add(User(email="m@siswa.um.edu.my", password_hash=None, role="student", name="M",
                        status="active", moodle_user_id=5))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"email": "m@siswa.um.edu.my", "password": ""})
    assert resp.status_code == 401


async def test_empty_username_or_password_is_rejected(client):
    assert (await client.post("/auth/moodle-login", json={"username": "", "password": "x"})).status_code == 422
    assert (await client.post("/auth/moodle-login", json={"username": "x", "password": ""})).status_code == 422


# ── against the local Moodle (SPeCTRUM simulation) ───────────────────────────

@pytest.mark.db
@pytest.mark.moodle
async def test_local_moodle_student1_logs_in(client):
    resp = await _login(client, username="student1", password="Student123!")
    assert resp.status_code == 200, resp.text
    user = resp.json()["user"]
    assert user["role"] == "student"
    assert user["email"] == "student1@example.com"
    assert user["student"] is not None


@pytest.mark.db
@pytest.mark.moodle
async def test_local_moodle_lecturer1_is_a_lecturer(client):
    resp = await _login(client, username="lecturer1", password="Lecturer123!")
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["role"] == "lecturer"


@pytest.mark.db
@pytest.mark.moodle
async def test_local_moodle_wrong_password_is_401(client):
    resp = await _login(client, username="student1", password="not-the-password")
    assert resp.status_code == 401
