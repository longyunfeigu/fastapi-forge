"""
Payment specific codes and provider status mapping.
"""
from __future__ import annotations

from enum import IntEnum


class PaymentCode(IntEnum):
    # Generic success
    SUCCESS = 0

    # Provider/Network errors (6xxxx)
    PROVIDER_ERROR = 60000
    PROVIDER_RECOVERABLE = 60001
    SIGNATURE_ERROR = 60002
    TIMEOUT = 60003
    RATE_LIMITED = 60004


# Provider→internal status mapping placeholders (extend per needs)
PROVIDER_STATUS_TO_INTERNAL = {
    "stripe": {
        "requires_payment_method": "failed",
        "requires_action": "pending",
        "processing": "pending",
        "requires_capture": "pending",
        "succeeded": "succeeded",
        "canceled": "canceled",
    },
    "alipay": {
        # Per trade_status
        "WAIT_BUYER_PAY": "pending",
        "TRADE_SUCCESS": "succeeded",
        "TRADE_FINISHED": "succeeded",
        "TRADE_CLOSED": "canceled",
        "EXPIRED": "expired",
    },
    "wechat": {
        # Per trade_state
        "SUCCESS": "succeeded",
        "NOTPAY": "created",
        "USERPAYING": "pending",
        "PROCESSING": "processing",
        "EXPIRED": "expired",
        "PAYERROR": "failed",
        "CLOSED": "canceled",
        "REFUND": "refund_pending",
    },
}
