"""CORS: the browser apps' dev origins may call the API (T05: lecturer app on Expo web)."""

import httpx
import pytest

from app.main import app


async def _preflight(origin: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        return await c.options(
            "/auth/login",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                     "Access-Control-Request-Headers": "content-type,authorization"},
        )


@pytest.mark.parametrize("origin", ["http://localhost:8081", "http://localhost:8082", "http://localhost:8092", "http://localhost:8093", "http://localhost:5173"])
async def test_preflight_allowed_for_dev_origins(origin):
    res = await _preflight(origin)
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == origin


async def test_preflight_rejected_for_unknown_origin():
    res = await _preflight("http://evil.example")
    assert "access-control-allow-origin" not in res.headers
