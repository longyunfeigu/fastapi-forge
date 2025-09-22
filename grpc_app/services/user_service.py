from __future__ import annotations

import grpc

from application.services.user_service import UserApplicationService
from application.dto import (
    UserCreateDTO,
    UserUpdateDTO,
    LoginDTO,
    ChangePasswordDTO,
)
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from grpc_app.generated.forge.v1 import user_pb2, user_pb2_grpc
from grpc_app.mappers.user import user_dto_to_proto, Empty


class UserService(user_pb2_grpc.UserServiceServicer):
    def __init__(self) -> None:
        self._svc = UserApplicationService(uow_factory=SQLAlchemyUnitOfWork)

    # Anonymous methods
    async def Register(self, request: user_pb2.RegisterRequest, context: grpc.aio.ServicerContext) -> user_pb2.UserReply:  # type: ignore[override]
        dto = UserCreateDTO(
            username=request.username,
            email=request.email,
            password=request.password,
            full_name=request.full_name or None,
            phone=request.phone or None,
        )
        user = await self._svc.register_user(dto)
        return user_pb2.UserReply(user=user_dto_to_proto(user))

    async def Login(self, request: user_pb2.LoginRequest, context: grpc.aio.ServicerContext) -> user_pb2.LoginReply:  # type: ignore[override]
        token = await self._svc.login(LoginDTO(username=request.username, password=request.password))
        return user_pb2.LoginReply(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            token_type=token.token_type,
            expires_in=token.expires_in,
        )

    async def Refresh(self, request: user_pb2.RefreshRequest, context: grpc.aio.ServicerContext) -> user_pb2.LoginReply:  # type: ignore[override]
        token = await self._svc.refresh_token(request.refresh_token)
        return user_pb2.LoginReply(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            token_type=token.token_type,
            expires_in=token.expires_in,
        )

    # Authenticated methods
    async def GetUser(self, request: user_pb2.GetUserRequest, context: grpc.aio.ServicerContext) -> user_pb2.UserReply:  # type: ignore[override]
        user = await self._svc.get_user(int(request.id))
        return user_pb2.UserReply(user=user_dto_to_proto(user))

    async def ListUsers(self, request: user_pb2.ListUsersRequest, context: grpc.aio.ServicerContext) -> user_pb2.ListUsersReply:  # type: ignore[override]
        page = int(request.page or 1)
        size = int(request.page_size or 20)
        skip = max(0, (page - 1) * size)
        is_active = request.is_active.value if request.HasField("is_active") else None

        users, total = await self._svc.list_users(skip=skip, limit=size, is_active=is_active)
        return user_pb2.ListUsersReply(
            items=[user_dto_to_proto(u) for u in users],
            total=int(total),
            page=page,
            page_size=size,
        )

    async def UpdateUser(self, request: user_pb2.UpdateUserRequest, context: grpc.aio.ServicerContext) -> user_pb2.UserReply:  # type: ignore[override]
        update_dto = UserUpdateDTO(
            full_name=request.full_name.value if request.HasField("full_name") else None,
            phone=request.phone.value if request.HasField("phone") else None,
        )
        user = await self._svc.update_user(int(request.id), update_dto)
        return user_pb2.UserReply(user=user_dto_to_proto(user))

    async def ChangePassword(self, request: user_pb2.ChangePasswordRequest, context: grpc.aio.ServicerContext) -> Empty:  # type: ignore[override]
        await self._svc.change_password(
            int(request.id),
            ChangePasswordDTO(old_password=request.old_password, new_password=request.new_password),
        )
        return Empty()

    async def ActivateUser(self, request: user_pb2.UserIdRequest, context: grpc.aio.ServicerContext) -> user_pb2.UserReply:  # type: ignore[override]
        user = await self._svc.activate_user(int(request.id))
        return user_pb2.UserReply(user=user_dto_to_proto(user))

    async def DeactivateUser(self, request: user_pb2.UserIdRequest, context: grpc.aio.ServicerContext) -> user_pb2.UserReply:  # type: ignore[override]
        user = await self._svc.deactivate_user(int(request.id))
        return user_pb2.UserReply(user=user_dto_to_proto(user))

    async def DeleteUser(self, request: user_pb2.UserIdRequest, context: grpc.aio.ServicerContext) -> Empty:  # type: ignore[override]
        await self._svc.delete_user(int(request.id))
        return Empty()

