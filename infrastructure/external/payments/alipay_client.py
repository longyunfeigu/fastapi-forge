"""
Alipay adapter using the official alipay-sdk-python-all.

Implements unified methods for precreate (QR), page pay (PC), WAP, query,
refund, close, and webhook signature verification.
"""
from __future__ import annotations

from typing import Any, Optional
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qsl

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
    from alipay.aop.api.AlipayClientConfig import AlipayClientConfig  # type: ignore
    from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient  # type: ignore
    from alipay.aop.api.request.AlipayTradePrecreateRequest import AlipayTradePrecreateRequest  # type: ignore
    from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest  # type: ignore
    from alipay.aop.api.request.AlipayTradeWapPayRequest import AlipayTradeWapPayRequest  # type: ignore
    from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest  # type: ignore
    from alipay.aop.api.request.AlipayTradeRefundRequest import AlipayTradeRefundRequest  # type: ignore
    from alipay.aop.api.request.AlipayTradeCloseRequest import AlipayTradeCloseRequest  # type: ignore
    from alipay.aop.api.util.SignatureUtils import verify_with_rsa  # type: ignore
except Exception:  # pragma: no cover
    AlipayClientConfig = None  # type: ignore
    DefaultAlipayClient = None  # type: ignore
    AlipayTradePrecreateRequest = None  # type: ignore
    AlipayTradePagePayRequest = None  # type: ignore
    AlipayTradeWapPayRequest = None  # type: ignore
    AlipayTradeQueryRequest = None  # type: ignore
    AlipayTradeRefundRequest = None  # type: ignore
    AlipayTradeCloseRequest = None  # type: ignore
    verify_with_rsa = None  # type: ignore


