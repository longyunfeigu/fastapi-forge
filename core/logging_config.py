"""
Structlog 日志配置模块
"""
import logging
import json
import structlog
from structlog.processors import TimeStamper, add_log_level, JSONRenderer
from structlog.dev import ConsoleRenderer
from structlog.contextvars import merge_contextvars
from structlog.stdlib import ProcessorFormatter
from typing import Any, List

from core.config import settings


def get_renderer() -> Any:
    """根据环境选择渲染器 (Console in DEBUG, JSON otherwise).
    注意：structlog 会向 serializer 传入 default/sort_keys 等参数，需要适配。
    """
    if settings.DEBUG:
        return ConsoleRenderer(colors=True)
    # 定义 serializer，兼容 structlog 传入的关键字参数
    def _dumps(obj, default=None, **kwargs):
        return json.dumps(obj, ensure_ascii=False, default=default, **kwargs)
    return JSONRenderer(serializer=_dumps)


def configure_logging() -> None:
    """配置 structlog 并桥接标准库 logging 到同一处理链。"""
    timestamper = TimeStamper(fmt="iso")

    # 预处理链（同时用于 stdlib ProcessorFormatter 和 structlog.configure）
    shared_pre_chain: List[Any] = [
        merge_contextvars,
        add_log_level,
        timestamper,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # 配置 structlog —— 交由 ProcessorFormatter 渲染
    structlog.configure(
        processors=[
            *shared_pre_chain,
            ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 标准库 logging 使用 ProcessorFormatter，把 stdlib 日志也纳入 structlog 渲染
    renderer = get_renderer()
    formatter = ProcessorFormatter(
        foreign_pre_chain=shared_pre_chain,
        processors=[
            ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """获取 structlog logger 实例。"""
    return structlog.get_logger(name)


# 初始化配置
configure_logging()
