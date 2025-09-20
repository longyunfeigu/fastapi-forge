"""
Base payment client implementing shared concerns: http, retry, logging, mapping.

Concrete providers should subclass and implement provider-specific logic.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional
from contextlib import asynccontextmanager

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.logging_config import get_logger
from application.dtos.payments import (
    CreatePayment,
    PaymentIntent,
    RefundRequest,
    RefundResult,
    QueryPayment,
    ClosePayment,
    WebhookEvent,
)
from application.ports.payment_gateway import PaymentGateway
from infrastructure.external.payments.exceptions import (
    PaymentProviderError,
    PaymentRecoverableError,
)
from shared.codes.payment_codes import PROVIDER_STATUS_TO_INTERNAL


logger = get_logger(__name__)


class BasePaymentClient(PaymentGateway):
    provider: str = "base"

    def __init__(
        self,
        *,
        timeouts: Optional[dict[str, float]] = None,
        retry: Optional[dict[str, Any]] = None,
    ) -> None:
        self._timeouts_cfg = timeouts or {"connect": 1.0, "read": 3.0, "write": 3.0, "total": 5.0}
        self._retry_cfg = retry or {"max": 2, "base": 0.2}
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def timeouts(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self._timeouts_cfg["connect"],
            read=self._timeouts_cfg["read"],
            write=self._timeouts_cfg["write"],
            timeout=self._timeouts_cfg["total"],
        )

    @asynccontextmanager
    async def client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeouts)
        try:
            yield self._client
        finally:
            # Keep open for reuse; explicit aclose() will close.
            ...

    async def aclose(self) -> None:
        """Close underlying HTTP client if created."""
        if self._client is not None:
            try:
                await self._client.aclose()
            finally:
                self._client = None

    async def _retry(self, fn: Callable[[], Any]):
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(int(self._retry_cfg["max"]) + 1),
            wait=wait_exponential(multiplier=self._retry_cfg["base"], min=0.1, max=2.0),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
            reraise=True,
        ):
            with attempt:
                return await fn()

    # Default implementations raise to force override where needed
    async def create_payment(self, req: CreatePayment) -> PaymentIntent:  # type: ignore[override]
        raise NotImplementedError

    async def query_payment(self, query: QueryPayment) -> PaymentIntent:  # type: ignore[override]
        raise NotImplementedError

    async def refund(self, req: RefundRequest) -> RefundResult:  # type: ignore[override]
        raise NotImplementedError

    async def close_payment(self, req: ClosePayment) -> None:  # type: ignore[override]
        raise NotImplementedError

    def parse_webhook(self, headers: dict[str, Any], body: bytes) -> WebhookEvent:  # type: ignore[override]
        raise NotImplementedError

    # Helpers
    def _map_status(self, provider_status: str) -> str:
        mapping = PROVIDER_STATUS_TO_INTERNAL.get(self.provider, {})
        return mapping.get(provider_status, provider_status)

    def _log(self, event: str, **kwargs) -> None:
        logger.info(
            event,
            provider=self.provider,
            **kwargs,
        )
