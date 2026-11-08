"""Minimal Moodle Web Services (REST) client for the SPeCTRUM simulation."""
from dataclasses import dataclass

import httpx

from app.core.config import settings


class MoodleError(Exception):
    pass


@dataclass
class MoodleFile:
    module_id: int        # course module id (cmid) of the File resource
    module_name: str      # the resource's display name, e.g. "Week 3 - Lecture slides"
    section_name: str     # e.g. "Week 3"
    file_name: str
    file_path: str
    file_url: str
    timemodified: int
    size: int
    mimetype: str | None

    @property
    def source_key(self) -> str:
        return f"moodle:{self.module_id}:{self.file_path}{self.file_name}"


class MoodleFileStream:
    """An open Moodle file download, read in chunks so big slide decks aren't held in memory."""

    def __init__(self, resp: httpx.Response):
        self._resp = resp
        self.content_type = resp.headers.get("content-type") or None

    def aiter_bytes(self):
        return self._resp.aiter_bytes()

    async def aclose(self) -> None:
        await self._resp.aclose()


class MoodleClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 60.0):
        self.base_url = (base_url or settings.MOODLE_URL).rstrip("/")
        self.token = token or settings.MOODLE_TOKEN
        if not self.token:
            raise MoodleError("MOODLE_TOKEN is not configured")
        self._http = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self._http.aclose()

    async def call(self, function: str, **params) -> object:
        resp = await self._http.post(
            f"{self.base_url}/webservice/rest/server.php",
            data={"wstoken": self.token, "wsfunction": function, "moodlewsrestformat": "json", **params},
        )
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, dict) and "exception" in body:
            raise MoodleError(f"{function}: {body.get('errorcode')} - {body.get('message')}")
        return body

    async def get_course_id(self, shortname: str) -> int | None:
        body = await self.call("core_course_get_courses_by_field", field="shortname", value=shortname)
        courses = body.get("courses", [])
        return courses[0]["id"] if courses else None

    async def list_files(self, course_id: int) -> list[MoodleFile]:
        """Every file inside a File resource of the course, with its section name."""
        sections = await self.call("core_course_get_contents", courseid=course_id)
        files: list[MoodleFile] = []
        for section in sections:
            for module in section.get("modules", []):
                if module.get("modname") != "resource" or not module.get("visible", 1):
                    continue
                for c in module.get("contents", []) or []:
                    if c.get("type") != "file":
                        continue
                    files.append(MoodleFile(
                        module_id=module["id"],
                        module_name=module.get("name") or c["filename"],
                        section_name=section.get("name") or "",
                        file_name=c["filename"],
                        file_path=c.get("filepath") or "/",
                        file_url=c["fileurl"],
                        timemodified=int(c.get("timemodified") or 0),
                        size=int(c.get("filesize") or 0),
                        mimetype=c.get("mimetype"),
                    ))
        return files

    async def open_file(self, file_url: str) -> MoodleFileStream:
        """Start streaming a file. Errors are raised before any bytes are sent; the caller closes it."""
        req = self._http.build_request("GET", file_url, params={"token": self.token})
        try:
            resp = await self._http.send(req, stream=True)
        except httpx.HTTPError as exc:
            raise MoodleError(f"download failed: {exc.__class__.__name__}") from exc
        content_type = resp.headers.get("content-type", "")
        if resp.status_code >= 400 or content_type.startswith("application/json"):
            # Moodle reports a bad token or missing file as a small JSON body
            await resp.aread()
            await resp.aclose()
            detail = f"HTTP {resp.status_code}"
            if content_type.startswith("application/json"):
                try:
                    detail = resp.json().get("errorcode") or detail
                except ValueError:
                    pass
            raise MoodleError(f"download failed: {detail}")
        return MoodleFileStream(resp)

    async def download(self, file_url: str) -> bytes:
        resp = await self._http.get(file_url, params={"token": self.token})
        resp.raise_for_status()
        if resp.headers.get("content-type", "").startswith("application/json"):
            body = resp.json()
            if isinstance(body, dict) and body.get("error"):
                raise MoodleError(f"download failed: {body.get('errorcode')}")
        return resp.content
