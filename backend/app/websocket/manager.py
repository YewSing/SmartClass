from fastapi import WebSocket


class ConnectionManager:
    """
    Singleton that tracks all active WebSocket connections.

    Session channels (keyed by session_id) carry a session's live feed to the lecturer's screens
    (NFR-27); user channels (keyed by users.id) carry a student's own events (FR-406).
    """

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._user_connections: dict[int, set[WebSocket]] = {}

    async def connect(self, session_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(session_id, set()).add(ws)

    def disconnect(self, session_id: int, ws: WebSocket) -> None:
        self._connections.get(session_id, set()).discard(ws)

    async def broadcast(self, session_id: int, payload: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._connections.get(session_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[session_id].discard(ws)

    async def connect_user(self, user_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._user_connections.setdefault(user_id, set()).add(ws)

    def disconnect_user(self, user_id: int, ws: WebSocket) -> None:
        self._user_connections.get(user_id, set()).discard(ws)

    async def send_to_user(self, user_id: int, payload: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._user_connections.get(user_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._user_connections.get(user_id, set()).discard(ws)


manager = ConnectionManager()
