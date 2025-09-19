"""
Stripe PaymentIntents adapter using the official stripe-python SDK.

Notes on SDK usage (as of 2025-09):
- Use the client/service pattern via `stripe.StripeClient` or the module-level
  helpers. Idempotency keys are supplied via request options or the
  `idempotency_key` kwarg. Webhook verification uses
  `stripe.Webhook.construct_event` with the `Stripe-Signature` header.
"""
from __future__ import annotations

from typing import Any, Optional
from decimal import Decimal

from application.dtos.payments import (
    CreatePayment,
    PaymentIntent,
    RefundRequest,
    RefundResult,
    QueryPayment,
    ClosePayment,
    WebhookEvent,
)
from infrastructure.external.payments.base import BasePaymentClient
from infrastructure.external.payments.exceptions import (
    PaymentProviderError,
    PaymentRecoverableError,
    PaymentSignatureError,
)
from core.settings import payment_settings
from core.logging_config import get_logger


logger = get_logger(__name__)

try:  # optional import to keep repo install-light
    import stripe  # type: ignore
except Exception:  # pragma: no cover - graceful degradation
    stripe = None  # type: ignore


class StripeClient(BasePaymentClient):
    provider = "stripe"

    def __init__(self):
        super().__init__(
            timeouts=payment_settings.timeouts.model_dump(),
            retry={"max": payment_settings.retry.max, "base": payment_settings.retry.base_backoff},
        )
        if not stripe:
            raise RuntimeError("stripe SDK not installed. Add 'stripe' to requirements and install.")
        if not payment_settings.stripe.secret_key:
            raise RuntimeError("STRIPE__SECRET_KEY not configured")
        # Configure module-level key for compatibility across SDK variants
        stripe.api_key = payment_settings.stripe.secret_key

    @staticmethod
    def _to_minor(amount: Decimal, currency: str) -> int:
        # Stripe expects amounts in the smallest currency unit
        # Default exponent 2 (fiat), special cases like JPY(0) can be handled elsewhere if needed.
        exponent = 0 if currency.upper() in {"JPY", "KRW"} else 2
        return int((amount * (Decimal(10) ** exponent)).to_integral_value())

    async def create_payment(self, req: CreatePayment) -> PaymentIntent:  # type: ignore[override]
        metadata = req.metadata or {}
        metadata.setdefault("order_id", req.order_id)
        amount_minor = self._to_minor(req.amount, req.currency)

        try:
            # Module-level create (accepts idempotency_key kwarg)
            pi = stripe.PaymentIntent.create(
                amount=amount_minor,
                currency=req.currency.lower(),
                metadata=metadata,
                automatic_payment_methods={"enabled": True},
                idempotency_key=req.idempotency_key,
            )
            status = self._map_status(pi["status"])  # type: ignore[index]
            return PaymentIntent(
                intent_id=str(pi["id"]),  # type: ignore[index]
                status=status,
                client_secret_or_params={"client_secret": pi.get("client_secret")},  # type: ignore[union-attr]
                provider=self.provider,
                provider_ref=str(pi.get("latest_charge") or ""),
                order_id=req.order_id,
            )
        except Exception as exc:  # pragma: no cover
            msg = str(exc)
            if "rate_limit" in msg or "timeout" in msg:
                raise PaymentRecoverableError(msg, provider=self.provider) from exc
            raise PaymentProviderError(msg, provider=self.provider) from exc

    async def query_payment(self, query: QueryPayment) -> PaymentIntent:  # type: ignore[override]
        try:
            if query.provider_ref:
                pi = stripe.PaymentIntent.retrieve(query.provider_ref)
            else:
                pi = stripe.PaymentIntent.search(query=f"metadata['order_id']:'{query.order_id}'")
            if isinstance(pi, dict) and pi.get("object") == "search_result":
                data = pi.get("data") or []
                if not data:
                    raise PaymentProviderError("Payment not found", provider=self.provider)
                pi = data[0]
            status = self._map_status(pi["status"])  # type: ignore[index]
            return PaymentIntent(
                intent_id=str(pi["id"]),  # type: ignore[index]
                status=status,
                client_secret_or_params=None,
                provider=self.provider,
                provider_ref=str(pi.get("latest_charge") or ""),
                order_id=query.order_id,
            )
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    async def refund(self, req: RefundRequest) -> RefundResult:  # type: ignore[override]
        try:
            # Find latest charge by order_id, or require provider_ref in metadata
            if req.provider_ref:
                charge_id = req.provider_ref
            else:
                search = stripe.Charge.search(query=f"metadata['order_id']:'{req.order_id}'")
                data = search.get("data") if isinstance(search, dict) else None
                if not data:
                    raise PaymentProviderError("Charge not found for refund", provider=self.provider)
                charge_id = data[0]["id"]
            refund = stripe.Refund.create(
                charge=charge_id,
                amount=self._to_minor(req.amount, req.currency),
                metadata={"order_id": req.order_id, "reason": req.reason or ""},
                idempotency_key=req.idempotency_key,
            )
            return RefundResult(
                refund_id=str(refund["id"]),  # type: ignore[index]
                status=self._map_status(str(refund.get("status", ""))),
                provider=self.provider,
                provider_ref=str(refund.get("charge") or ""),
            )
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    async def close_payment(self, req: ClosePayment) -> None:  # type: ignore[override]
        try:
            # Cancel open PaymentIntent by order_id
            search = stripe.PaymentIntent.search(query=f"metadata['order_id']:'{req.order_id}'")
            data = search.get("data") if isinstance(search, dict) else None
            if not data:
                return
            for pi in data:
                if pi.get("status") in {"requires_payment_method", "requires_confirmation", "requires_action", "processing"}:
                    stripe.PaymentIntent.cancel(pi["id"])  # type: ignore[index]
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    def parse_webhook(self, headers: dict[str, Any], body: bytes) -> WebhookEvent:  # type: ignore[override]
        if not stripe:
            raise RuntimeError("stripe SDK not installed")
        secret = payment_settings.stripe.webhook_secret
        if not secret:
            raise PaymentSignatureError("Missing STRIPE__WEBHOOK_SECRET", provider=self.provider)
        sig = headers.get("Stripe-Signature")
        if not sig:
            raise PaymentSignatureError("Missing Stripe-Signature header", provider=self.provider)
        try:
            event = stripe.Webhook.construct_event(
                payload=body,
                sig_header=sig,
                secret=secret,
                tolerance=payment_settings.webhook.tolerance_seconds,
            )
            return WebhookEvent(
                id=str(event.get("id")),
                type=str(event.get("type")),
                provider=self.provider,
                data=event.get("data", {}) or {},
                raw_headers=headers,
                raw_body=body,
            )
        except Exception as exc:  # pragma: no cover
            raise PaymentSignatureError(str(exc), provider=self.provider) from exc
