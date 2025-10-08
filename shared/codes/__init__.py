"""
Shared business codes used across layers (Domain/Core/API).

This package exposes BusinessCode at `shared.codes` and keeps
payment-specific codes under `shared.codes.payment_codes`.
"""
from enum import IntEnum


class BusinessCode(IntEnum):
    """Unified business status codes (single source of truth)."""

    # Success
    SUCCESS = 0

    # Parameter errors (1xxxx)
    PARAM_ERROR = 10000
    PARAM_MISSING = 10001
    PARAM_TYPE_ERROR = 10002
    PARAM_VALIDATION_ERROR = 10003

    # Business errors (2xxxx)
    BUSINESS_ERROR = 20000
    USER_NOT_FOUND = 20001
    USER_ALREADY_EXISTS = 20002
    PASSWORD_ERROR = 20003
    TOKEN_INVALID = 20004
    TOKEN_EXPIRED = 20005
    NOT_FOUND = 20006  # Generic resource not found

    # Authorization errors (3xxxx)
    PERMISSION_ERROR = 30000
    UNAUTHORIZED = 30001
    FORBIDDEN = 30002

    # System errors (4xxxx)
    SYSTEM_ERROR = 40000
    DATABASE_ERROR = 40001
    NETWORK_ERROR = 40002
    SERVICE_UNAVAILABLE = 40003

    # Rate limiting (5xxxx)
    RATE_LIMIT_ERROR = 50000
    TOO_MANY_REQUESTS = 50001


__all__ = ["BusinessCode"]

