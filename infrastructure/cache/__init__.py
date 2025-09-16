"""缓存层对外暴露的接口"""
from .redis_cache import (
    RedisCache,
    init_redis_cache,
    shutdown_redis_cache,
    get_redis_cache,
)

__all__ = [
    "RedisCache",
    "init_redis_cache",
    "shutdown_redis_cache",
    "get_redis_cache",
]
