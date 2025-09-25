"""Application service for realtime WebSocket workflows.

Keeps application logic (authorization, orchestration) separate from
the concrete connection management and broadcast transport.
"""
from __future__ import annotations

from typing import List, Set
from datetime import datetime, timezone

from fastapi import WebSocket

from application.ports.realtime import Envelope, RealtimeBrokerPort
from infrastructure.realtime.connection_manager import ConnectionManager
from core.logging_config import get_logger


logger = get_logger(__name__)


class RealtimeService:
    def __init__(self, *, broker: RealtimeBrokerPort, connections: ConnectionManager) -> None:
        self._broker = broker
        self._conn = connections
        # Track online users for business logic
        self._online_users: Set[int] = set()

    # Connection lifecycle management
    async def connect(self, user_id: int, ws: WebSocket, *, is_superuser: bool = False) -> None:
        """Handle new WebSocket connection establishment."""
        # 1. Add connection to manager
        await self._conn.add(user_id, ws)

        # 2. Update online status
        self._online_users.add(user_id)

        # 3. Send welcome message with server capabilities
        await self._conn.broadcast_user(
            user_id,
            Envelope(
                type="welcome",
                data={
                    "user_id": user_id,
                    "server_time": datetime.now(timezone.utc).isoformat(),
                    "capabilities": ["chat", "rooms", "broadcast", "presence"]
                }
            )
        )

        # 4. Optional: Broadcast user online status
        if self._should_broadcast_presence(user_id, is_superuser):
            await self._broker.publish(
                "presence",
                Envelope(
                    type="user_online",
                    data={"user_id": user_id, "timestamp": datetime.now(timezone.utc).isoformat()}
                )
            )

        logger.info("user_connected", user_id=user_id, is_superuser=is_superuser)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        """Handle WebSocket connection termination."""
        # 1. Get user's current rooms for cleanup
        rooms = await self._get_user_rooms(user_id, ws)

        # 2. Leave all rooms
        for room in rooms:
            await self.leave_room(user_id, room, ws)

        # 3. Remove connection from manager
        await self._conn.remove(user_id, ws)

        # 4. Update online status
        self._online_users.discard(user_id)

        # 5. Optional: Broadcast user offline status
        # Check if user still has other connections
        if not await self._has_other_connections(user_id):
            await self._broker.publish(
                "presence",
                Envelope(
                    type="user_offline",
                    data={"user_id": user_id, "timestamp": datetime.now(timezone.utc).isoformat()}
                )
            )

        logger.info("user_disconnected", user_id=user_id, rooms_left=len(rooms))

    # Public API (use-cases)
    async def join_room(self, user_id: int, room: str, ws: WebSocket, *, is_superuser: bool = False) -> None:
        self._ensure_can_join(user_id, room, is_superuser)
        await self._conn.join(room, user_id, ws)
        # Send room-specific welcome message
        await self._conn.broadcast_room(
            room,
            Envelope(
                type="user_joined",
                room=room,
                data={"user_id": user_id, "timestamp": datetime.now(timezone.utc).isoformat()}
            )
        )

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

    # -------------------- Helper methods --------------------
    async def _get_user_rooms(self, user_id: int, ws: WebSocket) -> List[str]:
        """Get all rooms that a user's specific connection is in."""
        rooms = []
        async with self._conn._lock:
            for room, members in self._conn._by_room.items():
                if (user_id, ws) in members:
                    rooms.append(room)
        return rooms

    async def _has_other_connections(self, user_id: int) -> bool:
        """Check if user has other active connections."""
        async with self._conn._lock:
            connections = self._conn._by_user.get(user_id, set())
            return len(connections) > 0

    def _should_broadcast_presence(self, user_id: int, is_superuser: bool) -> bool:
        """Determine whether to broadcast user presence changes."""
        # Business rule: broadcast presence for superusers or in future for VIP users
        # This can be extended based on business requirements
        return is_superuser

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
