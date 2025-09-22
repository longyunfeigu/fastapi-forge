from __future__ import annotations

import time
from typing import Callable, Awaitable

import grpc

from core.logging_config import get_logger
from grpc_app.interceptors.request_id import get_request_id


logger = get_logger(__name__)


class LoggingInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        handler = await continuation(handler_call_details)
        if handler is None:
            return handler

        method = handler_call_details.method

        async def _unary_unary(request, context: grpc.aio.ServicerContext):
            start = time.perf_counter()
            try:
                peer = context.peer() if hasattr(context, "peer") else None
                logger.info("grpc_request", method=method, peer=peer, request_id=get_request_id())
                resp = await handler.unary_unary(request, context)
                return resp
            except grpc.RpcError as rpce:
                # Already mapped exception; log and propagate
                logger.warning(
                    "grpc_error",
                    method=method,
                    code=str(rpce.code()),
                    details=rpce.details(),
                    request_id=get_request_id(),
                )
                raise
            except Exception as exc:
                logger.error("grpc_unhandled_error", method=method, error=str(exc), exc_info=True, request_id=get_request_id())
                raise
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info("grpc_request_done", method=method, elapsed_ms=round(elapsed_ms, 2), request_id=get_request_id())

        if handler.unary_unary:
            return grpc.aio.unary_unary_rpc_method_handler(
                _unary_unary,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        return handler
