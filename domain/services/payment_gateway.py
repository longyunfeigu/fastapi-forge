"""
Payment gateway abstraction (domain/service) with protocol and events.

This layer must not import infrastructure. It defines the replaceable
contract that application code depends upon.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from application.dtos.payments import (
    CreatePayment,
    PaymentIntent,
    RefundRequest,
    RefundResult,
    QueryPayment,
    ClosePayment,
    WebhookEvent,
)


@runtime_checkable
class PaymentGateway(Protocol):
    """Gateway protocol for third-party payment providers.

    Implementations should be async and side-effect free beyond IO.
    """

    provider: str

    async def create_payment(self, req: CreatePayment) -> PaymentIntent: ...

    async def query_payment(self, query: QueryPayment) -> PaymentIntent: ...

    async def refund(self, req: RefundRequest) -> RefundResult: ...

    async def close_payment(self, req: ClosePayment) -> None: ...

    def parse_webhook(self, headers: dict[str, Any], body: bytes) -> WebhookEvent: ...


# Domain events (raised by application when interpreting WebhookEvent)
class PaymentEvent:
    def __init__(self, *, order_id: str, provider: str, provider_ref: str | None = None) -> None:
        self.order_id = order_id
        self.provider = provider
        self.provider_ref = provider_ref


class PaymentSucceeded(PaymentEvent):
    pass


class PaymentFailed(PaymentEvent):
    def __init__(self, *, order_id: str, provider: str, reason: str | None = None, provider_ref: str | None = None):
        super().__init__(order_id=order_id, provider=provider, provider_ref=provider_ref)
        self.reason = reason


class PaymentRefunded(PaymentEvent):
    def __init__(self, *, order_id: str, provider: str, refund_id: str, amount: str, provider_ref: str | None = None):
        super().__init__(order_id=order_id, provider=provider, provider_ref=provider_ref)
        self.refund_id = refund_id
        self.amount = amount


class PaymentCanceled(PaymentEvent):
    pass

