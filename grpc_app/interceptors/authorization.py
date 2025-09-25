from __future__ import annotations

from typing import Callable, Awaitable

import grpc

from application.services.user_service import UserApplicationService
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from grpc_app.interceptors.auth import get_current_user_id


class AuthorizationInterceptor(grpc.aio.ServerInterceptor):
    """Enforce superuser for selected RPCs.

    Only unary-unary handlers are wrapped. Assumes AuthInterceptor runs earlier
    to populate current user context.
    """

    def __init__(self) -> None:
        self._svc = UserApplicationService(uow_factory=SQLAlchemyUnitOfWork)
        # Full method names that require superuser
        self._superuser_methods = {
            "/forge.v1.UserService/GetUser",
            "/forge.v1.UserService/ListUsers",
            "/forge.v1.UserService/UpdateUser",
            "/forge.v1.UserService/ActivateUser",
            "/forge.v1.UserService/DeactivateUser",
            "/forge.v1.UserService/DeleteUser",
        }

    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        handler = await continuation(handler_call_details)
        if handler is None:
            return handler

        method = handler_call_details.method
        if method not in self._superuser_methods:
            return handler

        async def _unary_unary(request, context: grpc.aio.ServicerContext):
            uid = get_current_user_id()
            if not uid:
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, "未提供认证凭据")
                return None
            # Fetch current user and check superuser flag
            try:
                user = await self._svc.get_user(int(uid))
            except Exception:
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, "无效的认证凭据")
                return None
            if not user.is_superuser:
                await context.abort(grpc.StatusCode.PERMISSION_DENIED, "需要超级管理员权限")
                return None
            return await handler.unary_unary(request, context)

        if handler.unary_unary:
            return grpc.unary_unary_rpc_method_handler(
                _unary_unary,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        return handler

