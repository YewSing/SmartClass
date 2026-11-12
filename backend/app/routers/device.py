"""Endpoints called by camera devices, authenticated by their own `X-Device-Key` (FR-408, NFR-07)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.camera import Camera
from app.services import device_service

router = APIRouter(prefix="/device", tags=["device"])


@router.post("/heartbeat")
async def heartbeat(
    request: Request,
    camera: Camera = Depends(device_service.require_device),
    db: AsyncSession = Depends(get_db),
):
    """The device is alive. It counts as online for DEVICE_ONLINE_SECONDS after this (NFR-23)."""
    now = device_service.clock()
    camera.last_heartbeat_at = now
    if request.client:
        camera.ip_address = request.client.host[:50]
    await db.flush()
    return {"device_id": camera.device_id, "room": camera.room, "server_time": now}
