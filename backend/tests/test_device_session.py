"""T42: GET /device/session, the same session rule as POST /device/faces (FR-401)."""
import pytest

from tests.test_device_faces import open_session

pytestmark = pytest.mark.db

URL = "/device/session"


async def test_session_assigned_to_the_device(client, classroom, device):
    session_id = await open_session(classroom, device["id"])
    resp = await client.get(URL, headers=device["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"] == session_id
    assert body["occurrence_id"] == classroom["occurrence_id"]
    assert body["room"] == "DK1"


async def test_camera_less_session_in_the_devices_room(client, classroom, device):
    session_id = await open_session(classroom, None)
    resp = await client.get(URL, headers=device["headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["session_id"] == session_id


async def test_other_rooms_session_and_no_session_are_404(client, classroom, device):
    assert (await client.get(URL, headers=device["headers"])).status_code == 404

    await open_session(classroom, None, "other_occurrence_id")
    assert (await client.get(URL, headers=device["headers"])).status_code == 404


async def test_needs_a_valid_device_key(client, device):
    assert (await client.get(URL)).status_code == 422                       # header missing
    assert (await client.get(URL, headers={"X-Device-Key": "scd_wrong"})).status_code == 401
