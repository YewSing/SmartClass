"""Camera device keys and heartbeats (FR-408, NFR-07, NFR-23).

Each device gets its own random key, shown to the admin once. Only its SHA-256 hash is stored:
the key is 256 random bits, so a slow password hash adds nothing and a plain hash can be looked
up directly. Regenerating a key replaces the hash, which revokes the old key at once.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.timezone import now_myt
from app.models.camera import Camera

KEY_PREFIX = "scd_"


def clock() -> datetime:
    """Current naive MYT time. Tests monkeypatch this (controlled clock)."""
    return now_myt()


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def issue_key(camera: Camera, now: datetime | None = None) -> str:
    """Give the camera a new key (revoking any old one) and return it. The caller commits."""
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    camera.key_hash = hash_key(key)
    camera.key_created_at = now or clock()
    return key


def new_device_id() -> str:
    return f"CAM-{secrets.token_hex(4).upper()}"


def is_online(camera: Camera, now: datetime | None = None) -> bool:
    if camera.last_heartbeat_at is None:
        return False
    now = now or clock()
    return now - camera.last_heartbeat_at <= timedelta(seconds=settings.DEVICE_ONLINE_SECONDS)


async def authenticate(db: AsyncSession, key: str) -> Camera | None:
    if not key:
        return None
    return (await db.execute(select(Camera).where(Camera.key_hash == hash_key(key)))).scalar_one_or_none()


async def require_device(
    x_device_key: str = Header(..., description="The camera device's own key (FR-408)"),
    db: AsyncSession = Depends(get_db),
) -> Camera:
    """Dependency for device endpoints: the camera whose key is in `X-Device-Key`, else 401."""
    camera = await authenticate(db, x_device_key)
    if camera is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device key")
    return camera
