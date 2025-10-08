"""
WeChat Pay v3 adapter using the community `wechatpayv3` SDK.

Features used:
- Request signing with merchant private key (v3)
- Platform certificate verification and webhook resource decryption (AES-256-GCM)
- JSAPI/NATIVE/H5 flows
"""
from __future__ import annotations

from typing import Any, Optional
from decimal import Decimal
from pathlib import Path

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


try:  # optional import
    from wechatpayv3 import WeChatPay, WeChatPayType  # type: ignore
except Exception:  # pragma: no cover
    WeChatPay = None  # type: ignore
    WeChatPayType = None  # type: ignore


class WechatPayClient(BasePaymentClient):
    provider = "wechat"

    def __init__(self, *, appid: Optional[str] = None):
        super().__init__(
            timeouts=payment_settings.timeouts.model_dump(),
            retry={"max": payment_settings.retry.max, "base": payment_settings.retry.base_backoff},
        )
        if not WeChatPay:
            raise RuntimeError("wechatpayv3 SDK not installed. Add 'wechatpayv3' to requirements.")
        cfg = payment_settings.wechat
        if not (cfg.mch_id and cfg.mch_cert_serial_no and cfg.private_key_path and cfg.api_v3_key):
            raise RuntimeError("WECHAT configuration incomplete")
        key_path = Path(cfg.private_key_path)
        private_key = key_path.read_text(encoding="utf-8") if key_path.exists() else cfg.private_key_path
        self._wx = WeChatPay(
            mchid=cfg.mch_id,
            cert_serial_no=cfg.mch_cert_serial_no,
            private_key=private_key,
            apiv3_key=cfg.api_v3_key,
            appid=appid,
            notify_url=None,
            cert_dir=cfg.platform_cert_dir,
        )

    @staticmethod
    def _to_minor(amount: Decimal) -> int:
        return int((amount * Decimal(100)).to_integral_value())

    async def create_payment(self, req: CreatePayment) -> PaymentIntent:  # type: ignore[override]
        scene = (req.scene or "qr_code").lower()
        total = self._to_minor(req.amount)
        body = {
            "description": f"order:{req.order_id}",
            "out_trade_no": req.order_id,
            "amount": {"total": total, "currency": req.currency},
            "notify_url": req.notify_url,
            "attach": (req.metadata or {}).get("attach"),
        }
        try:
            if scene in {"qr_code", "native"}:
                code, message = self._wx.pay(description=body["description"], out_trade_no=req.order_id, amount={"total": total, "currency": req.currency}, pay_type=WeChatPayType.NATIVE)
                if code != 0:
                    raise PaymentProviderError(str(message), provider=self.provider)
                return PaymentIntent(
                    intent_id=req.order_id,
                    status=self._map_status("NOTPAY"),
                    client_secret_or_params={"code_url": message.get("code_url")},
                    provider=self.provider,
                    provider_ref=None,
                    order_id=req.order_id,
                )
            elif scene in {"h5", "wap"}:
                code, message = self._wx.pay(description=body["description"], out_trade_no=req.order_id, amount={"total": total, "currency": req.currency}, pay_type=WeChatPayType.H5)
                if code != 0:
                    raise PaymentProviderError(str(message), provider=self.provider)
                return PaymentIntent(
                    intent_id=req.order_id,
                    status=self._map_status("NOTPAY"),
                    client_secret_or_params=message,
                    provider=self.provider,
                    provider_ref=None,
                    order_id=req.order_id,
                )
            else:  # jsapi
                openid = (req.metadata or {}).get("openid")
                if not openid:
                    raise PaymentProviderError("openid required for jsapi", provider=self.provider)
                code, message = self._wx.pay(description=body["description"], out_trade_no=req.order_id, amount={"total": total, "currency": req.currency}, payer={"openid": openid}, pay_type=WeChatPayType.JSAPI)
                if code != 0:
                    raise PaymentProviderError(str(message), provider=self.provider)
                return PaymentIntent(
                    intent_id=req.order_id,
                    status=self._map_status("NOTPAY"),
                    client_secret_or_params=message,  # prepay_id and JSAPI params
                    provider=self.provider,
                    provider_ref=None,
                    order_id=req.order_id,
                )
        except PaymentProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    async def query_payment(self, query: QueryPayment) -> PaymentIntent:  # type: ignore[override]
        try:
            code, data = self._wx.transactions.query(out_trade_no=query.order_id)
            if code != 0:
                raise PaymentProviderError(str(data), provider=self.provider)
            status = self._map_status(str(data.get("trade_state", "")))
            return PaymentIntent(
                intent_id=query.order_id,
                status=status,
                client_secret_or_params=None,
                provider=self.provider,
                provider_ref=str(data.get("transaction_id") or ""),
                order_id=query.order_id,
            )
        except PaymentProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    async def refund(self, req: RefundRequest) -> RefundResult:  # type: ignore[override]
        try:
            out_refund_no = req.idempotency_key or f"refund-{req.order_id}"
            kwargs = {
                "out_refund_no": out_refund_no,
                "amount": {"refund": self._to_minor(req.amount), "currency": req.currency},
                "reason": req.reason,
            }
            if req.provider_ref:
                kwargs["transaction_id"] = req.provider_ref
            else:
                kwargs["out_trade_no"] = req.order_id
            code, data = self._wx.refunds.apply(**kwargs)
            if code != 0:
                raise PaymentProviderError(str(data), provider=self.provider)
            return RefundResult(
                refund_id=str(data.get("refund_id") or out_refund_no),
                status=self._map_status(str(data.get("status", "REFUND"))),
                provider=self.provider,
                provider_ref=str(data.get("transaction_id") or ""),
            )
        except PaymentProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    async def close_payment(self, req: ClosePayment) -> None:  # type: ignore[override]
        try:
            code, data = self._wx.transactions.close(out_trade_no=req.order_id)
            if code != 0:
                raise PaymentProviderError(str(data), provider=self.provider)
        except PaymentProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    def parse_webhook(self, headers: dict[str, Any], body: bytes) -> WebhookEvent:  # type: ignore[override]
        # Avoid relying on global SDK at parse time; rely on injected client
        if getattr(self, "_wx", None) is None:
            raise RuntimeError("WeChatPay client not configured")
        try:
            code, data = self._wx.callback(headers, body)  # type: ignore[attr-defined]
            if code != 0:
                raise PaymentSignatureError(str(data), provider=self.provider)
            event_type = str(data.get("event_type") or data.get("resource_type") or "transaction.success")
            event_id = str(data.get("id") or data.get("event_id") or "")
            return WebhookEvent(
                id=event_id,
                type=event_type,
                provider=self.provider,
                data=data,
                raw_headers=headers,
                raw_body=body,
            )
        except PaymentSignatureError:
            raise
        except Exception as exc:  # pragma: no cover
            raise PaymentSignatureError(str(exc), provider=self.provider) from exc
