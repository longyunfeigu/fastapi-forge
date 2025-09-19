import os
import pytest


@pytest.mark.asyncio
async def test_alipay_parse_webhook(monkeypatch):
    from infrastructure.external.payments.alipay_client import AlipayClient

    # Bypass SDK-heavy initialization and key reading
    def _init(self):
        self.provider = "alipay"
    monkeypatch.setattr(AlipayClient, "__init__", _init)
    monkeypatch.setattr(AlipayClient, "_read_key", lambda self, p: "PUBKEY")

    # Stub signature verifier to return True
    import infrastructure.external.payments.alipay_client as mod
    def _verify(pubkey, content, sign, encoding, sign_type):
        assert sign_type in {"RSA2", "RSA"}
        assert isinstance(content, str)
        return True
    monkeypatch.setattr(mod, "verify_with_rsa", _verify)

    gw = AlipayClient()
    form = (
        "notify_type=trade_status_sync&trade_status=TRADE_SUCCESS&out_trade_no=ORDER_1&trade_no=TN_1" \
        "&total_amount=1.00&sign_type=RSA2&sign=BASE64=="
    ).encode()
    evt = gw.parse_webhook({}, form)
    assert evt.type == "TRADE_SUCCESS"
    assert evt.provider == "alipay"

