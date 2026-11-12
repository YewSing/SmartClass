"""
Issue a new key for a camera device and print it once (FR-408). The old key stops working.
Same as the admin "regenerate key" action, for when no admin screen is at hand (T46 adds one).

Run from backend/:  python scripts/device_key.py CAM-TEST
Then start the worker with DEVICE_KEY=<printed key>.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.camera import Camera
from app.services import device_service


async def main(device_id: str) -> int:
    async with AsyncSessionLocal() as db:
        cam = (await db.execute(select(Camera).where(Camera.device_id == device_id))).scalar_one_or_none()
        if cam is None:
            known = (await db.execute(select(Camera.device_id).order_by(Camera.device_id))).scalars().all()
            print(f"No device {device_id}. Known: {', '.join(known) or 'none (run scripts/seed.py)'}")
            return 1
        room = cam.room
        key = device_service.issue_key(cam)
        await db.commit()
    print(f"New key for {device_id} ({room}); the old one no longer works:")
    print(key)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
