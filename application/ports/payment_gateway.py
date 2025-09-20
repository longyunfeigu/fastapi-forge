"""
Payment gateway port (application/ports) exposing a replaceable protocol.

Application depends on this Protocol; infrastructure implements adapters.
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

