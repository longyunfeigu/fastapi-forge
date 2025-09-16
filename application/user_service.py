"""
用户应用服务 - 编排领域服务和处理应用逻辑
"""
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import jwt

from domain.user.entity import User
from domain.user.service import UserDomainService
from domain.user.repository import UserRepository
from .dto import (
    UserCreateDTO, UserUpdateDTO, UserResponseDTO,
    LoginDTO, TokenDTO, ChangePasswordDTO
)
from core.config import settings


class UserApplicationService:
    """用户应用服务 - 处理应用层逻辑"""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
        self.domain_service = UserDomainService(user_repository)
    
    async def register_user(self, user_data: UserCreateDTO) -> UserResponseDTO:
        """注册新用户"""
        user = await self.domain_service.register_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            phone=user_data.phone
        )
        
        # 处理领域事件（例如发送欢迎邮件）
        events = self.domain_service.get_domain_events()
        for event in events:
            # 这里可以发布事件到消息队列或处理其他副作用
            pass
        
        return self._to_response_dto(user)
    
    async def login(self, login_data: LoginDTO) -> TokenDTO:
        """用户登录"""
        user = await self.domain_service.authenticate_user(
            username=login_data.username,
            password=login_data.password
        )
        
        if not user:
            raise ValueError("用户名或密码错误")
        
        # 生成JWT令牌
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
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")
        return self._to_response_dto(user)
    
    async def get_user_by_username(self, username: str) -> UserResponseDTO:
        """根据用户名获取用户"""
        user = await self.user_repository.get_by_username(username)
        if not user:
            raise ValueError("用户不存在")
        return self._to_response_dto(user)
    
    async def list_users(self, skip: int = 0, limit: int = 100,
                         is_active: Optional[bool] = None) -> List[UserResponseDTO]:
        """获取用户列表"""
        users = await self.user_repository.get_all(skip, limit, is_active)
        return [self._to_response_dto(user) for user in users]
    
    async def update_user(self, user_id: int, 
                         update_data: UserUpdateDTO) -> UserResponseDTO:
        """更新用户信息"""
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        # 更新用户信息
        if update_data.full_name is not None:
            user.full_name = update_data.full_name
        if update_data.phone is not None:
            user.phone = update_data.phone
            user.validate_phone()
        
        user.updated_at = datetime.now(timezone.utc)
        updated_user = await self.user_repository.update(user)
        
        return self._to_response_dto(updated_user)
    
    async def change_password(self, user_id: int,
                            password_data: ChangePasswordDTO) -> UserResponseDTO:
        """修改密码"""
        user = await self.domain_service.change_user_password(
            user_id=user_id,
            old_password=password_data.old_password,
            new_password=password_data.new_password
        )
        
        # 处理领域事件
        events = self.domain_service.get_domain_events()
        for event in events:
            # 可以发送密码修改通知邮件等
            pass
        
        return self._to_response_dto(user)
    
    async def activate_user(self, user_id: int) -> UserResponseDTO:
        """激活用户"""
        user = await self.domain_service.activate_user(user_id)
        return self._to_response_dto(user)
    
    async def deactivate_user(self, user_id: int) -> UserResponseDTO:
        """停用用户"""
        user = await self.domain_service.deactivate_user(user_id)
        return self._to_response_dto(user)
    
    async def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        return await self.user_repository.delete(user_id)
    
    async def verify_token(self, token: str) -> Optional[int]:
        """验证JWT令牌并返回用户ID"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            token_type = payload.get("type", "access")
            if token_type != "access":
                return None
            user_id = payload.get("sub")
            if user_id is None:
                return None
            return int(user_id)
        except jwt.PyJWTError:
            return None
    
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
