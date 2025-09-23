"""
用户仓储实现 - 使用SQLAlchemy实现数据访问
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from domain.user.entity import User
from domain.user.repository import UserRepository
from infrastructure.models.user import UserModel
from core.logging_config import get_logger
from domain.common.exceptions import (
    UsernameAlreadyExistsException,
    UserAlreadyExistsException,
    UserNotFoundException,
)


logger = get_logger(__name__)


class SQLAlchemyUserRepository(UserRepository):
    """用户仓储的SQLAlchemy实现"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: UserModel) -> User:
        """将数据库模型转换为领域实体"""
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            phone=model.phone,
            full_name=model.full_name,
            hashed_password=model.hashed_password,
            is_active=model.is_active,
            is_superuser=model.is_superuser,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_login=model.last_login
        )

    def _to_model(self, entity: User) -> UserModel:
        """将领域实体转换为数据库模型"""
        return UserModel(
            id=entity.id,
            username=entity.username,
            email=entity.email,
            phone=entity.phone,
            full_name=entity.full_name,
            hashed_password=entity.hashed_password,
            is_active=entity.is_active,
            is_superuser=entity.is_superuser,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            last_login=entity.last_login
        )

    async def create(self, user: User) -> User:
        """创建用户"""
        try:
            db_user = self._to_model(user)
            self.session.add(db_user)
            await self.session.flush()  # 获取生成的ID
            await self.session.refresh(db_user)
            return self._to_entity(db_user)
        except IntegrityError as e:
            await self.session.rollback()
            msg = str(e).lower()
            if "username" in msg:
                logger.warning(
                    "create_user_conflict",
                    field="username",
                    username=user.username)
                raise UsernameAlreadyExistsException(user.username)
            if "email" in msg:
                logger.warning(
                    "create_user_conflict",
                    field="email",
                    email=user.email)
                raise UserAlreadyExistsException(user.email)
            raise

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        db_user = result.scalar_one_or_none()
        return self._to_entity(db_user) if db_user else None

    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        result = await self.session.execute(
            select(UserModel).where(UserModel.username == username)
        )
        db_user = result.scalar_one_or_none()
        return self._to_entity(db_user) if db_user else None

    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        result = await self.session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        db_user = result.scalar_one_or_none()
        return self._to_entity(db_user) if db_user else None

    async def get_all(self, skip: int = 0, limit: int = 100,
                      is_active: Optional[bool] = None) -> List[User]:
        """获取用户列表"""
        query = select(UserModel)

        if is_active is not None:
            query = query.where(UserModel.is_active == is_active)
        # 默认按创建时间倒序，再按ID倒序，确保分页稳定
        query = query.order_by(
            UserModel.created_at.desc(),
            UserModel.id.desc())
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        db_users = result.scalars().all()

        return [self._to_entity(db_user) for db_user in db_users]

    async def update(self, user: User) -> User:
        """更新用户"""
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise UserNotFoundException(str(user.id))

        # 更新字段
        db_user.username = user.username
        db_user.email = user.email
        db_user.phone = user.phone
        db_user.full_name = user.full_name
        db_user.hashed_password = user.hashed_password
        db_user.is_active = user.is_active
        db_user.is_superuser = user.is_superuser
        db_user.updated_at = user.updated_at
        db_user.last_login = user.last_login

        try:
            await self.session.flush()
        except IntegrityError as e:
            await self.session.rollback()
            msg = str(e).lower()
            if "username" in msg:
                logger.warning(
                    "update_user_conflict",
                    field="username",
                    user_id=user.id,
                    username=user.username)
                raise UsernameAlreadyExistsException(user.username)
            if "email" in msg:
                logger.warning(
                    "update_user_conflict",
                    field="email",
                    user_id=user.id,
                    email=user.email)
                raise UserAlreadyExistsException(user.email)
            raise
        await self.session.refresh(db_user)
        return self._to_entity(db_user)

    async def delete(self, user_id: int) -> bool:
        """删除用户"""
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            return False

        self.session.delete(db_user)
        await self.session.flush()
        return True

    async def exists_by_username(self, username: str) -> bool:
        """检查用户名是否存在"""
        result = await self.session.execute(
            select(func.count()).select_from(UserModel)
            .where(UserModel.username == username)
        )
        count = result.scalar()
        return count > 0

    async def exists_by_email(self, email: str) -> bool:
        """检查邮箱是否存在"""
        result = await self.session.execute(
            select(func.count()).select_from(UserModel)
            .where(UserModel.email == email)
        )
        count = result.scalar()
        return count > 0

    async def count_all(self, is_active: Optional[bool] = None) -> int:
        """统计用户数量"""
        query = select(func.count()).select_from(UserModel)

        if is_active is not None:
            query = query.where(UserModel.is_active == is_active)

        result = await self.session.execute(query)
        return result.scalar()