class AlipayClient(BasePaymentClient):
    provider = "alipay"

    def __init__(self):
        super().__init__(
            timeouts=payment_settings.timeouts.model_dump(),
            retry={"max": payment_settings.retry.max, "base": payment_settings.retry.base_backoff},
        )
        if not AlipayClientConfig:
            raise RuntimeError("alipay-sdk-python-all not installed. Add it to requirements.")
        cfg = payment_settings.alipay
        if not (cfg.app_id and cfg.private_key_path and cfg.alipay_public_key_path):
            raise RuntimeError("ALIPAY configuration incomplete")

        self._client = self._build_client(
            server_url=cfg.gateway,
            app_id=cfg.app_id,
            app_private_key_path=cfg.private_key_path,
            alipay_public_key_path=cfg.alipay_public_key_path,
            sign_type=cfg.sign_type,
        )

    @staticmethod
    def _read_key(path: str) -> str:
        p = Path(path)
        return p.read_text(encoding="utf-8") if p.exists() else path

    def _build_client(self, *, server_url: str, app_id: str, app_private_key_path: str, alipay_public_key_path: str, sign_type: str):
        alipay_client_config = AlipayClientConfig()
        alipay_client_config.server_url = server_url
        alipay_client_config.app_id = app_id
        alipay_client_config.app_private_key = self._read_key(app_private_key_path)
        alipay_client_config.alipay_public_key = self._read_key(alipay_public_key_path)
        alipay_client_config.sign_type = sign_type
        return DefaultAlipayClient(alipay_client_config=alipay_client_config)

    @staticmethod
    def _to_yuan(amount: Decimal) -> str:
        # Alipay uses yuan units as string, with 2 decimals
        return f"{amount:.2f}"

    async def create_payment(self, req: CreatePayment) -> PaymentIntent:  # type: ignore[override]
        cfg = payment_settings.alipay
        scene = (req.scene or "qr_code").lower()
        try:
            if scene in {"qr_code", "native"}:
                request = AlipayTradePrecreateRequest()
                request.set_notify_url(req.notify_url)
                request.set_biz_content({
                    "out_trade_no": req.order_id,
                    "total_amount": self._to_yuan(req.amount),
                    "subject": f"order:{req.order_id}",
                })
                response = self._client.execute(request)
                if not response.is_success():  # type: ignore[attr-defined]
                    raise PaymentProviderError(response.body, provider=self.provider)  # type: ignore[attr-defined]
                qr = getattr(response, "alipay_trade_precreate_response", {})  # type: ignore[attr-defined]
                return PaymentIntent(
                    intent_id=req.order_id,
                    status=self._map_status("WAIT_BUYER_PAY"),
                    client_secret_or_params={"qr_code": qr.get("qr_code")},
                    provider=self.provider,
                    provider_ref=str(qr.get("trade_no") or ""),
                    order_id=req.order_id,
                )
            elif scene in {"pc_web", "app"}:  # page pay
                request = AlipayTradePagePayRequest() if scene == "pc_web" else AlipayTradeWapPayRequest()
                request.set_notify_url(req.notify_url)
                if req.return_url:
                    request.set_return_url(req.return_url)
                request.set_biz_content({
                    "out_trade_no": req.order_id,
                    "product_code": "FAST_INSTANT_TRADE_PAY",
                    "total_amount": self._to_yuan(req.amount),
                    "subject": f"order:{req.order_id}",
                })
                # page_execute returns a form/html/redirect url depending on SDK version
                page_content = self._client.page_execute(request, http_method="GET")
                return PaymentIntent(
                    intent_id=req.order_id,
                    status=self._map_status("WAIT_BUYER_PAY"),
                    client_secret_or_params={"page_content": page_content},
                    provider=self.provider,
                    provider_ref=None,
                    order_id=req.order_id,
                )
            else:
                raise PaymentProviderError(f"Unsupported scene: {scene}", provider=self.provider)
        except PaymentProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    async def query_payment(self, query: QueryPayment) -> PaymentIntent:  # type: ignore[override]
        try:
            request = AlipayTradeQueryRequest()
            request.set_biz_content({
                "out_trade_no": query.order_id,
            })
            resp = self._client.execute(request)
            if not resp.is_success():  # type: ignore[attr-defined]
                raise PaymentProviderError(resp.body, provider=self.provider)  # type: ignore[attr-defined]
            data = getattr(resp, "alipay_trade_query_response", {})  # type: ignore[attr-defined]
            status = self._map_status(str(data.get("trade_status", "")))
            return PaymentIntent(
                intent_id=query.order_id,
                status=status,
                client_secret_or_params=None,
                provider=self.provider,
                provider_ref=str(data.get("trade_no") or ""),
                order_id=query.order_id,
            )
        except PaymentProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    async def refund(self, req: RefundRequest) -> RefundResult:  # type: ignore[override]
        try:
            request = AlipayTradeRefundRequest()
            request.set_biz_content({
                "out_trade_no": req.order_id,
                "refund_amount": self._to_yuan(req.amount),
                "refund_reason": req.reason or "",
            })
            resp = self._client.execute(request)
            if not resp.is_success():  # type: ignore[attr-defined]
                raise PaymentProviderError(resp.body, provider=self.provider)  # type: ignore[attr-defined]
            data = getattr(resp, "alipay_trade_refund_response", {})  # type: ignore[attr-defined]
            return RefundResult(
                refund_id=str(data.get("trade_no") or req.order_id),
                status=self._map_status("REFUND"),
                provider=self.provider,
                provider_ref=str(data.get("trade_no") or ""),
            )
        except PaymentProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    async def close_payment(self, req: ClosePayment) -> None:  # type: ignore[override]
        try:
            request = AlipayTradeCloseRequest()
            request.set_biz_content({
                "out_trade_no": req.order_id,
            })
            resp = self._client.execute(request)
            if not resp.is_success():  # type: ignore[attr-defined]
                raise PaymentProviderError(resp.body, provider=self.provider)  # type: ignore[attr-defined]
        except PaymentProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderError(str(exc), provider=self.provider) from exc

    def parse_webhook(self, headers: dict[str, Any], body: bytes) -> WebhookEvent:  # type: ignore[override]
        # Alipay sends form-encoded payloads
        if not verify_with_rsa:
            raise RuntimeError("alipay-sdk not installed for signature verification")
        params = dict(parse_qsl(body.decode("utf-8")))
        sign = params.pop("sign", None)
        sign_type = params.pop("sign_type", "RSA2")
        if not sign:
            raise PaymentSignatureError("Missing sign", provider=self.provider)
        # Build unsigned content: sort by key and join as k=v with &
        unsigned_items = [f"{k}={v}" for k, v in sorted(params.items()) if v is not None and v != ""]
        unsigned_content = "&".join(unsigned_items)
        # Verify with Alipay public key
        alipay_key_path = payment_settings.alipay.alipay_public_key_path
        if not alipay_key_path:
            raise PaymentSignatureError("Missing ALIPAY__ALIPAY_PUBLIC_KEY_PATH", provider=self.provider)
        alipay_pubkey = self._read_key(alipay_key_path)
        ok = verify_with_rsa(alipay_pubkey, unsigned_content, sign, "utf-8", sign_type)
        if not ok:
            raise PaymentSignatureError("Invalid signature", provider=self.provider)
        event_type = params.get("trade_status", "trade_status.sync")
        event_id = params.get("trade_no", params.get("out_trade_no", ""))
        return WebhookEvent(
            id=str(event_id),
            type=str(event_type),
            provider=self.provider,
            data=params,
            raw_headers=headers,
            raw_body=body,
        )

