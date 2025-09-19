import os
import pytest


stripe = pytest.importorskip("stripe")


@pytest.mark.asyncio
async def test_stripe_parse_webhook(monkeypatch):
    from infrastructure.external.payments import get_payment_gateway
    from infrastructure.external.payments.stripe_client import StripeClient

    os.environ.setdefault("STRIPE__SECRET_KEY", "sk_test_123")
    os.environ.setdefault("STRIPE__WEBHOOK_SECRET", "whsec_test")

    # Fake construct_event to bypass cryptography
    class _FakeWebhook:
        @staticmethod
        def construct_event(payload, sig_header, secret, tolerance=None):
            return {"id": "evt_1", "type": "payment_intent.succeeded", "data": {"object": {"status": "succeeded"}}}

    monkeypatch.setattr(stripe, "Webhook", _FakeWebhook)

    gw = get_payment_gateway("stripe")
    assert isinstance(gw, StripeClient)
    evt = gw.parse_webhook({"Stripe-Signature": "t=1,v1=abc"}, b"{}")
    assert evt.type == "payment_intent.succeeded"
    assert evt.provider == "stripe"

