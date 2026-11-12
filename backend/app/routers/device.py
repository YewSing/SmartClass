"""Endpoints called by camera devices, authenticated by their own `X-Device-Key` (FR-408, NFR-07)."""
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.camera import Camera
from app.schemas.device import DeviceFacesResponse
from app.services import device_service, recognition_service

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


@router.post("/faces", response_model=DeviceFacesResponse)
async def faces(
    request: Request,
    crops: list[UploadFile] = File(..., description="Face crops from one camera frame"),
    camera: Camera = Depends(device_service.require_device),
    db: AsyncSession = Depends(get_db),
):
    """Recognise the face crops of one camera frame (FR-402–FR-405).

    The server embeds each crop, matches it only against students enrolled in the open session's
    class, and records a student as Present or Late once FACE_VOTE_THRESHOLD consecutive frames
    agree (FR-404). A repeat never creates a second record, and an existing override is kept
    (NFR-22). A face in the database that belongs to someone not enrolled in this class is
    logged, never recorded (FR-403), and neither names nor matric numbers go back to the device.
    Crops are never stored (NFR-01); unmatched crops are kept from T43.
    """
    face_app = getattr(request.app.state, "face_app", None)
    if face_app is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Face recognition model not loaded")
    if not 1 <= len(crops) <= settings.DEVICE_MAX_CROPS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Send 1 to {settings.DEVICE_MAX_CROPS} face crops")

    datas = []
    for crop in crops:
        data = await crop.read()
        if len(data) > settings.DEVICE_MAX_CROP_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail="Face crop too large")
        datas.append(data)

    session = await recognition_service.find_open_session(db, camera)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No open session for this device's room")

    results = await recognition_service.recognise_frame(db, face_app, camera, session, datas)
    return {"session_id": session.id, "results": results}
