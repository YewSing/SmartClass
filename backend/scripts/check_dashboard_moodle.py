"""Read-only demo-account diagnostic; prints no token or password."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.config import settings


async def main():
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(f"{settings.MOODLE_URL.rstrip('/')}/login/token.php",
            data={"username": "student1", "password": "Student123!", "service": "smartclass"})
        body = response.json()
        print({"http_status": response.status_code, "authenticated": bool(body.get("token")),
               "errorcode": body.get("errorcode")})


if __name__ == "__main__":
    asyncio.run(main())
