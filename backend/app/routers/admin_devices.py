"""Admin camera device registry (FR-408): register, list with online status, regenerate key."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.camera import Camera
from app.models.user import User
from app.services import device_service
from app.services.audit_service import write_log

router = APIRouter(prefix="/admin/devices", tags=["admin-devices"])

_admin_only = require_role("admin")


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    room: str = Field(min_length=1, max_length=255)

    @field_validator("name", "room")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class DeviceOut(BaseModel):
    id: int
    name: str
    room: str
    device_id: str
    online: bool
    last_heartbeat_at: Optional[datetime]
    has_key: bool
    key_created_at: Optional[datetime]


class DeviceWithKey(DeviceOut):
    key: str  # shown once; only its hash is stored


def _out(cam: Camera, now: datetime) -> dict:
    return dict(
        id=cam.id, name=cam.label, room=cam.room, device_id=cam.device_id,
        online=device_service.is_online(cam, now), last_heartbeat_at=cam.last_heartbeat_at,
        has_key=cam.key_hash is not None, key_created_at=cam.key_created_at,
    )


@router.get("", response_model=list[DeviceOut])
async def list_devices(db: AsyncSession = Depends(get_db), _: User = Depends(_admin_only)):
    now = device_service.clock()
    cams = (await db.execute(select(Camera).order_by(Camera.room))).scalars().all()
    return [_out(c, now) for c in cams]


@router.post("", response_model=DeviceWithKey, status_code=status.HTTP_201_CREATED)
async def register_device(
    body: DeviceCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(_admin_only)
):
    taken = (await db.execute(select(Camera.id).where(Camera.room == body.room))).first()
    if taken:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Room {body.room} already has a device; regenerate its key instead.")
    now = device_service.clock()
    cam = Camera(label=body.name, room=body.room, device_id=device_service.new_device_id())
    key = device_service.issue_key(cam, now)
    db.add(cam)
    await db.flush()
    await write_log(db, admin.id, "DEVICE_REGISTER", "camera", cam.id,
                    new_val={"name": cam.label, "room": cam.room, "device_id": cam.device_id})
    return {**_out(cam, now), "key": key}


@router.post("/{camera_id}/regenerate-key", response_model=DeviceWithKey)
async def regenerate_key(
    camera_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(_admin_only)
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    now = device_service.clock()
    had_key = cam.key_hash is not None
    key = device_service.issue_key(cam, now)
    await write_log(db, admin.id, "DEVICE_KEY_REGENERATE", "camera", cam.id,
                    old_val={"had_key": had_key}, new_val={"key_created_at": now.isoformat()})
    return {**_out(cam, now), "key": key}
