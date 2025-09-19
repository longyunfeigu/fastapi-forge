import pytest


@pytest.mark.asyncio
async def test_wechat_parse_webhook(monkeypatch):
    from infrastructure.external.payments.wechatpay_client import WechatPayClient

    class _FakeWX:
        def callback(self, headers, body):
            return 0, {"id": "EV-1", "event_type": "TRANSACTION.SUCCESS", "resource_type": "encrypt-resource"}

    def _init(self, *args, **kwargs):
        self.provider = "wechat"
        self._wx = _FakeWX()

    monkeypatch.setattr(WechatPayClient, "__init__", _init)
    gw = WechatPayClient()
    evt = gw.parse_webhook({}, b"{}")
    assert evt.type == "TRANSACTION.SUCCESS"
    assert evt.provider == "wechat"

