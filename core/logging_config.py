"""
Structlog 日志配置模块
"""
import sys
import structlog
from structlog.processors import TimeStamper, add_log_level, JSONRenderer
from structlog.dev import ConsoleRenderer
from structlog.contextvars import merge_contextvars
from typing import Any, Dict, List

from core.config import settings


def get_renderer() -> Any:
    """
    根据环境选择渲染器
    
    Returns:
        日志渲染器
    """
    if settings.DEBUG:
        # 开发环境：使用彩色控制台输出
        return ConsoleRenderer(colors=True)
    else:
        # 生产环境：使用JSON格式
        return JSONRenderer()


def configure_logging() -> None:
    """
    配置structlog
    """
    # 设置时间戳格式
    timestamper = TimeStamper(fmt="iso")
    
    # 配置处理器链
    processors: List[Any] = [
        # 合并contextvars中的上下文信息
        merge_contextvars,
        # 添加时间戳
        timestamper,
        # 添加日志级别
        add_log_level,
        # 开发环境下添加额外信息
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # 使用环境相关的渲染器
        get_renderer(),
    ]
    
    # 配置structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """
    获取logger实例
    
    Args:
        name: logger名称
        
    Returns:
        配置好的logger实例
    """
    return structlog.get_logger(name)


# 初始化配置
configure_logging()