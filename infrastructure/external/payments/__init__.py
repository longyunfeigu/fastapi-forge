"""
Factory for payment gateway clients.
"""
from __future__ import annotations

from typing import Optional

from core.settings import payment_settings
from application.ports.payment_gateway import PaymentGateway


def get_payment_gateway(provider: Optional[str] = None) -> PaymentGateway:
    name = (provider or payment_settings.default_provider).lower()
    if name == "stripe":
        from .stripe_client import StripeClient
        return StripeClient()
    if name in {"wechat", "wechatpay", "wx"}:
        from .wechatpay_client import WechatPayClient
        return WechatPayClient()
    if name in {"alipay", "ali"}:
        from .alipay_client import AlipayClient
        return AlipayClient()
    raise ValueError(f"Unsupported payment provider: {name}")
