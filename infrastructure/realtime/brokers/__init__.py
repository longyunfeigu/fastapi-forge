"""Realtime brokers (in-memory, Redis, Kafka, RocketMQ)."""

# Re-export convenience types for app assembly
from .inmemory import InMemoryRealtimeBroker
from .redis import RedisRealtimeBroker
try:  # optional deps
    from .kafka import KafkaRealtimeBroker  # type: ignore
except Exception:  # pragma: no cover
    KafkaRealtimeBroker = None  # type: ignore
try:  # optional deps
    from .rocketmq import RocketMQRealtimeBroker  # type: ignore
except Exception:  # pragma: no cover
    RocketMQRealtimeBroker = None  # type: ignore

__all__ = [
    "InMemoryRealtimeBroker",
    "RedisRealtimeBroker",
    "KafkaRealtimeBroker",
    "RocketMQRealtimeBroker",
]
