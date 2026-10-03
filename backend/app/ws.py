"""WebSocket /ws: одно соединение на клиента, подписка определяется ролью из токена."""

import asyncio
import logging
from dataclasses import dataclass

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.errors import Unauthorized
from app.models.enums import Role
from app.security import decode_access_token
from app.services.notifications.live import LiveEvent

log = logging.getLogger(__name__)
router = APIRouter()


@dataclass(frozen=True, slots=True)
class Subscriber:
    user_id: int
    role: Role


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, Subscriber] = {}

    def add(self, websocket: WebSocket, subscriber: Subscriber) -> None:
        self._connections[websocket] = subscriber

    def remove(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)

    @property
    def count(self) -> int:
        return len(self._connections)

    async def deliver(self, event: LiveEvent) -> None:
        targets = [
            ws for ws, sub in self._connections.items() if event.is_for(sub.user_id, sub.role)
        ]
        if not targets:
            return
        message = event.wire()
        results = await asyncio.gather(
            *(ws.send_json(message) for ws in targets), return_exceptions=True
        )
        for ws, result in zip(targets, results, strict=True):
            if isinstance(result, Exception):
                self.remove(ws)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")) -> None:
    try:
        claims = decode_access_token(token)
    except Unauthorized:
        await websocket.close(code=4401, reason="unauthorized")
        return

    await websocket.accept()
    manager.add(websocket, Subscriber(user_id=claims.user_id, role=claims.role))
    await websocket.send_json({"type": "hello", "payload": {"role": claims.role.value}})
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(websocket)
