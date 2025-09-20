"""
Application service orchestrating payment use-cases.

This class depends only on the application PaymentGateway port and DTOs.
Gateway implementations are provided by infrastructure and must be injected
from the composition root (API/tasks), keeping dependencies one-way.
"""
from __future__ import annotations

import hashlib

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
from core.logging_config import get_logger


logger = get_logger(__name__)


def _ensure_idempotency_key(req: CreatePayment | RefundRequest) -> None:
    if getattr(req, "idempotency_key", None):
        return
    # Stable, reproducible key derived from business identifiers (no timestamp)
    def pick_meta(meta: dict | None) -> str:
        if not meta:
            return ""
        # project-specific stable subset to avoid high cardinality
        keys = [k for k in ("idempotency_hint", "customer_id", "product_id") if k in meta]
        if not keys:
            return ""
        parts = [f"{k}={meta[k]}" for k in keys]
        return "|".join(parts)

    if isinstance(req, CreatePayment):
        op = "create"
        base = f"{op}|{req.order_id}|{req.amount}|{req.currency}|{(req.provider or '').lower()}|{req.scene}|{pick_meta(req.metadata)}"
    else:
        op = "refund"
        pref = getattr(req, "provider_ref", None) or ""
        base = f"{op}|{req.order_id}|{pref}|{req.amount}|{req.currency}|{(req.provider or '').lower()}|{pick_meta(None)}"
    setattr(req, "idempotency_key", hashlib.sha256(base.encode("utf-8")).hexdigest())


class PaymentService:
    def __init__(self, gateway: PaymentGateway) -> None:
        self.gateway = gateway

    async def create_payment(self, req: CreatePayment) -> PaymentIntent:
        _ensure_idempotency_key(req)
        logger.info(
            "payment_create_request",
            order_id=req.order_id,
            provider=req.provider or self.gateway.provider,
            idempotency_key=req.idempotency_key,
        )
        intent = await self.gateway.create_payment(req)
        logger.info(
            "payment_create_response",
            order_id=req.order_id,
            provider=intent.provider,
            status=intent.status,
        )
        return intent

    async def query_payment(self, req: QueryPayment) -> PaymentIntent:
        logger.info("payment_query_request", order_id=req.order_id, provider=req.provider or self.gateway.provider)
        return await self.gateway.query_payment(req)

    async def refund(self, req: RefundRequest) -> RefundResult:
        _ensure_idempotency_key(req)
        logger.info("payment_refund_request", order_id=req.order_id, provider=req.provider or self.gateway.provider)
        return await self.gateway.refund(req)

    async def close_payment(self, req: ClosePayment) -> None:
        logger.info("payment_close_request", order_id=req.order_id, provider=req.provider or self.gateway.provider)
        await self.gateway.close_payment(req)

    def handle_webhook(self, headers: dict, body: bytes) -> WebhookEvent:
        event = self.gateway.parse_webhook(headers, body)
        logger.info("payment_webhook_parsed", provider=self.gateway.provider, event_type=event.type, event_id=event.id)
        return event

    async def aclose(self) -> None:
        # Best-effort close underlying resources
        close = getattr(self.gateway, "aclose", None)
        if callable(close):
            await close()
