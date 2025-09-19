"""
Payment-related domain entities and state machine.

Keep this layer free of infrastructure dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


class PaymentStatus(str, Enum):
    created = "created"
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"
    refund_pending = "refund_pending"
    refunded = "refunded"
    refund_failed = "refund_failed"
    partial_refunded = "partial_refunded"
    chargeback = "chargeback"
    dispute = "dispute"


@dataclass
class Money:
    amount: Decimal
    currency: str

    def to_minor(self, exponent: int = 2) -> int:
        return int((self.amount * (Decimal(10) ** exponent)).to_integral_value())


@dataclass
class Transaction:
    id: Optional[str]
    order_id: str
    provider: str
    provider_ref: Optional[str] = None
    status: PaymentStatus = PaymentStatus.created
    amount: Money = field(default_factory=lambda: Money(Decimal(0), "CNY"))
    client_secret_or_params: Optional[dict] = None


@dataclass
class Refund:
    id: Optional[str]
    order_id: str
    provider: str
    provider_ref: Optional[str] = None
    status: PaymentStatus = PaymentStatus.refund_pending
    amount: Money = field(default_factory=lambda: Money(Decimal(0), "CNY"))

