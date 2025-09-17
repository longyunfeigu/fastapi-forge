"""缓存层对外暴露的接口"""
from .redis_client import (
    # 主类
    RedisClient,
    CachePatterns,
    CacheInterface,
    
    # 枚举和数据类
    CacheStatus,
    RedisDataType,
    CacheMetrics,
    
    # 初始化和管理函数
    init_redis_client,
    get_redis_client,
    shutdown_redis_client,
    create_redis_client,
)

# 兼容旧接口（在缺失旧模块时静默跳过）
try:
    from .redis_cache import (
        RedisCache,
        init_redis_cache,
        shutdown_redis_cache,
        get_redis_cache,
    )
except Exception:  # pragma: no cover - optional compatibility
    RedisCache = None  # type: ignore
    init_redis_cache = None  # type: ignore
    shutdown_redis_cache = None  # type: ignore
    get_redis_cache = None  # type: ignore

__all__ = [
    # 新接口（推荐使用）
    "RedisClient",
    "CachePatterns",
    "CacheInterface",
    "CacheStatus",
    "RedisDataType",
    "CacheMetrics",
    "init_redis_client",
    "get_redis_client",
    "shutdown_redis_client",
    "create_redis_client",
    
    # 旧接口（保持兼容，如果存在）
    "RedisCache",
    "init_redis_cache",
    "shutdown_redis_cache",
    "get_redis_cache",
]
