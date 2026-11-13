"""T40: camera device registry, per-device keys and heartbeat (FR-408, NFR-07, NFR-23)."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.camera import Camera
from app.services import device_service

pytestmark = pytest.mark.db

T0 = datetime(2026, 11, 16, 8, 0, 0)


@pytest.fixture
def fixed_clock(monkeypatch):
    def set_clock(t: datetime) -> None:
        monkeypatch.setattr(device_service, "clock", lambda: t)
    set_clock(T0)
    return set_clock


async def _register(admin_client, name="DK3 door", room="DK3") -> dict:
    resp = await admin_client.post("/admin/devices", json={"name": name, "room": room})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _heartbeat(client, key):
    return await client.post("/device/heartbeat", headers={"X-Device-Key": key})


# ── Registering and keys ─────────────────────────────────────────────────────

async def test_register_returns_key_once_and_stores_only_its_hash(admin_client, users, db_session, fixed_clock):
    body = await _register(admin_client)
    key = body["key"]
    assert key.startswith("scd_") and len(key) > 40
    assert body["name"] == "DK3 door" and body["room"] == "DK3"
    assert body["has_key"] is True and body["online"] is False and body["last_heartbeat_at"] is None

    cam = (await db_session.execute(select(Camera).where(Camera.id == body["id"]))).scalar_one()
    assert cam.key_hash == device_service.hash_key(key)
    assert key not in (cam.key_hash, cam.device_id, cam.label)

    # The list never shows the key again
    listed = (await admin_client.get("/admin/devices")).json()
    [row] = [d for d in listed if d["id"] == body["id"]]
    assert "key" not in row and row["has_key"] is True

    log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "DEVICE_REGISTER"))).scalar_one()
    assert (log.actor_id, log.target_id) == (users["admin"].id, str(body["id"]))
    assert key not in (log.new_val or "")


async def test_register_rejects_second_device_for_a_room_and_blank_fields(admin_client):
    await _register(admin_client, room="DK3")
    resp = await admin_client.post("/admin/devices", json={"name": "Another", "room": "DK3"})
    assert resp.status_code == 409
    resp = await admin_client.post("/admin/devices", json={"name": "  ", "room": "DK4"})
    assert resp.status_code == 422


async def test_regenerate_key_revokes_the_old_one(admin_client, client, users, db_session, fixed_clock):
    body = await _register(admin_client)
    old_key = body["key"]
    assert (await _heartbeat(client, old_key)).status_code == 200

    resp = await admin_client.post(f"/admin/devices/{body['id']}/regenerate-key")
    assert resp.status_code == 200, resp.text
    new_key = resp.json()["key"]
    assert new_key != old_key

    assert (await _heartbeat(client, old_key)).status_code == 401
    assert (await _heartbeat(client, new_key)).status_code == 200

    log = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "DEVICE_KEY_REGENERATE"))).scalar_one()
    assert (log.actor_id, log.target_id) == (users["admin"].id, str(body["id"]))
    assert new_key not in (log.new_val or "") and old_key not in (log.old_val or "")

    assert (await admin_client.post("/admin/devices/999999/regenerate-key")).status_code == 404


async def test_seeded_camera_without_key_gets_one_by_regenerating(admin_client, client, db_session):
    cam = Camera(label="DK9", room="DK9", device_id="CAM-009")
    db_session.add(cam)
    await db_session.commit()
    [row] = [d for d in (await admin_client.get("/admin/devices")).json() if d["id"] == cam.id]
    assert row["has_key"] is False

    key = (await admin_client.post(f"/admin/devices/{cam.id}/regenerate-key")).json()["key"]
    assert (await _heartbeat(client, key)).status_code == 200


async def test_only_admins_manage_devices(lecturer_client, student_client, client):
    for c in (lecturer_client, student_client):
        assert (await c.get("/admin/devices")).status_code == 403
        assert (await c.post("/admin/devices", json={"name": "x", "room": "y"})).status_code == 403
        assert (await c.post("/admin/devices/1/regenerate-key")).status_code == 403
    assert (await client.get("/admin/devices")).status_code == 403  # no token: HTTPBearer answers 403 app-wide


# ── Heartbeat and online status ──────────────────────────────────────────────

async def test_heartbeat_marks_online_for_60_seconds(admin_client, client, fixed_clock):
    body = await _register(admin_client)
    fixed_clock(T0)
    resp = await _heartbeat(client, body["key"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["device_id"] == body["device_id"] and resp.json()["room"] == "DK3"

    def online() -> bool:
        return next(d for d in listed if d["id"] == body["id"])["online"]

    fixed_clock(T0 + timedelta(seconds=60))
    listed = (await admin_client.get("/admin/devices")).json()
    assert online() is True
    assert next(d for d in listed if d["id"] == body["id"])["last_heartbeat_at"] == T0.isoformat()

    fixed_clock(T0 + timedelta(seconds=61))
    listed = (await admin_client.get("/admin/devices")).json()
    assert online() is False

    # A new heartbeat brings it back
    await _heartbeat(client, body["key"])
    listed = (await admin_client.get("/admin/devices")).json()
    assert online() is True


async def test_heartbeat_needs_a_valid_device_key(client, admin_client):
    assert (await client.post("/device/heartbeat")).status_code == 422  # header missing
    assert (await _heartbeat(client, "")).status_code == 401
    assert (await _heartbeat(client, "scd_not-a-real-key")).status_code == 401
    # A user's bearer token is not a device key
    assert (await admin_client.post("/device/heartbeat")).status_code == 422


# ── The old /internal/* recognition path is gone (T46b) ─────────────────────

async def test_device_endpoints_refuse_the_old_shared_internal_key(client, device):
    from app.core.config import settings
    shared = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    for headers in (shared, device["headers"]):
        assert (await client.get("/internal/active-session", headers=headers)).status_code == 404
        assert (await client.post("/internal/face-match", headers=headers,
                                  json={"embedding": [0.0] * 512, "session_id": 1})).status_code == 404
        assert (await client.post("/internal/face-review", headers=headers,
                                  json={"embedding": [0.0] * 512})).status_code == 404
    # The device path takes the device's own key, never the shared one
    bad = {"X-Device-Key": settings.INTERNAL_API_KEY}
    assert (await client.get("/device/session", headers=bad)).status_code == 401
