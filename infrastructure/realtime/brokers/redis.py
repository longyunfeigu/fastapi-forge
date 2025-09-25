"""Redis Pub/Sub based RealtimeBrokerPort implementation.

Refactored to reuse the shared RedisClient from infrastructure.external.cache.
Broadcast semantics unchanged: publish to per-room channels `rt:room:{room}`
and pattern-subscribe `rt:room:*` to receive all rooms.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from application.ports.realtime import Envelope, RealtimeBrokerPort, Handler
from core.config import settings
from core.logging_config import get_logger
from infrastructure.external.cache import get_redis_client, RedisClient


logger = get_logger(__name__)


class RedisRealtimeBroker(RealtimeBrokerPort):
    def __init__(self, url: Optional[str] = None) -> None:
        # URL is kept for backward compatibility; actual client managed elsewhere.
        self._task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()
        self._handler: Optional[Handler] = None
        self._client: Optional[RedisClient] = None

    @staticmethod
    def _room_channel(room: str) -> str:
        return f"rt:room:{room}"

    async def publish(self, room: str, envelope: Envelope) -> None:  # type: ignore[override]
        if self._client is None:
            self._client = await get_redis_client()
        channel = self._room_channel(room)
        try:
            # RedisClient handles JSON serialization internally
            await self._client.publish(channel, envelope.model_dump(mode="json"))
        except Exception as exc:  # pragma: no cover
            logger.error("redis_publish_failed", channel=channel, error=str(exc))

    async def _listen(self) -> None:
        assert self._client is not None and self._handler is not None
        try:
            logger.info("redis_pubsub_subscribed", pattern="rt:room:*")
            async for message in self._client.psubscribe("rt:room:*"):
                if self._stopping.is_set():
                    break
                try:
                    data = message.get("data")  # already deserialized (dict)
                    if not isinstance(data, dict):
                        continue
                    env = Envelope.model_validate(data)
                    await self._handler(env)
                except Exception as exc:  # pragma: no cover
                    logger.warning("redis_pubsub_parse_failed", error=str(exc))
        except Exception as exc:  # pragma: no cover
            logger.error("redis_pubsub_listen_failed", error=str(exc))

    async def subscribe(self, handler: Handler) -> None:  # type: ignore[override]
        self._handler = handler
        if self._client is None:
            self._client = await get_redis_client()
        self._task = asyncio.create_task(self._listen(), name="redis-realtime-listener")

    async def aclose(self) -> None:  # type: ignore[override]
        self._stopping.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:  # pragma: no cover
                pass
        self._task = None
        self._client = None
