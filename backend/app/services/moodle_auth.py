"""Moodle (SPeCTRUM) username/password login (FR-101, FR-102).

The password is sent once to Moodle's `login/token.php` and never stored or logged (NFR-05).
Everything else is read with the user's own Moodle token, so a user only sees their own data.
"""
from dataclasses import dataclass, field

import httpx

from app.core.config import settings
from app.services.kb.moodle_client import MoodleClient, MoodleError
from app.services.moodle_sync import MoodleCourse, course_from_enrolled, profile_fields

MOODLE_SERVICE = "smartclass"

# token.php errors that mean Moodle itself is misconfigured or closed, not that the
# credentials are wrong. Everything else (invalidlogin, suspended, ...) is a failed login.
_UNAVAILABLE_ERRORS = {"servicenotavailable", "enablewsdescription", "sitemaintenance"}


class MoodleLoginRejected(Exception):
    """Moodle refused the username/password."""


class MoodleUnavailable(Exception):
    """Moodle could not be reached or answered with something unusable."""


@dataclass
class MoodleProfile:
    user_id: int
    username: str
    fullname: str
    email: str | None
    idnumber: str | None
    department: str | None
    teaches: bool
    fields: dict = field(default_factory=dict)   # moodle_sync.profile_fields() of the user record
    courses: list[MoodleCourse] = field(default_factory=list)


async def get_user_token(username: str, password: str, base_url: str | None = None) -> str:
    url = f"{(base_url or settings.MOODLE_URL).rstrip('/')}/login/token.php"
    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.post(url, data={"username": username, "password": password, "service": MOODLE_SERVICE})
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        # The message only names the error class: the request body holds the password
        raise MoodleUnavailable(f"token request failed: {exc.__class__.__name__}") from None
    if not isinstance(body, dict):
        raise MoodleUnavailable("token request failed: unexpected response")
    if body.get("token"):
        return body["token"]
    if body.get("errorcode") in _UNAVAILABLE_ERRORS:
        raise MoodleUnavailable(f"token request failed: {body.get('errorcode')}")
    raise MoodleLoginRejected(body.get("errorcode") or "login rejected")


async def read_profile(token: str, base_url: str | None = None) -> MoodleProfile:
    """The logged-in user's identity, profile fields and whether they teach any course."""
    try:
        async with MoodleClient(base_url=base_url, token=token, timeout=20.0) as moodle:
            info = await moodle.call("core_webservice_get_site_info")
            user_id = int(info["userid"])
            users = await moodle.call("core_user_get_users_by_field", field="id", **{"values[0]": user_id})
            details = users[0] if users else {}
            my_courses: list[MoodleCourse] = []
            for course in await moodle.call("core_enrol_get_users_courses", userid=user_id):
                enrolled = await moodle.call("core_enrol_get_enrolled_users", courseid=course["id"])
                # Only this user's own role counts: the login sync changes no one else (FR-104)
                me = [u for u in enrolled if u.get("id") == user_id]
                my_courses.append(course_from_enrolled(course, me))
            teaches = any(c.teachers for c in my_courses)
    except (httpx.HTTPError, MoodleError, ValueError, KeyError, TypeError) as exc:
        raise MoodleUnavailable(f"profile read failed: {exc.__class__.__name__}") from None
    return MoodleProfile(
        user_id=user_id,
        username=info.get("username") or details.get("username") or str(user_id),
        fullname=info.get("fullname") or details.get("fullname") or info.get("username") or "",
        email=details.get("email") or None,
        idnumber=(details.get("idnumber") or "").strip() or None,
        department=details.get("department") or None,
        teaches=teaches,
        fields=profile_fields(details),
        courses=my_courses,
    )


async def authenticate(username: str, password: str) -> MoodleProfile:
    token = await get_user_token(username, password)
    return await read_profile(token)
