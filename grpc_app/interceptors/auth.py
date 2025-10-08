from __future__ import annotations

from typing import Callable, Awaitable
import contextvars

import grpc

from core.logging_config import get_logger
from application.services.token_service import TokenService
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork


logger = get_logger(__name__)


_current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("grpc_current_user_id", default=None)


def get_current_user_id() -> int | None:
    return _current_user_id.get()


class AuthInterceptor(grpc.aio.ServerInterceptor):
    """Simple Bearer token authentication.

    - Expects metadata `authorization: Bearer <token>` or `access_token: <token>`
    - Anonymous methods can be whitelisted by full method name
    """

    def __init__(self) -> None:
        # Full method names: "/forge.v1.UserService/Register"
        self._anonymous_methods = {
            "/forge.v1.UserService/Register",
            "/forge.v1.UserService/Login",
            "/forge.v1.UserService/Refresh",
            "/grpc.health.v1.Health/Check",
            "/grpc.health.v1.Health/Watch",
        }
        self._token_service = TokenService(uow_factory=SQLAlchemyUnitOfWork)

    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        # 获取下游原始处理器
        handler = await continuation(handler_call_details)
        if handler is None:
            return handler

        method = handler_call_details.method
        md = dict(handler_call_details.invocation_metadata or [])

        if method in self._anonymous_methods:
            return handler

        async def _unary_unary(request, context: grpc.aio.ServicerContext):
            token = None
            auth = md.get("authorization") or md.get("Authorization")
            if auth and auth.lower().startswith("bearer "):
                token = auth[7:].strip()
            if not token:
                token = md.get("access_token")

            if not token:
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, "未提供认证凭据")
                return None

            # Validate token and set current user id into contextvar
            user_id: int | None = None
            try:
                user_id = await self._token_service.verify_access_token(token)
            except Exception:
                # TokenExpiredException and others are handled by ExceptionMappingInterceptor
                raise
            if not user_id:
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, "无效的认证凭据")
                return None

            token_ctx = _current_user_id.set(user_id)
            try:
                return await handler.unary_unary(request, context)
            finally:
                _current_user_id.reset(token_ctx)
        """
        unary-unary 指“单请求 → 单响应”的调用类型（一次只发送一个请求消息，收到一个响应消息）。对应 4 种基本形态中的第一种：
        unary-unary: 单请求 → 单响应
        unary-stream: 单请求 → 流式响应（服务端流）
        stream-unary: 流式请求 → 单响应（客户端流）
        stream-stream: 流式请求 → 流式响应（双向流）
        """
        if handler.unary_unary:
            return grpc.unary_unary_rpc_method_handler(
                _unary_unary,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        return handler
