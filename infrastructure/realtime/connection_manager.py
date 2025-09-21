"""In-process WebSocket connection manager.

Keeps track of user connections and room memberships, and provides
broadcast helpers for this process. Cross-process broadcast is handled
by a RealtimeBrokerPort implementation.
"""
from __future__ import annotations

import asyncio
from typing import Dict, Set, Tuple

from fastapi import WebSocket

from application.ports.realtime import Envelope
from core.logging_config import get_logger
from core.config import settings


logger = get_logger(__name__)


class ConnectionManager:
    """Manage per-process WebSocket connections and room memberships."""

    def __init__(self) -> None:
        # user_id -> set[WebSocket]
        self._by_user: Dict[int, Set[WebSocket]] = {}
        # room -> set[(user_id, WebSocket)]
        self._by_room: Dict[str, Set[Tuple[int, WebSocket]]] = {}
        self._lock = asyncio.Lock()
        # per-connection send queues and sender tasks
        self._send_queues: Dict[WebSocket, asyncio.Queue] = {}
        self._sender_tasks: Dict[WebSocket, asyncio.Task] = {}

    async def add(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._by_user.setdefault(user_id, set()).add(ws)
            # prepare send queue and sender task if not exists
            if ws not in self._send_queues:
                q: asyncio.Queue = asyncio.Queue(maxsize=max(1, int(settings.REALTIME_WS_SEND_QUEUE_MAX)))
                self._send_queues[ws] = q
                self._sender_tasks[ws] = asyncio.create_task(self._sender_loop(ws, q))
        logger.info("ws_connected", user_id=user_id)

    async def remove(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._by_user.get(user_id, set()).discard(ws)
            # remove from any rooms
            for members in self._by_room.values():
                members.discard((user_id, ws))
            # stop sender
            task = self._sender_tasks.pop(ws, None)
            if task is not None:
                task.cancel()
            self._send_queues.pop(ws, None)
        logger.info("ws_disconnected", user_id=user_id)

    async def join(self, room: str, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._by_room.setdefault(room, set()).add((user_id, ws))
        logger.info("ws_join_room", room=room, user_id=user_id)

    async def leave(self, room: str, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._by_room.setdefault(room, set()).discard((user_id, ws))
        logger.info("ws_leave_room", room=room, user_id=user_id)

    async def broadcast_room(self, room: str, envelope: Envelope) -> None:
        async with self._lock:
            targets = list(self._by_room.get(room, set()))
        if not targets:
            return
        payload = envelope.model_dump(mode="json")
        for _uid, ws in targets:
            await self._enqueue(ws, payload, context={"room": room})

    async def broadcast_user(self, user_id: int, envelope: Envelope) -> None:
        async with self._lock:
            conns = list(self._by_user.get(user_id, set()))
        if not conns:
            return
        payload = envelope.model_dump(mode="json")
        for ws in conns:
            await self._enqueue(ws, payload, context={"user_id": user_id})

    async def _enqueue(self, ws: WebSocket, payload: dict, context: dict) -> None:
        q = self._send_queues.get(ws)
        if q is None:
            return
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            policy = (settings.REALTIME_WS_SEND_OVERFLOW_POLICY or "drop_oldest").lower()
            if policy not in {"drop_oldest", "drop_new", "disconnect"}:
                logger.warning("ws_send_queue_policy_invalid", policy=policy, fallback="drop_oldest")
                policy = "drop_oldest"
            if policy == "drop_new":
                logger.warning("ws_send_queue_drop_new", **context)
                return
            if policy == "disconnect":
                logger.warning("ws_send_queue_disconnect", **context)
                try:
                    await ws.close(code=1013)
                except Exception:
                    pass
                return
            # default: drop_oldest
            try:
                _ = q.get_nowait()
            except Exception:
                pass
            try:
                q.put_nowait(payload)
            except Exception:
                logger.warning("ws_send_queue_drop_after_trim", **context)

    async def _sender_loop(self, ws: WebSocket, q: asyncio.Queue) -> None:
        try:
            while True:
                payload = await q.get()
                try:
                    await ws.send_json(payload)
                except Exception as exc:  # pragma: no cover
                    logger.warning("ws_send_failed", error=str(exc))
        except asyncio.CancelledError:  # graceful exit
            return
