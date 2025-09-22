from __future__ import annotations

from typing import Callable, Awaitable

import grpc

from core.logging_config import get_logger
from domain.common.exceptions import BusinessException
from core.exceptions import UnauthorizedException, TokenExpiredException
from shared.codes import BusinessCode


logger = get_logger(__name__)


def _business_code_to_grpc_status(code: int) -> grpc.StatusCode:
    try:
        bc = BusinessCode(code)
    except Exception:
        return grpc.StatusCode.FAILED_PRECONDITION

    mapping = {
        BusinessCode.PARAM_VALIDATION_ERROR: grpc.StatusCode.INVALID_ARGUMENT,
        BusinessCode.PARAM_ERROR: grpc.StatusCode.INVALID_ARGUMENT,
        BusinessCode.PARAM_MISSING: grpc.StatusCode.INVALID_ARGUMENT,
        BusinessCode.PARAM_TYPE_ERROR: grpc.StatusCode.INVALID_ARGUMENT,

        BusinessCode.USER_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        BusinessCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        BusinessCode.USER_ALREADY_EXISTS: grpc.StatusCode.ALREADY_EXISTS,
        BusinessCode.PASSWORD_ERROR: grpc.StatusCode.UNAUTHENTICATED,
        BusinessCode.TOKEN_INVALID: grpc.StatusCode.UNAUTHENTICATED,
        BusinessCode.TOKEN_EXPIRED: grpc.StatusCode.UNAUTHENTICATED,

        BusinessCode.UNAUTHORIZED: grpc.StatusCode.UNAUTHENTICATED,
        BusinessCode.FORBIDDEN: grpc.StatusCode.PERMISSION_DENIED,
        BusinessCode.PERMISSION_ERROR: grpc.StatusCode.PERMISSION_DENIED,

        BusinessCode.TOO_MANY_REQUESTS: grpc.StatusCode.RESOURCE_EXHAUSTED,
        BusinessCode.RATE_LIMIT_ERROR: grpc.StatusCode.RESOURCE_EXHAUSTED,

        BusinessCode.SERVICE_UNAVAILABLE: grpc.StatusCode.UNAVAILABLE,
        BusinessCode.SYSTEM_ERROR: grpc.StatusCode.INTERNAL,
        BusinessCode.DATABASE_ERROR: grpc.StatusCode.INTERNAL,
        BusinessCode.NETWORK_ERROR: grpc.StatusCode.UNAVAILABLE,
    }
    return mapping.get(bc, grpc.StatusCode.FAILED_PRECONDITION)


class ExceptionMappingInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        handler = await continuation(handler_call_details)
        if handler is None:
            return handler

        async def _unary_unary(request, context: grpc.aio.ServicerContext):
            try:
                return await handler.unary_unary(request, context)
            except TokenExpiredException as exc:
                # Distinguish to allow client-specific UX
                context.set_trailing_metadata((
                    ("x-biz-code", str(BusinessCode.TOKEN_EXPIRED.value)),
                    ("x-error-type", exc.error_type),
                ))
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, exc.message)
            except UnauthorizedException as exc:
                context.set_trailing_metadata((
                    ("x-biz-code", str(BusinessCode.UNAUTHORIZED.value)),
                    ("x-error-type", exc.error_type),
                ))
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, exc.message)
            except BusinessException as exc:
                status = _business_code_to_grpc_status(exc.code)
                try:
                    context.set_trailing_metadata((
                        ("x-biz-code", str(exc.code)),
                        ("x-error-type", exc.error_type or "BusinessError"),
                    ))
                except Exception:
                    pass
                await context.abort(status, exc.message)
            except Exception as exc:
                try:
                    context.set_trailing_metadata((
                        ("x-biz-code", str(BusinessCode.SYSTEM_ERROR.value)),
                        ("x-error-type", "SystemError"),
                    ))
                except Exception:
                    pass
                await context.abort(grpc.StatusCode.INTERNAL, "系统内部错误")

        if handler.unary_unary:
            return grpc.aio.unary_unary_rpc_method_handler(
                _unary_unary,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        return handler
