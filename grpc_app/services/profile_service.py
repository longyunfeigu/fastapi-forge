from __future__ import annotations

import grpc
from core.logging_config import get_logger
from application.services.user_service import UserApplicationService
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from grpc_app.generated.forge.v1 import profile_pb2, profile_pb2_grpc, common_pb2


logger = get_logger(__name__)


class ProfileService(profile_pb2_grpc.ProfileServiceServicer):
    def __init__(self) -> None:
        # 复用用户应用服务作为数据来源，演示如何对接应用层
        self._usersvc = UserApplicationService(uow_factory=SQLAlchemyUnitOfWork)
    async def ListProfiles(
        self,
        request: profile_pb2.ListProfilesRequest,
        context: grpc.aio.ServicerContext,
    ) -> profile_pb2.ListProfilesReply:
        # 从应用层获取用户列表，并映射为 Profile 列表
        page = int(request.page.page or 1)
        size = int(request.page.page_size or 20)
        skip = max(0, (page - 1) * size)

        users, total = await self._usersvc.list_users(skip=skip, limit=size, is_active=True)
        items = [
            profile_pb2.Profile(
                id=int(u.id), full_name=u.full_name or u.username, bio=""
            )
            for u in users
        ]
        pages = (total + size - 1) // size if size > 0 else 0
        meta = common_pb2.PageMeta(total=int(total), page=page, page_size=size, pages=int(pages))
        return profile_pb2.ListProfilesReply(items=items, meta=meta)

    async def GetProfile(
        self,
        request: common_pb2.IdRequest,
        context: grpc.aio.ServicerContext,
    ) -> profile_pb2.Profile:
        u = await self._usersvc.get_user(int(request.id))
        return profile_pb2.Profile(id=int(u.id), full_name=u.full_name or u.username, bio="")
