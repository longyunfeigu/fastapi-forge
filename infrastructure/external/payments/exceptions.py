"""
Exceptions for payment providers mapped to unified BusinessException variants.
"""
from __future__ import annotations

from typing import Optional
from domain.common.exceptions import BusinessException
from shared.codes.payment_codes import PaymentCode


class PaymentProviderError(BusinessException):
    def __init__(self, message: str, *, provider: str, provider_code: str | None = None, details: Optional[dict] = None):
        full_details = {"provider": provider, "provider_code": provider_code}
        if details:
            full_details.update(details)
        super().__init__(
            code=PaymentCode.PROVIDER_ERROR,
            message=message,
            error_type="PaymentProviderError",
            details=full_details,
        )


class PaymentRecoverableError(BusinessException):
    def __init__(self, message: str, *, provider: str, provider_code: str | None = None, details: Optional[dict] = None):
        full_details = {"provider": provider, "provider_code": provider_code}
        if details:
            full_details.update(details)
        super().__init__(
            code=PaymentCode.PROVIDER_RECOVERABLE,
            message=message,
            error_type="PaymentRecoverableError",
            details=full_details,
        )


class PaymentSignatureError(BusinessException):
    def __init__(self, message: str, *, provider: str, details: Optional[dict] = None):
        full_details = {"provider": provider}
        if details:
            full_details.update(details)
        super().__init__(
            code=PaymentCode.SIGNATURE_ERROR,
            message=message,
            error_type="PaymentSignatureError",
            details=full_details,
        )

