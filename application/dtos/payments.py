"""
Payment DTOs (Pydantic v2) used at application boundaries.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from pydantic.types import condecimal

# Common ISO-4217 currencies (extend as needed)
ISO_4217 = {
    "USD", "EUR", "GBP", "CNY", "JPY", "KRW", "HKD", "AUD", "CAD", "SGD",
}

# Scene allow list per provider
SCENE_BY_PROVIDER = {
    "stripe": {"card"},
    "alipay": {"qr_code", "pc_web", "wap", "app"},
    "wechat": {"qr_code", "native", "h5", "jsapi"},
}


class CreatePayment(BaseModel):
    order_id: str
    amount: condecimal(gt=0)  # type: ignore[valid-type]
    currency: str = Field(default="CNY")
    provider: Optional[str] = None
    scene: Literal["qr_code", "wap", "pc_web", "app", "jsapi", "h5", "card"] = "qr_code"
    notify_url: Optional[str] = None
    return_url: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    @field_validator("currency")
    @classmethod
    def _upper_and_validate_currency(cls, v: str) -> str:
        u = (v or "").upper()
        if len(u) != 3 or not u.isalpha():
            raise ValueError("currency must be ISO-4217 alpha-3")
        if u not in ISO_4217:
            raise ValueError("unsupported currency")
        return u

    @field_validator("scene")
    @classmethod
    def _validate_scene_by_provider(cls, v: str, info):
        provider = (info.data.get("provider") or "").lower()
        if provider and provider in SCENE_BY_PROVIDER:
            if v not in SCENE_BY_PROVIDER[provider]:
                raise ValueError(f"scene '{v}' not supported by provider '{provider}'")
        return v


class QueryPayment(BaseModel):
    order_id: str
    provider: Optional[str] = None
    provider_ref: Optional[str] = None


class ClosePayment(BaseModel):
    order_id: str
    provider: Optional[str] = None


class PaymentIntent(BaseModel):
    intent_id: str
    status: str
    client_secret_or_params: Optional[dict[str, Any]] = None
    provider: str
    provider_ref: Optional[str] = None
    order_id: Optional[str] = None


class RefundRequest(BaseModel):
    order_id: str
    amount: condecimal(gt=0)  # type: ignore[valid-type]
    currency: str = Field(default="CNY")
    reason: Optional[str] = None
    provider: Optional[str] = None
    idempotency_key: Optional[str] = None
    provider_ref: Optional[str] = None  # e.g., Stripe charge/payment_intent id or channel transaction id

    @field_validator("currency")
    @classmethod
    def _upper_and_validate_currency_refund(cls, v: str) -> str:
        u = (v or "").upper()
        if len(u) != 3 or not u.isalpha():
            raise ValueError("currency must be ISO-4217 alpha-3")
        if u not in ISO_4217:
            raise ValueError("unsupported currency")
        return u


class RefundResult(BaseModel):
    refund_id: str
    status: str
    provider: str
    provider_ref: Optional[str] = None


class WebhookEvent(BaseModel):
    id: str
    type: str
    provider: str
    data: dict[str, Any]
    # raw fields for traceability (optional)
    raw_headers: Optional[dict[str, Any]] = None
    raw_body: Optional[bytes] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
