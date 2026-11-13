"""Synchronous client for the device endpoints (FR-401, FR-402).

A 404 from `GET /device/session` or `POST /device/faces` is a normal "no session open" answer and
becomes None. 401/403 means the key is wrong or revoked and must stop the client.
"""
import httpx


class ApiError(Exception):
    """The server answered with an error the client does not know how to handle."""


class ApiUnreachable(ApiError):
    """The server could not be reached at all (connection error / timeout)."""


class AuthError(ApiError):
    """The server refused this device key (401/403): wrong or revoked."""


class DeviceApi:
    def __init__(self, base_url: str, key: str, client: httpx.Client | None = None, timeout: float = 5.0):
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)
        self._headers = {"X-Device-Key": key}

    def _request(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            resp = self._client.request(method, path, headers=self._headers, **kw)
        except httpx.TransportError as exc:
            raise ApiUnreachable(str(exc)) from exc
        if resp.status_code in (401, 403):
            raise AuthError(f"{resp.status_code}: {resp.text[:120]}")
        if resp.status_code != 404 and not resp.is_success:
            raise ApiError(f"{resp.status_code}: {resp.text[:120]}")
        return resp

    def heartbeat(self) -> None:
        self._request("POST", "/device/heartbeat")

    def current_session(self) -> int | None:
        resp = self._request("GET", "/device/session")
        if resp.status_code == 404:
            return None
        return resp.json()["session_id"]

    def send_faces(self, crops: list[bytes]) -> dict | None:
        resp = self._request(
            "POST", "/device/faces",
            files=[("crops", (f"face{i}.jpg", data, "image/jpeg")) for i, data in enumerate(crops)],
        )
        if resp.status_code == 404:
            return None
        return resp.json()

    def close(self) -> None:
        self._client.close()
