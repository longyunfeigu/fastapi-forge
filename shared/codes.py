"""
Shared business codes used across layers (Domain/Core/API).

This module provides a single source of truth to avoid drift between
multiple enum definitions scattered across the codebase.
"""
from enum import IntEnum


class BusinessCode(IntEnum):
    """业务状态码定义（单一来源）"""

    # 成功
    SUCCESS = 0

    # 参数错误 (1xxxx)
    PARAM_ERROR = 10000
    PARAM_MISSING = 10001
    PARAM_TYPE_ERROR = 10002
    PARAM_VALIDATION_ERROR = 10003

    # 业务错误 (2xxxx)
    BUSINESS_ERROR = 20000
    USER_NOT_FOUND = 20001
    USER_ALREADY_EXISTS = 20002
    PASSWORD_ERROR = 20003
    TOKEN_INVALID = 20004
    TOKEN_EXPIRED = 20005
    NOT_FOUND = 20006  # 资源未找到（通用）

    # 权限错误 (3xxxx)
    PERMISSION_ERROR = 30000
    UNAUTHORIZED = 30001
    FORBIDDEN = 30002

    # 系统错误 (4xxxx)
    SYSTEM_ERROR = 40000
    DATABASE_ERROR = 40001
    NETWORK_ERROR = 40002
    SERVICE_UNAVAILABLE = 40003

    # 限流错误 (5xxxx)
    RATE_LIMIT_ERROR = 50000
    TOO_MANY_REQUESTS = 50001


__all__ = ["BusinessCode"]

