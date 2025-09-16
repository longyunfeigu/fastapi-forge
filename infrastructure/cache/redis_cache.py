"""Redis缓存实现"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from redis import asyncio as aioredis

from core.config import settings


def _json_dumps(value: Any) -> str:
    """将任意对象序列化为JSON字符串"""
    return json.dumps(value, default=str)


def _json_loads(value: Optional[str]) -> Any:
    """将JSON字符串反序列化为对象"""
    if value is None:
        return None
    return json.loads(value)


class RedisCache:
    """基于Redis的简单缓存实现"""

    def __init__(self, client: aioredis.Redis, namespace: str = "") -> None:
        self._client = client
        self._namespace = namespace.strip(":")

    def _format_key(self, key: str) -> str:
        if not self._namespace:
            return key
        return f"{self._namespace}:{key}"

    async def get(self, key: str) -> Any:
        value = await self._client.get(self._format_key(key))
        if value is None:
            return None
        return _json_loads(value)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        payload = _json_dumps(value)
        expire = settings.CACHE_DEFAULT_TTL if ttl is None else ttl
        formatted_key = self._format_key(key)
        if expire and expire > 0:
            await self._client.set(formatted_key, payload, ex=expire)
        else:
            await self._client.set(formatted_key, payload)

    async def delete(self, key: str) -> bool:
        return bool(await self._client.delete(self._format_key(key)))

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(self._format_key(key)))

    async def incr(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        formatted_key = self._format_key(key)
        value = await self._client.incrby(formatted_key, amount)
        expire = settings.CACHE_DEFAULT_TTL if ttl is None else ttl
        if expire and expire > 0:
            await self._client.expire(formatted_key, expire)
        return value


_redis_client: Optional[aioredis.Redis] = None
_cache_instance: Optional[RedisCache] = None
_lock = asyncio.Lock()


async def init_redis_cache(namespace: Optional[str] = None) -> RedisCache:
    """初始化Redis缓存实例"""
    global _redis_client, _cache_instance

    if _cache_instance is not None:
        return _cache_instance

    async with _lock:
        if _cache_instance is not None:
            return _cache_instance

        if not settings.REDIS_URL:
            raise RuntimeError("REDIS_URL 未配置，无法初始化Redis缓存")

        client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
        )

        _redis_client = client
        _cache_instance = RedisCache(
            client=client,
            namespace=namespace or settings.CACHE_NAMESPACE,
        )
        return _cache_instance


async def get_redis_cache() -> RedisCache:
    """获取全局Redis缓存实例"""
    if _cache_instance is None:
        return await init_redis_cache()
    return _cache_instance


async def shutdown_redis_cache() -> None:
    """关闭Redis连接"""
    global _redis_client, _cache_instance

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        _cache_instance = None
