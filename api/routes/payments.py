"""
Payments API routes.

Exposes webhook and minimal demo endpoints to initiate/query/refund/close
payments via the application service. Keep this thin: no SDK details here.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Query

from application.services.payment_service import PaymentService
from application.dtos.payments import (
    CreatePayment,
    PaymentIntent,
    RefundRequest,
    RefundResult,
    QueryPayment,
)
from core.response import success_response
from core.logging_config import get_logger
from core.settings import payment_settings
from infrastructure.external.cache import get_redis_client
import hashlib
import ipaddress


router = APIRouter(prefix="/payments", tags=["Payments"])
logger = get_logger(__name__)


@router.post("/webhooks/{provider}")
async def payments_webhook(provider: str, request: Request):
    # Content-Type checks
    ct = (request.headers.get("content-type") or "").lower()
    if provider.lower() == "alipay":
        if "application/x-www-form-urlencoded" not in ct:
            return success_response(message="Unsupported Content-Type for Alipay webhook")
    else:
        if "application/json" not in ct:
            return success_response(message="Unsupported Content-Type for JSON webhook")

    # Optional IP allowlist
    allowlist = payment_settings.webhook.ip_allowlist or []
    if allowlist and request.client and request.client.host:
        remote_ip = request.client.host
        try:
            rip = ipaddress.ip_address(remote_ip)
            permitted = False
            for entry in allowlist:
                try:
                    if "/" in entry:
                        if rip in ipaddress.ip_network(entry, strict=False):
                            permitted = True
                            break
                    else:
                        if remote_ip == entry:
                            permitted = True
                            break
                except Exception:
                    continue
            if not permitted:
                return success_response(message="IP not allowed for webhook")
        except Exception:
            return success_response(message="Invalid remote IP")

    raw_body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    service = PaymentService(provider=provider)
    event = service.handle_webhook(provider, headers, raw_body)

    # Deduplicate by event.id + body hash within tolerance
    try:
        cache = await get_redis_client()
        body_hash = hashlib.sha256(raw_body or b"{}").hexdigest()
        key = f"webhook:{provider}:{event.id}:{body_hash}"
        ttl = max(60, int(payment_settings.webhook.tolerance_seconds))
        is_new = await cache.set(key, 1, ttl=ttl, nx=True)
        if not is_new:
            logger.info("webhook_duplicate_ignored", provider=provider, event_id=event.id)
            return success_response(
                data={"id": event.id, "type": event.type, "provider": event.provider, "duplicate": True},
                message="Duplicate webhook ignored",
            )
    except Exception as exc:  # pragma: no cover
        logger.error("webhook_dedupe_failed", provider=provider, error=str(exc))

    # Return 200 to acknowledge receipt per provider conventions
    return success_response(
        data={"id": event.id, "type": event.type, "provider": event.provider},
        message="Webhook received",
    )


@router.post("/intents", summary="Create payment", response_model=None)
async def create_payment(payload: CreatePayment):
    service = PaymentService(provider=payload.provider)
    intent = await service.create_payment(payload)
    await service.aclose()
    return success_response(data=intent.model_dump(mode="json"), message="Payment created")


@router.get("/intents/{order_id}", summary="Query payment")
async def query_payment(order_id: str, provider: str | None = Query(default=None), provider_ref: str | None = Query(default=None)):
    service = PaymentService(provider=provider)
    intent = await service.query_payment(QueryPayment(order_id=order_id, provider=provider, provider_ref=provider_ref))
    await service.aclose()
    return success_response(data=intent.model_dump(mode="json"), message="Payment status")


@router.post("/refunds", summary="Trigger refund")
async def trigger_refund(payload: RefundRequest):
    service = PaymentService(provider=payload.provider)
    result = await service.refund(payload)
    await service.aclose()
    return success_response(data=result.model_dump(mode="json"), message="Refund triggered")


@router.post("/intents/{order_id}/close", summary="Close payment")
async def close_payment(order_id: str, provider: str | None = Query(default=None)):
    service = PaymentService(provider=provider)
    from application.dtos.payments import ClosePayment as _Close
    await service.close_payment(_Close(order_id=order_id, provider=provider))
    await service.aclose()
    return success_response(message="Payment closed", data={"order_id": order_id, "provider": provider})
