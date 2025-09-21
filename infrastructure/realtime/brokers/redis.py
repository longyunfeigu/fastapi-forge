"""Redis Pub/Sub based RealtimeBrokerPort implementation.

Uses `redis.asyncio` PubSub under the hood to broadcast envelopes across
processes. Channels: rt:room:{room}
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from redis import asyncio as aioredis

from application.ports.realtime import Envelope, RealtimeBrokerPort, Handler
from core.config import settings
from core.logging_config import get_logger


logger = get_logger(__name__)


class RedisRealtimeBroker(RealtimeBrokerPort):
    def __init__(self, url: Optional[str] = None) -> None:
        self._url = url or settings.redis.url or "redis://localhost:6379/0"
        self._redis: Optional[aioredis.Redis] = None
        self._task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()
        self._handler: Optional[Handler] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None  # type: ignore[attr-defined]

    @staticmethod
    def _room_channel(room: str) -> str:
        return f"rt:room:{room}"

    async def _ensure_client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self._url, decode_responses=False)
        return self._redis

    async def publish(self, room: str, envelope: Envelope) -> None:  # type: ignore[override]
        r = await self._ensure_client()
        channel = self._room_channel(room)
        payload = json.dumps(envelope.model_dump(mode="json")).encode("utf-8")
        try:
            await r.publish(channel, payload)
        except Exception as exc:  # pragma: no cover
            logger.error("redis_publish_failed", channel=channel, error=str(exc))

    async def _listen(self) -> None:
        assert self._redis is not None and self._handler is not None
        pubsub = self._redis.pubsub()
        self._pubsub = pubsub
        try:
            await pubsub.psubscribe("rt:room:*")
            logger.info("redis_pubsub_subscribed", pattern="rt:room:*")
            async for message in pubsub.listen():
                if self._stopping.is_set():
                    break
                # message types: pmessage, message
                try:
                    if not isinstance(message, dict):
                        continue
                    data = message.get("data")
                    if not isinstance(data, (bytes, bytearray)):
                        continue
                    env = Envelope.model_validate_json(data)
                    await self._handler(env)
                except Exception as exc:  # pragma: no cover
                    logger.warning("redis_pubsub_parse_failed", error=str(exc))
        except Exception as exc:  # pragma: no cover
            logger.error("redis_pubsub_listen_failed", error=str(exc))
        finally:
            try:
                # Attempt graceful close regardless of sync/async implementation
                close = getattr(pubsub, "close", None)
                if callable(close):
                    res = close()
                    if asyncio.iscoroutine(res):
                        await res
            except Exception:  # pragma: no cover
                pass

    async def subscribe(self, handler: Handler) -> None:  # type: ignore[override]
        self._handler = handler
        await self._ensure_client()
        self._task = asyncio.create_task(self._listen(), name="redis-realtime-listener")

    async def aclose(self) -> None:  # type: ignore[override]
        self._stopping.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:  # pragma: no cover
                pass
        # Close pubsub explicitly if present
        if self._pubsub is not None:
            try:
                res = self._pubsub.close()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:  # pragma: no cover
                pass
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # pragma: no cover
                pass
        self._task = None
        self._redis = None
        self._pubsub = None
