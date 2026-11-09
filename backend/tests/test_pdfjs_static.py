"""FR-809: the app's PDF viewer loads pdf.js from our backend, so no third-party script sees the token."""
import httpx
import pytest

from app.main import app


@pytest.mark.parametrize("name", ["pdf.min.js", "pdf.worker.min.js"])
async def test_pdfjs_is_served_as_javascript(name):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/static/pdfjs/{name}")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]   # browsers refuse a worker served as anything else
    assert len(resp.content) > 100_000


async def test_only_the_pdfjs_folder_is_exposed():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/static/pdfjs/../../main.py")
    assert resp.status_code == 404
