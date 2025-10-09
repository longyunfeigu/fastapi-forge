"""
用户应用服务（application/services）- 编排领域服务和处理应用逻辑
"""
from typing import Optional, List, Callable, Tuple
from datetime import datetime, timezone

from domain.user.entity import User
from domain.user.service import UserDomainService
from domain.common.unit_of_work import AbstractUnitOfWork
from application.dto import (
    UserCreateDTO, UserUpdateDTO, UserResponseDTO,
    LoginDTO, TokenDTO, ChangePasswordDTO
)
from application.services.token_service import TokenService
from core.config import settings
from domain.common.exceptions import UserNotFoundException, UserInactiveException
from core.exceptions import UnauthorizedException, TokenExpiredException


class UserApplicationService:
    """用户应用服务 - 处理应用层逻辑"""

    def __init__(self, uow_factory: Callable[[], AbstractUnitOfWork]):
        self._uow_factory = uow_factory
        self._token_service = TokenService(uow_factory)
    
    async def _is_first_user_candidate(self) -> bool:
        """判断当前是否可能为首个用户（只读查询）。"""
        async with self._uow_factory(readonly=True) as uow:
            total = await uow.user_repository.count_all()
            return int(total) == 0

    async def register_user(self, user_data: UserCreateDTO) -> UserResponseDTO:
        """注册新用户（在可能的首个用户场景使用分布式锁避免并发竞态）。"""
        needs_lock = await self._is_first_user_candidate()

        cache = None
        if needs_lock and settings.redis.url:
            try:
                from infrastructure.external.cache import get_redis_client
                cache = await get_redis_client()
            except Exception:
                cache = None

        async def _do_register() -> UserResponseDTO:
            async with self._uow_factory() as uow:
                domain_service = UserDomainService(uow.user_repository)
                user = await domain_service.register_user(
                    username=user_data.username,
                    email=user_data.email,
                    password=user_data.password,
                    full_name=user_data.full_name,
                    phone=user_data.phone
                )

                events = domain_service.get_domain_events()
                for _event in events:
                    # 可以将事件发布到消息队列、指标系统等
                    pass

                return self._to_response_dto(user)

        # 如判断可能是首个用户且可用缓存锁，则在锁内再次执行（锁内将再次判断）
        if cache is not None:
            async with cache.lock(
                "first_superuser_init",
                timeout=settings.FIRST_SUPERUSER_LOCK_TIMEOUT,
                blocking_timeout=settings.FIRST_SUPERUSER_LOCK_BLOCKING_TIMEOUT,
            ):
                # 锁内再确认一次，确保只有一个请求能看到 total==0
                if await self._is_first_user_candidate():
                    return await _do_register()
                # 如果不再是首个用户，直接按常规注册
                return await _do_register()

        # 无锁情况下按常规注册（存在极小概率并发条件竞争，仅作为回退路径）
        return await _do_register()
    
    async def login(
        self,
        login_data: LoginDTO,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> TokenDTO:
        """用户登录（支持刷新令牌轮转）"""
        async with self._uow_factory() as uow:
            domain_service = UserDomainService(uow.user_repository)
            user = await domain_service.authenticate_user(
                username=login_data.username,
                password=login_data.password
            )

            access_token = self._token_service.create_access_token(user)
            # 重要：在同一事务/会话中创建刷新令牌，避免 MySQL 外键检查与用户行更新产生锁等待
            refresh_token = await self._token_service.create_refresh_token(
                user,
                device_info=device_info,
                ip_address=ip_address,
                uow=uow,
            )

            return TokenDTO(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            )
    
    async def get_user(self, user_id: int) -> UserResponseDTO:
        """获取用户信息"""
        async with self._uow_factory(readonly=True) as uow:
            user = await uow.user_repository.get_by_id(user_id)
            if not user:
                raise UserNotFoundException(str(user_id))
            return self._to_response_dto(user)
    
    async def get_user_by_username(self, username: str) -> UserResponseDTO:
        """根据用户名获取用户"""
        async with self._uow_factory(readonly=True) as uow:
            user = await uow.user_repository.get_by_username(username)
            if not user:
                raise UserNotFoundException(username)
            return self._to_response_dto(user)
    
    async def list_users(self, skip: int = 0, limit: int = 100,
                         is_active: Optional[bool] = None) -> Tuple[List[UserResponseDTO], int]:
        """获取用户列表（带总数）"""
        async with self._uow_factory(readonly=True) as uow:
            users = await uow.user_repository.get_all(skip, limit, is_active)
            total = await uow.user_repository.count_all(is_active)
            return [self._to_response_dto(user) for user in users], int(total)
    
    async def update_user(self, user_id: int, 
                         update_data: UserUpdateDTO) -> UserResponseDTO:
        """更新用户信息"""
        async with self._uow_factory() as uow:
            user = await uow.user_repository.get_by_id(user_id)
            if not user:
                raise UserNotFoundException(str(user_id))

            if update_data.full_name is not None:
                user.full_name = update_data.full_name
            if update_data.phone is not None:
                user.phone = update_data.phone
                user.validate_phone()

            user.updated_at = datetime.now(timezone.utc)
            updated_user = await uow.user_repository.update(user)

            return self._to_response_dto(updated_user)
    
    async def change_password(self, user_id: int,
                            password_data: ChangePasswordDTO) -> UserResponseDTO:
        """修改密码"""
        async with self._uow_factory() as uow:
            domain_service = UserDomainService(uow.user_repository)
            user = await domain_service.change_user_password(
                user_id=user_id,
                old_password=password_data.old_password,
                new_password=password_data.new_password
            )

            events = domain_service.get_domain_events()
            for _event in events:
                pass

            return self._to_response_dto(user)
    
    async def activate_user(self, user_id: int) -> UserResponseDTO:
        """激活用户"""
        async with self._uow_factory() as uow:
            domain_service = UserDomainService(uow.user_repository)
            user = await domain_service.activate_user(user_id)
            return self._to_response_dto(user)
    
    async def deactivate_user(self, user_id: int) -> UserResponseDTO:
        """停用用户"""
        async with self._uow_factory() as uow:
            domain_service = UserDomainService(uow.user_repository)
            user = await domain_service.deactivate_user(user_id)
            return self._to_response_dto(user)
    
    async def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        async with self._uow_factory() as uow:
            return await uow.user_repository.delete(user_id)
    
    async def verify_token(self, token: str) -> Optional[int]:
        """验证JWT令牌并返回用户ID（委托 TokenService）。

        - 过期: 抛出 TokenExpiredException（供上层统一处理）。
        - 无效: 返回 None（保持上层 401 无效凭据行为）。
        """
        return await self._token_service.verify_access_token(token)
    
    

    async def refresh_token(
        self,
        refresh_token: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> TokenDTO:
        """刷新令牌轮转 - 旧令牌失效，返回新令牌对"""
        return await self._token_service.rotate_refresh_token(
            refresh_token,
            device_info=device_info,
            ip_address=ip_address
        )

    async def logout_all_devices(self, user_id: int) -> int:
        """登出所有设备（撤销所有刷新令牌）"""
        return await self._token_service.revoke_all_user_tokens(
            user_id,
            reason="User initiated logout from all devices"
        )

    async def get_active_sessions(self, user_id: int) -> list:
        """获取用户的活跃登录会话"""
        return await self._token_service.get_active_sessions(user_id)
    
    def _to_response_dto(self, user: User) -> UserResponseDTO:
        """将领域实体转换为响应DTO"""
        return UserResponseDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            phone=user.phone,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login
        )
