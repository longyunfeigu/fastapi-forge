"""
Celery tasks for payment compensation workflows: query, retries, reconciliation.
"""
from __future__ import annotations

from celery import shared_task
import asyncio

from application.services.payment_service import PaymentService
from application.dtos.payments import QueryPayment, RefundRequest
from decimal import Decimal
from core.logging_config import get_logger


logger = get_logger(__name__)


@shared_task(name="payments.query_status", bind=True, max_retries=3, default_retry_delay=30)
def task_query_status(self, provider: str, order_id: str):
    try:
        async def _run():
            service = PaymentService(provider=provider)
            try:
                return await service.query_payment(QueryPayment(order_id=order_id, provider=provider))
            finally:
                await service.aclose()

        intent = asyncio.run(_run())
        logger.info("payment_status_polled", provider=provider, order_id=order_id, status=intent.status)
        return {"status": intent.status}
    except Exception as exc:  # pragma: no cover
        logger.error("payment_status_poll_failed", provider=provider, order_id=order_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task(name="payments.refund", bind=True, max_retries=3, default_retry_delay=30)
def task_refund(self, provider: str, order_id: str, amount: str, currency: str = "CNY", reason: str | None = None):
    try:
        async def _run():
            service = PaymentService(provider=provider)
            try:
                return await service.refund(RefundRequest(order_id=order_id, amount=Decimal(amount), currency=currency, reason=reason, provider=provider))
            finally:
                await service.aclose()

        result = asyncio.run(_run())
        logger.info("payment_refund_triggered", provider=provider, order_id=order_id, refund_id=result.refund_id)
        return {"refund_id": result.refund_id, "status": result.status}
    except Exception as exc:  # pragma: no cover
        logger.error("payment_refund_failed", provider=provider, order_id=order_id, error=str(exc))
        raise self.retry(exc=exc)


# Removed global event loop; use asyncio.run per-task for isolation.
