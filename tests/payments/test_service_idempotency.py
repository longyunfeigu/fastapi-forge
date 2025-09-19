import pytest
from decimal import Decimal

from application.services.payment_service import PaymentService
from application.dtos.payments import CreatePayment, RefundRequest, PaymentIntent, RefundResult, QueryPayment, ClosePayment, WebhookEvent
from domain.services.payment_gateway import PaymentGateway


class StubGateway(PaymentGateway):
    provider = "stub"

    async def create_payment(self, req: CreatePayment) -> PaymentIntent:  # type: ignore[override]
        return PaymentIntent(intent_id="int_1", status="created", client_secret_or_params=None, provider=self.provider)

    async def query_payment(self, query: QueryPayment) -> PaymentIntent:  # type: ignore[override]
        return PaymentIntent(intent_id="int_1", status="succeeded", client_secret_or_params=None, provider=self.provider)

    async def refund(self, req: RefundRequest) -> RefundResult:  # type: ignore[override]
        return RefundResult(refund_id="re_1", status="refund_pending", provider=self.provider)

    async def close_payment(self, req: ClosePayment) -> None:  # type: ignore[override]
        return None

    def parse_webhook(self, headers: dict, body: bytes) -> WebhookEvent:  # type: ignore[override]
        return WebhookEvent(id="evt_1", type="stub.event", provider=self.provider, data={})


@pytest.mark.asyncio
async def test_create_payment_generates_idempotency_key(monkeypatch):
    svc = PaymentService(gateway=StubGateway())
    req = CreatePayment(order_id="o1", amount=Decimal("1.00"), currency="USD", provider="stub", scene="qr_code")
    assert req.idempotency_key is None
    await svc.create_payment(req)
    assert isinstance(req.idempotency_key, str) and len(req.idempotency_key) == 64


@pytest.mark.asyncio
async def test_refund_generates_idempotency_key(monkeypatch):
    svc = PaymentService(gateway=StubGateway())
    req = RefundRequest(order_id="o1", amount=Decimal("1.00"), currency="USD", provider="stub")
    assert req.idempotency_key is None
    await svc.refund(req)
    assert isinstance(req.idempotency_key, str) and len(req.idempotency_key) == 64

