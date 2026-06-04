from fastapi import WebSocket


class ConnectionManager:
    """
    Singleton that tracks all active WebSocket connections keyed by session_id.
    Used for real-time attendance broadcasts (NFR-27).
    """

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}

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


manager = ConnectionManager()
