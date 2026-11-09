"""NFR-08: a failed Moodle download must never expose the Moodle token in its error text."""
import httpx
import pytest
import respx

from app.services.kb.moodle_client import MoodleClient, MoodleError

TOKEN = "secret-moodle-token"
FILE_URL = "http://moodle.test/webservice/pluginfile.php/1/mod_resource/content/1/week1.pdf"


@pytest.mark.parametrize("status", [403, 404, 500, 503])
@respx.mock
async def test_download_http_error_hides_token(status):
    respx.get(url__startswith=FILE_URL).mock(return_value=httpx.Response(status))
    async with MoodleClient(base_url="http://moodle.test", token=TOKEN) as client:
        with pytest.raises(MoodleError) as err:
            await client.download(FILE_URL)
    assert TOKEN not in str(err.value)
    assert f"HTTP {status}" in str(err.value)


@respx.mock
async def test_download_connection_error_hides_token():
    respx.get(url__startswith=FILE_URL).mock(side_effect=httpx.ConnectError(f"cannot reach {FILE_URL}?token={TOKEN}"))
    async with MoodleClient(base_url="http://moodle.test", token=TOKEN) as client:
        with pytest.raises(MoodleError) as err:
            await client.download(FILE_URL)
    assert TOKEN not in str(err.value)
    assert err.value.__cause__ is None and err.value.__suppress_context__


@respx.mock
async def test_download_still_returns_the_file():
    route = respx.get(url__startswith=FILE_URL).mock(return_value=httpx.Response(
        200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"}))
    async with MoodleClient(base_url="http://moodle.test", token=TOKEN) as client:
        assert await client.download(FILE_URL) == b"%PDF-1.4"
    assert route.calls.last.request.url.params["token"] == TOKEN
