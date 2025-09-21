"""Application service for realtime WebSocket workflows.

Keeps application logic (authorization, orchestration) separate from
the concrete connection management and broadcast transport.
"""
from __future__ import annotations

from fastapi import WebSocket

from application.ports.realtime import Envelope, RealtimeBrokerPort
from infrastructure.realtime.connection_manager import ConnectionManager
from core.logging_config import get_logger


logger = get_logger(__name__)


class RealtimeService:
    def __init__(self, *, broker: RealtimeBrokerPort, connections: ConnectionManager) -> None:
        self._broker = broker
        self._conn = connections

    # Public API (use-cases)
    async def join_room(self, user_id: int, room: str, ws: WebSocket, *, is_superuser: bool = False) -> None:
        self._ensure_can_join(user_id, room, is_superuser)
        # 连接的 add 在 API 握手后已完成，这里仅处理房间维度
        await self._conn.join(room, user_id, ws)
        await self._conn.broadcast_user(user_id, Envelope(type="welcome", data={"user_id": user_id}))

    async def leave_room(self, user_id: int, room: str, ws: WebSocket) -> None:
        await self._conn.leave(room, user_id, ws)

    async def send_message(self, user_id: int, room: str, data: dict, *, is_superuser: bool = False) -> None:
        self._ensure_can_send(user_id, room, is_superuser)
        env = Envelope(type="message", room=room, data=data, sender_id=user_id)
        await self._broker.publish(room, env)

    # Broker callback (cross-process events → in-process broadcast)
    async def on_broker_event(self, envelope: Envelope) -> None:
        if envelope.room:
            await self._conn.broadcast_room(envelope.room, envelope)
        else:
            # Fallback broadcast to sender or system-level; extend as needed
            if envelope.sender_id:
                await self._conn.broadcast_user(envelope.sender_id, envelope)
        logger.info("realtime_event_dispatched", type=envelope.type, room=envelope.room)

    # Expose for API convenience
    @property
    def connections(self) -> ConnectionManager:
        return self._conn

    # -------------------- ACL helpers --------------------
    @staticmethod
    def _ensure_can_join(user_id: int, room: str, is_superuser: bool) -> None:
        # Policy examples:
        # - public:* anyone can join
        # - private:<uid> only that user or superuser can join
        if room.startswith("private:"):
            try:
                owner = int(room.split(":", 1)[1])
            except Exception:
                owner = -1
            if not (is_superuser or owner == user_id):
                raise PermissionError("forbidden: private room")

    @staticmethod
    def _ensure_can_send(user_id: int, room: str, is_superuser: bool) -> None:
        # Reuse join policy by default
        RealtimeService._ensure_can_join(user_id, room, is_superuser)
