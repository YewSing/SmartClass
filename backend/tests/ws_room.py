"""Helpers to test broadcasts on an interaction's websocket room.

The real endpoint blocks in its receive loop, so tests must keep it running in a
background task while they trigger the action that broadcasts.
"""

import asyncio

from fastapi import WebSocketDisconnect

from app.websocket.manager import manager
from app.websocket.router import interaction_ws


class RecordingWebSocket:
    def __init__(self) -> None:
        self.closed_code = None
        self.sent = []
        self._stop = asyncio.Event()

    async def accept(self) -> None:
        pass

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code
        self._stop.set()

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def receive_text(self) -> str:
        await self._stop.wait()
        raise WebSocketDisconnect()


class InteractionRoom:
    """Run `interaction_ws` for one authenticated client while the block runs."""

    def __init__(self, interaction_id: int, token: str) -> None:
        self.ws = RecordingWebSocket()
        self._interaction_id = interaction_id
        self._token = token
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> RecordingWebSocket:
        self._task = asyncio.create_task(
            interaction_ws(self._interaction_id, self.ws, token=self._token)
        )
        for _ in range(100):
            if self.ws in manager._connections.get(self._interaction_id, set()):
                return self.ws
            if self._task.done():
                break
            await asyncio.sleep(0.01)
        return self.ws

    async def __aexit__(self, *exc) -> None:
        self.ws._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, WebSocketDisconnect):
                self._task.cancel()
