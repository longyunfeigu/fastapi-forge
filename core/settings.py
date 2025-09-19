"""
Payment-related settings using pydantic-settings v2 with nested env keys.

This module is isolated so existing core.config.Settings remains untouched.
"""
from __future__ import annotations

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field


class PaymentTimeouts(BaseModel):
    connect: float = 1.0
    read: float = 3.0
    write: float = 3.0
    total: float = 5.0


class PaymentRetry(BaseModel):
    max: int = 2
    base_backoff: float = 0.2


class WebhookSettings(BaseModel):
    tolerance_seconds: int = 300
    ip_allowlist: list[str] | None = None  # Optional IPs/CIDRs allowed to post webhooks


class AlipaySettings(BaseModel):
    app_id: Optional[str] = None
    private_key_path: Optional[str] = None
    alipay_public_key_path: Optional[str] = None
    gateway: str = "https://openapi.alipay.com/gateway.do"
    sign_type: str = "RSA2"


class WechatSettings(BaseModel):
    mch_id: Optional[str] = None
    mch_cert_serial_no: Optional[str] = None
    private_key_path: Optional[str] = None
    platform_cert_dir: Optional[str] = None
    api_v3_key: Optional[str] = None
    gateway: str = "https://api.mch.weixin.qq.com"


class StripeSettings(BaseModel):
    secret_key: Optional[str] = None
    webhook_secret: Optional[str] = None


class PaymentSettings(BaseSettings):
    default_provider: str = Field(default="stripe", validation_alias="PAYMENT__DEFAULT_PROVIDER")
    timeouts: PaymentTimeouts = Field(default_factory=PaymentTimeouts)
    retry: PaymentRetry = Field(default_factory=PaymentRetry)
    webhook: WebhookSettings = Field(default_factory=WebhookSettings)

    alipay: AlipaySettings = Field(default_factory=AlipaySettings)
    wechat: WechatSettings = Field(default_factory=WechatSettings)
    stripe: StripeSettings = Field(default_factory=StripeSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
        env_nested_delimiter="__",
    )


payment_settings = PaymentSettings()
