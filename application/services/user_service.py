"""
用户应用服务（application/services）- 编排领域服务和处理应用逻辑
"""
from typing import Optional, List, Callable, Tuple
from datetime import datetime, timedelta, timezone
import jwt

from domain.user.entity import User
from domain.user.service import UserDomainService
from domain.common.unit_of_work import AbstractUnitOfWork
from .dto import (
    UserCreateDTO, UserUpdateDTO, UserResponseDTO,
    LoginDTO, TokenDTO, ChangePasswordDTO
)
from core.config import settings
from domain.common.exceptions import UserNotFoundException, UserInactiveException
from core.exceptions import UnauthorizedException, TokenExpiredException


class UserApplicationService:
    """用户应用服务 - 处理应用层逻辑"""
    
    def __init__(self, uow_factory: Callable[[], AbstractUnitOfWork]):
        self._uow_factory = uow_factory
    
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
    
    async def login(self, login_data: LoginDTO) -> TokenDTO:
        """用户登录"""
        async with self._uow_factory() as uow:
            domain_service = UserDomainService(uow.user_repository)
            user = await domain_service.authenticate_user(
                username=login_data.username,
                password=login_data.password
            )

            access_token = self._create_access_token(user)
            refresh_token = self._create_refresh_token(user)

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
        """验证JWT令牌并返回用户ID。

        - 过期: 抛出 TokenExpiredException（供上层统一处理，返回 401 + 过期语义）。
        - 无效: 返回 None（上层保持当前行为，返回 401 无效凭据）。
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            # 令牌过期，抛出以便全局异常处理器映射到 TOKEN_EXPIRED
            raise TokenExpiredException()
        except jwt.InvalidTokenError:
            # 其它无效情况（签名错误、格式错误等）
            return None

        token_type = payload.get("type", "access")
        if token_type != "access":
            return None
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)
    
    def _create_access_token(self, user: User) -> str:
        """创建访问令牌"""
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user.id),
            "username": user.username,
            "is_superuser": user.is_superuser,
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    def _create_refresh_token(self, user: User) -> str:
        """创建刷新令牌"""
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {
            "sub": str(user.id),
            "username": user.username,
            "exp": expire,
            "type": "refresh"
        }
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    async def refresh_token(self, refresh_token: str) -> TokenDTO:
        """使用刷新令牌换取新的访问令牌"""
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpiredException()
        except jwt.PyJWTError:
            raise UnauthorizedException("无效的刷新令牌")

        if payload.get("type") != "refresh":
            raise UnauthorizedException("令牌类型错误")

        user_id = payload.get("sub")
        if user_id is None:
            raise UnauthorizedException("无效的刷新令牌")

        async with self._uow_factory() as uow:
            user = await uow.user_repository.get_by_id(int(user_id))
            if not user:
                raise UserNotFoundException(str(user_id))
            if not user.is_active:
                raise UserInactiveException()

            access_token = self._create_access_token(user)
            new_refresh_token = self._create_refresh_token(user)
            return TokenDTO(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            )
    
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
