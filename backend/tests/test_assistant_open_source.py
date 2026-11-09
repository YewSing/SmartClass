"""T84: open a cited source (FR-809).

The file endpoint is tested with a fake MoodleClient; MoodleClient.open_file itself is tested
against a mocked HTTP transport (respx), so nothing here calls a real Moodle.
"""
import httpx
import pytest
import respx

from app.models.knowledge import KbMaterial
from app.services.kb.moodle_client import MoodleClient, MoodleError
from tests.test_char_assistant import (  # noqa: F401  (fixtures used by name)
    _add_material, _fake_embeddings, _new_chat, _other_course_id, fake_llm, kb,
)

PDF = b"%PDF-1.4 fake slide deck " + b"x" * 200_000   # bigger than one chunk


class FakeStream:
    content_type = "application/pdf"

    def __init__(self, data: bytes):
        self.data, self.closed = data, False

    async def aiter_bytes(self):
        for i in range(0, len(self.data), 65536):
            yield self.data[i:i + 65536]

    async def aclose(self):
        self.closed = True


class FakeMoodle:
    data: dict[str, bytes] = {}
    error: Exception | None = None
    opened: list[str] = []
    streams: list[FakeStream] = []
    exited = 0

    def __init__(self):
        pass

    async def open_file(self, file_url):
        FakeMoodle.opened.append(file_url)
        if FakeMoodle.error:
            raise FakeMoodle.error
        stream = FakeStream(FakeMoodle.data[file_url])
        FakeMoodle.streams.append(stream)
        return stream

    async def __aexit__(self, *exc):
        FakeMoodle.exited += 1


@pytest.fixture
def fake_moodle(monkeypatch):
    FakeMoodle.data, FakeMoodle.error, FakeMoodle.opened, FakeMoodle.streams, FakeMoodle.exited = {}, None, [], [], 0
    monkeypatch.setattr("app.routers.assistant.MoodleClient", FakeMoodle)
    return FakeMoodle


async def _moodle_material(db, course_id, file_name="Week 4 – slides.pdf", url="http://moodle/pluginfile.php/7/w4.pdf"):
    mat = KbMaterial(course_id=course_id, source_key=f"moodle:7:/{file_name}", source="moodle", moodle_module_id=7,
                     file_name=file_name, file_url=url, title="Week 4 slides", mimetype="application/pdf",
                     status="indexed")
    db.add(mat)
    await db.commit()
    return mat


def _url(material_id):
    return f"/student/assistant/materials/{material_id}/file"


# ── the file endpoint ─────────────────────────────────────────────────────────

db = pytest.mark.db


@db
async def test_enrolled_student_gets_the_file_streamed(student_client, classroom, db_session, fake_moodle):
    mat = await _moodle_material(db_session, classroom["course_id"])
    fake_moodle.data = {mat.file_url: PDF}
    resp = await student_client.get(_url(mat.id))
    assert resp.status_code == 200, resp.text
    assert resp.content == PDF
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == "inline; filename*=UTF-8''Week%204%20%E2%80%93%20slides.pdf"
    assert resp.headers["cache-control"].startswith("private")
    assert fake_moodle.opened == [mat.file_url]
    assert fake_moodle.streams[0].closed and fake_moodle.exited == 1   # Moodle connection released


@db
async def test_not_enrolled_student_is_403_and_moodle_not_called(student_client, classroom, db_session, fake_moodle):
    other = await _other_course_id(db_session, classroom)
    mat = await _moodle_material(db_session, other)
    fake_moodle.data = {mat.file_url: PDF}
    assert (await student_client.get(_url(mat.id))).status_code == 403
    assert fake_moodle.opened == []


@db
async def test_file_endpoint_is_student_only(lecturer_client, admin_client, classroom, db_session, fake_moodle):
    mat = await _moodle_material(db_session, classroom["course_id"])
    for c in (lecturer_client, admin_client):
        assert (await c.get(_url(mat.id))).status_code == 403
    assert fake_moodle.opened == []


@db
async def test_unknown_material_is_404(student_client, classroom, fake_moodle):
    assert (await student_client.get(_url(999999))).status_code == 404


@db
async def test_local_material_without_moodle_file_is_404(student_client, classroom, db_session, fake_moodle):
    mat = await _add_material(db_session, classroom["course_id"], "Local notes")
    resp = await student_client.get(_url(mat.id))
    assert resp.status_code == 404 and "no file" in resp.json()["detail"]
    assert fake_moodle.opened == []


@db
async def test_moodle_error_is_502(student_client, classroom, db_session, fake_moodle):
    mat = await _moodle_material(db_session, classroom["course_id"])
    fake_moodle.error = MoodleError("download failed: invalidtoken")
    resp = await student_client.get(_url(mat.id))
    assert resp.status_code == 502 and "invalidtoken" in resp.json()["detail"]
    assert fake_moodle.exited == 1


# ── citations carry what the app needs to open them ───────────────────────────

@db
async def test_citation_has_file_url_and_page_to_open(student_client, classroom, kb, fake_llm):  # noqa: F811
    chat = await _new_chat(student_client, classroom["course_id"])
    url = f"/student/assistant/sessions/{chat['id']}/messages"
    reply = (await student_client.post(url, json={"content": "What is BVA?"})).json()
    [cit] = reply["citations"]
    assert cit["file_url"] == _url(kb["bva_id"])
    assert (cit["location_type"], cit["open_page"]) == ("slide", 4)    # chunk covers slides 4-6
    # Also when the chat is reloaded from the stored message
    [stored] = (await student_client.get(url)).json()[-1]["citations"]
    assert stored["file_url"] == cit["file_url"] and stored["open_page"] == 4


# ── MoodleClient.open_file (no database) ──────────────────────────────────────

FILE_URL = "http://moodle.test/webservice/pluginfile.php/7/mod_resource/content/1/w4.pdf"


@respx.mock
async def test_open_file_streams_with_token():
    route = respx.get(FILE_URL).mock(return_value=httpx.Response(
        200, content=PDF, headers={"content-type": "application/pdf"}))
    async with MoodleClient(base_url="http://moodle.test", token="tok") as client:
        stream = await client.open_file(FILE_URL)
        data = b"".join([c async for c in stream.aiter_bytes()])
        await stream.aclose()
    assert data == PDF and stream.content_type == "application/pdf"
    assert route.calls.last.request.url.params["token"] == "tok"


@respx.mock
@pytest.mark.parametrize("response, expected", [
    (httpx.Response(200, json={"error": "Invalid token", "errorcode": "invalidtoken"}), "invalidtoken"),
    (httpx.Response(404, text="not found"), "HTTP 404"),
])
async def test_open_file_errors_raise_before_streaming(response, expected):
    respx.get(FILE_URL).mock(return_value=response)
    async with MoodleClient(base_url="http://moodle.test", token="tok") as client:
        with pytest.raises(MoodleError, match=expected):
            await client.open_file(FILE_URL)


@respx.mock
async def test_open_file_connection_error_is_moodle_error():
    respx.get(FILE_URL).mock(side_effect=httpx.ConnectError("refused"))
    async with MoodleClient(base_url="http://moodle.test", token="tok") as client:
        with pytest.raises(MoodleError, match="ConnectError"):
            await client.open_file(FILE_URL)
